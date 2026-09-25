"""69书吧小说下载器。

支持传入书籍 ID 或完整目录 URL，下载分章文件并生成合并 TXT 与 ZIP。
"""

from __future__ import annotations

import argparse
import asyncio
import os
import random
import re
import shutil
import sys
import zipfile
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable, Sequence
from urllib.parse import urljoin, urlparse

from bs4 import BeautifulSoup
from curl_cffi.requests import AsyncSession
from tqdm import tqdm


SITE_ROOT = "https://www.69shuba.com"
DEFAULT_DOWNLOAD_DIR = Path("download")
BOOK_URL_RE = re.compile(r"^https?://(?:www\.)?69shuba\.com/book/(\d+)/?$", re.I)
CHAPTER_PATH_RE = re.compile(r"^/txt/(\d+)/(\d+)/?$", re.I)
CHARSET_RE = re.compile(br"charset\s*=\s*['\"]?([\w-]+)", re.I)
CHAPTER_NUMBER_RE = re.compile(r"第\s*(\d+)\s*章")


@dataclass(frozen=True)
class Chapter:
    serial: int
    title: str
    url: str


@dataclass(frozen=True)
class DownloadResult:
    chapter: Chapter
    path: Path
    ok: bool
    error: str = ""


def validate_filename(name: str) -> str:
    """移除 Windows/macOS 不适合出现在文件名中的字符。"""
    cleaned = re.sub(r'[\\/*?:"<>|\x00-\x1f]', "", name).strip().rstrip(".")
    return cleaned or "未命名"


def target_to_book_url(target: str) -> tuple[str, str]:
    """把纯数字 ID 或 69书吧目录 URL 规范化为 (book_id, url)。"""
    target = target.strip()
    if target.isdigit():
        return target, f"{SITE_ROOT}/book/{target}/"

    match = BOOK_URL_RE.fullmatch(target)
    if not match:
        raise ValueError(f"不是有效的书籍 ID 或 69书吧目录 URL：{target}")
    book_id = match.group(1)
    return book_id, f"{SITE_ROOT}/book/{book_id}/"


def decode_html(content: bytes, content_type: str = "") -> str:
    """按页面自身声明解码；站点响应头有时会把 GBK 错标为 UTF-8。"""
    sample = content[:4096]
    match = CHARSET_RE.search(sample)
    declared = match.group(1).decode("ascii", "ignore").lower() if match else ""

    if declared in {"gbk", "gb2312", "gb18030"}:
        encoding = "gb18030"
    elif declared:
        encoding = declared
    else:
        header_match = re.search(r"charset=([\w-]+)", content_type, re.I)
        encoding = header_match.group(1) if header_match else "utf-8"

    try:
        return content.decode(encoding)
    except (LookupError, UnicodeDecodeError):
        for fallback in ("gb18030", "utf-8"):
            try:
                return content.decode(fallback)
            except UnicodeDecodeError:
                continue
        return content.decode("utf-8", "replace")


def is_challenge_page(html: str) -> bool:
    lowered = html.lower()
    return any(
        marker in lowered
        for marker in (
            "<title>just a moment...</title>",
            "cf-chl-",
            "challenges.cloudflare.com",
            "cf-mitigated",
        )
    )


