"""69书吧交互式单本下载器（输入书籍 ID 即可下载）。"""

from curl_cffi.requests import AsyncSession
from bs4 import BeautifulSoup
import asyncio
import os
import sys
import io
import re
import random

from settings import PUBLIC_HEADERS, PROXY_URL, SEMAPHORE_COUNT

SEMAPHORE = asyncio.Semaphore(SEMAPHORE_COUNT)


def validate_filename(name):
    return re.sub(r'[\\/*?:"<>|]', "", name).strip()


async def download_chapter(session, chapter_url, chapter_title, save_dir):
    async with SEMAPHORE:
        try:
            await asyncio.sleep(random.uniform(1.5, 3.5))
            r = await session.get(
                chapter_url, headers=PUBLIC_HEADERS, proxy=PROXY_URL, timeout=30
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

                    safe_title = validate_filename(chapter_title)
                    file_path = os.path.join(save_dir, f"{safe_title}.txt")
                    with open(file_path, 'w', encoding='utf-8') as f:
                        f.write(clean_text)
                    print(f"✅ {safe_title}")
                else:
                    print(f"⚠️ 跳过: {chapter_title} (无正文)")
            elif r.status_code == 429:
                print(f"⛔ 429 被限流: {chapter_title} (稍后重试)")
                await asyncio.sleep(5)
            else:
                print(f"❌ 失败 [{r.status_code}]: {chapter_title}")

        except Exception as e:
            print(f"❌ 异常 {chapter_title}: {e}")


async def get_book_index(book_num):
    url = f'https://www.69shuba.com/book/{book_num}/'
    print(f"正在访问目录: {url} ...")

    async with AsyncSession(impersonate="chrome120") as session:
        try:
            r = await session.get(url, headers=PUBLIC_HEADERS, proxy=PROXY_URL, timeout=20)

            if r.status_code != 200:
                print(f"无法访问目录，状态码: {r.status_code}")
                return

            if b'charset=gbk' in r.content.lower() or b'charset="gbk"' in r.content.lower():
                r.encoding = 'gbk'
            else:
                r.encoding = 'utf-8'

            soup = BeautifulSoup(r.text, 'html.parser')
            title_tag = soup.find('title')
            if not title_tag:
                print("解析标题失败")
                return

            raw_title = title_tag.text.strip()
            book_title = raw_title.split("最")[0].strip() if "最" in raw_title else raw_title
            safe_book_title = validate_filename(book_title)
            os.makedirs(safe_book_title, exist_ok=True)

            chapter_list = soup.select('.catalog li a')
            if not chapter_list:
                chapter_list = soup.select('#catalog li a')

            print(f"📚 书名: {safe_book_title}")
            print(f"📊 发现 {len(chapter_list)} 章，启动慢速下载 (防封模式)...")

            tasks = []
            for link in chapter_list:
                href = link.get('href')
                c_title = link.text.strip()
                if href and href != "#":
                    tasks.append(download_chapter(session, href, c_title, safe_book_title))

            await asyncio.gather(*tasks)

        except Exception as e:
            print(f"运行错误: {e}")


if __name__ == '__main__':
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

    book_num = input("请输入书籍 ID -> ").strip()
    if book_num.isdigit():
        asyncio.run(get_book_index(book_num))
    else:
        print("错误：请输入纯数字 ID")
