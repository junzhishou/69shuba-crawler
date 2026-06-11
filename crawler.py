"""69书吧批量小说下载器（主程序）。"""

from curl_cffi.requests import AsyncSession
from bs4 import BeautifulSoup
from tqdm.asyncio import tqdm
import asyncio
import os
import sys
import io
import re
import random
import zipfile
import shutil

from settings import PUBLIC_HEADERS, PROXY_URL, BASE_DOWNLOAD_DIR, SEMAPHORE_COUNT

SEMAPHORE = asyncio.Semaphore(SEMAPHORE_COUNT)

# 书籍 ID 列表，在 https://www.69shuba.com/book/{id}/ 中获取
BOOKS_TO_DOWNLOAD = [
    # "88724",  # 示例：苟在初圣魔门当人材
]


def validate_filename(name):
    return re.sub(r'[\\/*?:"<>|]', "", name).strip()


async def download_chapter(session, chapter_url, chapter_title, save_dir, pbar, serial_num):
    """带重试机制的章节下载。"""
    safe_title = validate_filename(chapter_title)
    filename = f"{serial_num:05d}_{safe_title}.txt"
    file_path = os.path.join(save_dir, filename)

    if os.path.exists(file_path) and os.path.getsize(file_path) > 0:
        pbar.update(1)
        return

    async with SEMAPHORE:
        max_retries = 5
        for attempt in range(max_retries):
            try:
                await asyncio.sleep(random.uniform(2, 5))
                r = await session.get(
                    chapter_url, headers=PUBLIC_HEADERS, proxy=PROXY_URL, timeout=60
                )

                if r.status_code == 200:
                    if b'charset=gbk' in r.content.lower() or b'charset="gbk"' in r.content.lower():
                        r.encoding = 'gbk'
                    else:
                        r.encoding = 'utf-8'

                    soup = BeautifulSoup(r.text, 'html.parser')
                    text_element = soup.find('div', class_='txtnav')

                    if text_element:
                        raw_text = text_element.get_text()
                        clean_text = '\n'.join(
                            line.strip()
                            for line in raw_text.strip().split('\n')
                            if line.strip()
                        )
                        with open(file_path, 'w', encoding='utf-8') as f:
                            f.write(clean_text)
                        pbar.set_postfix_str(f"OK: {serial_num:05d}")
                        pbar.update(1)
                        return

                    pbar.write(f"⚠️ 跳过(无正文): {chapter_title}")
                    pbar.update(1)
                    return

                if r.status_code == 429:
                    wait_time = 30 + (attempt * 10)
                    pbar.write(
                        f"⛔ 429 限流: {chapter_title} "
                        f"(第{attempt + 1}次重试，暂停{wait_time}秒...)"
                    )
                    await asyncio.sleep(wait_time)
                    continue

                pbar.write(f"❌ 失败 [{r.status_code}]: {chapter_title}")
                continue

            except Exception as e:
                pbar.write(f"❌ 异常 {chapter_title}: {e}")
                await asyncio.sleep(5)
                continue

        pbar.write(f"💀 彻底失败(放弃): {chapter_title}")
        pbar.update(1)


def post_process_files(temp_chapter_dir, book_title):
    """合并章节、打包 ZIP 并清理临时文件。"""
    print(f"\n✅ [{book_title}] 下载完成！开始合并...")

    merged_file_path = os.path.join(BASE_DOWNLOAD_DIR, f"{book_title}_全本by69书吧.txt")
    zip_file_path = os.path.join(BASE_DOWNLOAD_DIR, f"{book_title}_分章包.zip")

    all_files = [f for f in os.listdir(temp_chapter_dir) if f.endswith(".txt")]
    all_files.sort()

    if not all_files:
        print("⚠️ 目录下没有文件，跳过合并。")
        return

    files_to_clean = []

    print(f"正在合并 {len(all_files)} 个文件，将自动忽略每章的第1行和第3行...")
    with open(merged_file_path, 'w', encoding='utf-8') as outfile:
        for filename in all_files:
            file_path = os.path.join(temp_chapter_dir, filename)
            chapter_title_in_txt = filename.split('_', 1)[1].replace('.txt', '')

            if os.path.exists(file_path):
                with open(file_path, 'r', encoding='utf-8') as infile:
                    lines = infile.readlines()
                    filtered_lines = [
                        line for i, line in enumerate(lines) if i not in (0, 2)
                    ]
                    content = "".join(filtered_lines)

                    outfile.write(chapter_title_in_txt + "\n\n")
                    outfile.write(content)
                    outfile.write("\n\n\n")
                    files_to_clean.append(file_path)

    print(f"正在压缩: {os.path.basename(zip_file_path)} ...")
    with zipfile.ZipFile(zip_file_path, 'w', zipfile.ZIP_DEFLATED) as zf:
        for file_path in files_to_clean:
            zf.write(file_path, arcname=os.path.basename(file_path))

    try:
        if os.path.exists(temp_chapter_dir):
            shutil.rmtree(temp_chapter_dir)
            print("🗑️ 已删除临时文件夹")
    except Exception as e:
        print(f"清理文件出错: {e}")

    print(f"🎉 [{book_title}] 处理完毕！")