def parse_book_page(html: str, book_id: str, book_url: str) -> tuple[str, list[Chapter]]:
    soup = BeautifulSoup(html, "html.parser")
    title_tag = soup.find("title")
    if not title_tag:
        raise ValueError("目录页没有 title，可能是站点页面已变更")

    raw_title = title_tag.get_text(" ", strip=True)
    book_title = re.split(r"最新章节|章节列表|[-_]69书吧", raw_title, maxsplit=1)[0].strip()
    book_title = validate_filename(book_title)

    links = soup.select("#catalog li a") or soup.select(".catalog li a")
    entries: list[tuple[str, str]] = []
    seen: set[str] = set()
    for link in links:
        href = (link.get("href") or "").strip()
        absolute_url = urljoin(book_url, href)
        parsed = urlparse(absolute_url)
        match = CHAPTER_PATH_RE.fullmatch(parsed.path)
        if not match or match.group(1) != book_id or absolute_url in seen:
            continue
        title = link.get_text(" ", strip=True)
        if not title:
            continue
        entries.append((title, absolute_url))
        seen.add(absolute_url)

    if not entries:
        raise ValueError("没有解析到章节链接，可能是目录选择器已失效")

    numbered = [
        int(match.group(1))
        for title, _ in entries
        if (match := CHAPTER_NUMBER_RE.search(title))
    ]
    if len(numbered) >= 2 and numbered[0] > numbered[-1]:
        entries.reverse()

    chapters = [
        Chapter(serial=index, title=title, url=url)
        for index, (title, url) in enumerate(entries, start=1)
    ]
    return book_title, chapters


def parse_chapter_text(html: str, expected_title: str) -> str:
    soup = BeautifulSoup(html, "html.parser")
    container = soup.select_one("div.txtnav")
    if container is None:
        raise ValueError("章节页没有 div.txtnav 正文容器")

    for selector in ("h1", ".txtinfo", "#txtright", "script", "style", "nav"):
        for element in container.select(selector):
            element.decompose()

    lines = [line.strip() for line in container.get_text("\n").splitlines() if line.strip()]
    if lines and lines[0] == expected_title.strip():
        lines.pop(0)
    if not lines:
        raise ValueError("章节正文为空")
    return "\n\n".join(lines)


def chapter_path(directory: Path, chapter: Chapter) -> Path:
    return directory / f"{chapter.serial:05d}_{validate_filename(chapter.title)}.txt"


def is_valid_chapter_file(path: Path) -> bool:
    """短通知也可能只有几十字节；只拒绝不存在、空白或不可读的文件。"""
    if not path.is_file() or path.stat().st_size == 0:
        return False
    try:
        return bool(path.read_text(encoding="utf-8").strip())
    except (OSError, UnicodeDecodeError):
        return False


async def request_html(
    session: AsyncSession,
    url: str,
    *,
    headers: dict[str, str],
    proxy: str | None,
    timeout: int,
) -> tuple[int, str]:
    kwargs = {"headers": headers, "timeout": timeout}
    if proxy:
        kwargs["proxy"] = proxy
    response = await session.get(url, **kwargs)
    html = decode_html(response.content, response.headers.get("content-type", ""))
    return response.status_code, html


async def download_chapter(
    session: AsyncSession,
    chapter: Chapter,
    directory: Path,
    semaphore: asyncio.Semaphore,
    pbar: tqdm,
    *,
    headers: dict[str, str],
    proxy: str | None,
    retries: int,
    min_delay: float,
    max_delay: float,
) -> DownloadResult:
    path = chapter_path(directory, chapter)
    if is_valid_chapter_file(path):
        pbar.update(1)
        return DownloadResult(chapter, path, True)

    last_error = "未知错误"
    async with semaphore:
        for attempt in range(1, retries + 1):
            if max_delay > 0:
                await asyncio.sleep(random.uniform(min_delay, max_delay))
            try:
                status, html = await request_html(
                    session,
                    chapter.url,
                    headers=headers,
                    proxy=proxy,
                    timeout=60,
                )
                if status == 200 and not is_challenge_page(html):
                    text = parse_chapter_text(html, chapter.title)
                    temp_path = path.with_suffix(path.suffix + ".part")
                    temp_path.write_text(text + "\n", encoding="utf-8")
                    os.replace(temp_path, path)
                    pbar.set_postfix_str(f"OK {chapter.serial:05d}")
                    pbar.update(1)
                    return DownloadResult(chapter, path, True)

                if is_challenge_page(html):
                    last_error = "Cloudflare 挑战页"
                else:
                    last_error = f"HTTP {status}"
            except Exception as exc:  # 网络、解析、磁盘异常都进入有上限的重试
                last_error = str(exc)

            if attempt < retries:
                wait_seconds = min(60.0, 2 ** attempt + random.random() * 2)
                pbar.write(
                    f"⚠️ {chapter.title}：{last_error}，"
                    f"第 {attempt}/{retries} 次失败，{wait_seconds:.1f}s 后重试"
                )
                await asyncio.sleep(wait_seconds)

    pbar.write(f"❌ {chapter.title}：重试 {retries} 次后失败（{last_error}）")
    pbar.update(1)
    return DownloadResult(chapter, path, False, last_error)


def build_outputs(directory: Path, book_title: str, chapters: Sequence[Chapter]) -> tuple[Path, Path]:
    """仅在章节齐全时生成最终 TXT/ZIP，保留分章目录便于续传。"""
    expected_paths = [chapter_path(directory, chapter) for chapter in chapters]
    missing = [path for path in expected_paths if not is_valid_chapter_file(path)]
    if missing:
        raise RuntimeError(f"仍缺少 {len(missing)} 个章节，拒绝生成不完整的最终文件")

    output_dir = directory.parent
    merged_path = output_dir / f"{book_title}_全本by69书吧.txt"
    zip_path = output_dir / f"{book_title}_分章包.zip"
    merged_temp = merged_path.with_suffix(merged_path.suffix + ".part")
    zip_temp = zip_path.with_suffix(zip_path.suffix + ".part")

    with merged_temp.open("w", encoding="utf-8", newline="\n") as output:
        for chapter, path in zip(chapters, expected_paths):
            output.write(f"{chapter.title}\n\n")
            output.write(path.read_text(encoding="utf-8").strip())
            output.write("\n\n\n")

    with zipfile.ZipFile(zip_temp, "w", zipfile.ZIP_DEFLATED) as archive:
        for path in expected_paths:
            archive.write(path, arcname=path.name)

    os.replace(merged_temp, merged_path)
    os.replace(zip_temp, zip_path)
    return merged_path, zip_path


async def process_book(args: argparse.Namespace, target: str) -> bool:
    book_id, book_url = target_to_book_url(target)
    headers = {
        "User-Agent": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/136.0.0.0 Safari/537.36"
        ),
        "Referer": book_url,
    }
    if args.cookie:
        headers["Cookie"] = args.cookie

    print(f"\n正在读取目录：{book_url}")
    async with AsyncSession(impersonate="chrome") as session:
        status, html = await request_html(
            session,
            book_url,
            headers=headers,
            proxy=args.proxy,
            timeout=45,
        )
        if status != 200 or is_challenge_page(html):
            detail = "Cloudflare 挑战页" if is_challenge_page(html) else f"HTTP {status}"
            raise RuntimeError(f"目录访问失败：{detail}")

        book_title, chapters = parse_book_page(html, book_id, book_url)

    print(f"书名：《{book_title}》；有效目录项：{len(chapters)}")
    output_dir = Path(args.output).expanduser().resolve()
    chapter_dir = output_dir / validate_filename(book_title)
    chapter_dir.mkdir(parents=True, exist_ok=True)
    semaphore = asyncio.Semaphore(args.concurrency)
    results: list[DownloadResult] = []

    with tqdm(total=len(chapters), unit="章", desc="下载", dynamic_ncols=True) as pbar:
        for start in range(0, len(chapters), args.session_batch_size):
            batch = chapters[start : start + args.session_batch_size]
            # Cloudflare 会逐渐提高长会话的挑战频率。小批量轮换 TLS/浏览器会话，
            # 并先访问目录页预热，能保持稳定且不会影响已有文件的断点续传。
            async with AsyncSession(impersonate="chrome") as session:
                for warmup_attempt in range(1, 4):
                    status, warmup_html = await request_html(
                        session,
                        book_url,
                        headers=headers,
                        proxy=args.proxy,
                        timeout=45,
                    )
                    if status == 200 and not is_challenge_page(warmup_html):
                        break
                    if warmup_attempt < 3:
                        await asyncio.sleep(2 ** warmup_attempt)

                tasks = [
                    download_chapter(
                        session,
                        chapter,
                        chapter_dir,
                        semaphore,
                        pbar,
                        headers=headers,
                        proxy=args.proxy,
                        retries=args.retries,
                        min_delay=args.min_delay,
                        max_delay=args.max_delay,
                    )
                    for chapter in batch
                ]
                results.extend(await asyncio.gather(*tasks))

    failures = [result for result in results if not result.ok]
    if failures:
        print(f"\n下载未完成：{len(failures)} 个目录项失败，分章文件已保留，可重跑续传。")
        for result in failures[:20]:
            print(f"  - {result.chapter.title}: {result.error}")
        return False

    merged_path, zip_path = build_outputs(chapter_dir, book_title, chapters)
    if not args.keep_chapters:
        shutil.rmtree(chapter_dir)
    print(f"\n下载完成：\n  TXT: {merged_path}\n  ZIP: {zip_path}")
    return True