async def process_single_book(book_num):
    url = f'https://www.69shuba.com/book/{book_num}/'
    print(f"\n========================================")
    print(f"正在获取书籍 ID: {book_num} ...")

    async with AsyncSession(impersonate="chrome120") as session:
        try:
            r = await session.get(url, headers=PUBLIC_HEADERS, proxy=PROXY_URL, timeout=30)
            if r.status_code != 200:
                print(f"❌ 无法访问目录 {r.status_code}")
                return

            if b'charset=gbk' in r.content.lower() or b'charset="gbk"' in r.content.lower():
                r.encoding = 'gbk'
            else:
                r.encoding = 'utf-8'

            soup = BeautifulSoup(r.text, 'html.parser')
            title_tag = soup.find('title')
            if not title_tag:
                print("❌ 解析标题失败")
                return

            raw_title = title_tag.text.strip()
            book_title = raw_title.split("最")[0].strip() if "最" in raw_title else raw_title
            safe_book_title = validate_filename(book_title)

            final_txt_path = os.path.join(BASE_DOWNLOAD_DIR, f"{safe_book_title}_全本by69书吧.txt")
            if os.path.exists(final_txt_path):
                print(f"⏭️  跳过已完成: 《{safe_book_title}》")
                return

            temp_chapter_dir = os.path.join(BASE_DOWNLOAD_DIR, safe_book_title)
            os.makedirs(temp_chapter_dir, exist_ok=True)

            chapter_list = soup.select('.catalog li a')
            if not chapter_list:
                chapter_list = soup.select('#catalog li a')

            if chapter_list:
                first_text = chapter_list[0].text
                last_text = chapter_list[-1].text
                is_reversed = "第1章" in last_text or "第一章" in last_text
                try:
                    first_num = int(re.search(r'(\d+)', first_text).group(1))
                    last_num = int(re.search(r'(\d+)', last_text).group(1))
                    if first_num > last_num:
                        is_reversed = True
                except (AttributeError, ValueError):
                    pass

                if is_reversed:
                    print("🔄 修正倒序列表...")
                    chapter_list.reverse()

            print(f"📚 书名: 《{safe_book_title}》")
            print(f"📊 章节数: {len(chapter_list)} 章")

            tasks = []
            with tqdm(total=len(chapter_list), unit="章", desc="下载中", ncols=100, mininterval=0.5) as pbar:
                for idx, link in enumerate(chapter_list):
                    href = link.get('href')
                    c_title = link.text.strip()
                    if href and href != "#":
                        tasks.append(
                            download_chapter(session, href, c_title, temp_chapter_dir, pbar, idx + 1)
                        )

                tasks.reverse()
                await asyncio.gather(*tasks)

            post_process_files(temp_chapter_dir, safe_book_title)

        except Exception as e:
            print(f"❌ 运行错误 (ID: {book_num}): {e}")
            import traceback
            traceback.print_exc()


async def main():
    if not BOOKS_TO_DOWNLOAD:
        print("请先在 crawler.py 的 BOOKS_TO_DOWNLOAD 中配置书籍 ID。")
        return

    os.makedirs(BASE_DOWNLOAD_DIR, exist_ok=True)

    total = len(BOOKS_TO_DOWNLOAD)
    print(f"🚀 批量任务开始: 共 {total} 本")

    for i, book_id in enumerate(BOOKS_TO_DOWNLOAD):
        await process_single_book(book_id)
        if i < total - 1:
            print("⏳ 休息 5 秒...")
            await asyncio.sleep(5)

    print("\n🏁 全部完成")


if __name__ == '__main__':
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
    asyncio.run(main())