def env_targets() -> list[str]:
    raw = os.getenv("SHUBA_BOOK_IDS", "")
    return [item.strip() for item in raw.split(",") if item.strip()]


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="下载 69书吧小说并生成合并 TXT 与分章 ZIP")
    parser.add_argument("targets", nargs="*", help="书籍 ID 或完整目录 URL，可传多个")
    parser.add_argument("-o", "--output", default=str(DEFAULT_DOWNLOAD_DIR), help="输出目录")
    parser.add_argument(
        "-c",
        "--concurrency",
        type=int,
        default=int(os.getenv("SHUBA_SEMAPHORE", "2")),
        help="并发数，默认 2",
    )
    parser.add_argument("--retries", type=int, default=6, help="每章最大尝试次数，默认 6")
    parser.add_argument(
        "--session-batch-size",
        type=int,
        default=25,
        help="每个浏览器会话处理的目录项数，默认 25",
    )
    parser.add_argument("--min-delay", type=float, default=0.6, help="请求前最短随机延迟")
    parser.add_argument("--max-delay", type=float, default=1.4, help="请求前最长随机延迟")
    parser.add_argument("--proxy", default=os.getenv("SHUBA_PROXY") or None, help="可选 HTTP/SOCKS 代理")
    parser.add_argument("--cookie", default=os.getenv("SHUBA_COOKIE") or "", help="可选 Cookie")
    parser.add_argument("--keep-chapters", action="store_true", help="成功后保留分章目录")
    return parser


def validate_args(parser: argparse.ArgumentParser, args: argparse.Namespace) -> None:
    if not args.targets:
        args.targets = env_targets()
    if not args.targets:
        parser.error("请传入书籍 ID/URL，或设置 SHUBA_BOOK_IDS")
    if args.concurrency < 1:
        parser.error("--concurrency 必须大于 0")
    if args.retries < 1:
        parser.error("--retries 必须大于 0")
    if args.session_batch_size < 1:
        parser.error("--session-batch-size 必须大于 0")
    if args.min_delay < 0 or args.max_delay < args.min_delay:
        parser.error("随机延迟必须满足 0 <= min-delay <= max-delay")


async def async_main(args: argparse.Namespace) -> int:
    Path(args.output).expanduser().mkdir(parents=True, exist_ok=True)
    all_ok = True
    for target in args.targets:
        try:
            all_ok = await process_book(args, target) and all_ok
        except Exception as exc:
            all_ok = False
            print(f"\n❌ {target}：{exc}", file=sys.stderr)
    return 0 if all_ok else 1


def main(argv: Iterable[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    validate_args(parser, args)
    return asyncio.run(async_main(args))


if __name__ == "__main__":
    raise SystemExit(main())
