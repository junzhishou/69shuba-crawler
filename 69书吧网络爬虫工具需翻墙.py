from curl_cffi.requests import AsyncSession
from bs4 import BeautifulSoup
from tqdm.asyncio import tqdm
import asyncio
import os
import sys
import io
import time
import re
import random
import zipfile  # 🟢 引入压缩库
import shutil  # 🟢 引入文件操作库(用于删除空文件夹)

# --- 配置区域 ---

SEMAPHORE = asyncio.Semaphore(2)

PUBLIC_HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/143.0.0.0 Safari/537.36",
    "Cookie": "zh_choose=s; _ga_04LTEL5PWY=GS2.1.s1767008106$o1$g0$t1767008106$j60$l0$h0; _ga=GA1.1.2030536588.1767008106",
    "Referer": "https://www.69shuba.com/",
}

PROXY_URL = "http://127.0.0.1:7890"


# ----------------

def validate_filename(name):
    return re.sub(r'[\\/*?:"<>|]', "", name).strip()


async def download_chapter(session, chapter_url, chapter_title, save_dir, pbar):
    safe_title = validate_filename(chapter_title)
    file_path = os.path.join(save_dir, f"{safe_title}.txt")

    # 检查文件是否存在
    if os.path.exists(file_path):
        if os.path.getsize(file_path) > 0:
            pbar.update(1)  # 静默跳过
            return

    async with SEMAPHORE:
        try:
            await asyncio.sleep(random.uniform(3, 6))

            r = await session.get(chapter_url, headers=PUBLIC_HEADERS, proxy=PROXY_URL, timeout=60)
            content_size = len(r.content)

            if r.status_code == 200:
                if b'charset=gbk' in r.content.lower() or b'charset="gbk"' in r.content.lower():
                    r.encoding = 'gbk'
                else:
                    r.encoding = 'utf-8'

                soup = BeautifulSoup(r.text, 'html.parser')
                text_element = soup.find('div', class_='txtnav')

                if text_element:
                    raw_text = text_element.get_text()
                    clean_text = '\n'.join(line.strip() for line in raw_text.strip().split('\n') if line.strip())

                    with open(file_path, 'w', encoding='utf-8') as f:
                        f.write(clean_text)

                    pbar.set_postfix_str(f"新下载: {safe_title[:10]}... {content_size / 1024:.1f}KB")
                else:
                    pbar.write(f"⚠️ 跳过: {chapter_title} (无正文)")
            elif r.status_code == 429:
                pbar.write(f"⛔ 429 被限流: {chapter_title} (暂停 30 秒...)")
                await asyncio.sleep(30)
            else:
                pbar.write(f"❌ 失败 [{r.status_code}]: {chapter_title}")

        except Exception as e:
            pbar.write(f"❌ 异常 {chapter_title}: {e}")
        finally:
            pbar.update(1)


def post_process_files(save_dir, book_title, chapter_list):
    """
    后处理：合并TXT -> 打包ZIP -> 删除零散文件
    """
    print(f"\n✅ 下载完成！开始后期处理...")

    merged_file = f"{book_title}_全本by69书吧.txt"
    zip_file = f"{book_title}_分章包.zip"

    # 倒序列表反转回正序 (第1章在前)
    reading_order_list = chapter_list[::-1]

    files_to_clean = []  # 记录需要删除的文件路径

    # --- 1. 合并文件 ---
    print(f"正在合并: {merged_file} ...")
    with open(merged_file, 'w', encoding='utf-8') as outfile:
        count = 0
        for link in reading_order_list:
            c_title = link.text.strip()
            safe_title = validate_filename(c_title)
            file_path = os.path.join(save_dir, f"{safe_title}.txt")

            if os.path.exists(file_path):
                with open(file_path, 'r', encoding='utf-8') as infile:
                    content = infile.read()
                    outfile.write(c_title + "\n\n")
                    outfile.write(content)
                    outfile.write("\n\n\n")
                    count += 1
                    files_to_clean.append(file_path)  # 加入待删除列表
            else:
                pass  # 缺失章节不处理

    # --- 2. 打包 ZIP ---
    print(f"正在压缩: {zip_file} ...")
    # compression=zipfile.ZIP_DEFLATED 需要 zlib 库，通常 Python 自带
    with zipfile.ZipFile(zip_file, 'w', zipfile.ZIP_DEFLATED) as zf:
        for file_path in files_to_clean:
            # arcname 是文件在压缩包里的名字，我们只保留文件名，不要路径
            file_name = os.path.basename(file_path)
            zf.write(file_path, arcname=file_name)

    # --- 3. 清理零散文件 ---
    print("正在清理零散文件...")
    try:
        # 方法一：一个个删文件
        # for file_path in files_to_clean:
        #     os.remove(file_path)

        # 方法二：直接暴力删除整个文件夹 (更干净，把文件夹也删了)
        if os.path.exists(save_dir):
            shutil.rmtree(save_dir)
            print(f"🗑️ 已删除临时文件夹: {save_dir}")

    except Exception as e:
        print(f"清理文件时出错: {e}")

    print(f"\n🎉 全部搞定！")
    print(f"📘 全本小说: {os.path.abspath(merged_file)}")
    print(f"📦 分章备份: {os.path.abspath(zip_file)}")


async def get_book_index(book_num):
    url = f'https://www.69shuba.com/book/{book_num}/'
    print(f"正在访问目录: {url} ...")

    async with AsyncSession(impersonate="chrome120") as session:
        try:
            r = await session.get(url, headers=PUBLIC_HEADERS, proxy=PROXY_URL, timeout=30)

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

            if not os.path.exists(safe_book_title):
                os.makedirs(safe_book_title)

            chapter_list = soup.select('.catalog li a')
            if not chapter_list:
                chapter_list = soup.select('#catalog li a')

            chapter_list.reverse()

            print(f"📚 书名: {safe_book_title}")
            print(f"📊 发现 {len(chapter_list)} 章，开始下载...")

            tasks = []
            with tqdm(total=len(chapter_list), unit="章", desc="进度", ncols=100, mininterval=0.5) as pbar:
                for link in chapter_list:
                    href = link.get('href')
                    c_title = link.text.strip()
                    if href and href != "#":
                        tasks.append(download_chapter(session, href, c_title, safe_book_title, pbar))

                await asyncio.gather(*tasks)

            # 调用新的后处理函数
            post_process_files(safe_book_title, safe_book_title, chapter_list)

        except Exception as e:
            print(f"运行错误: {e}")


if __name__ == '__main__':
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

    default_id = "74678"  # 逼我重生是吧
    # default_id = "49986" # 都重生了谁谈恋爱啊
    # default_id = "74644" # 都重生了谁考公务员啊
    # default_id = "51567" # 我的模拟长生路
    # default_id = "40345" # 我的女友来自未来！
    # default_id = "51434" # 玄鉴仙族
    # default_id = "51290" # 国民法医
    # default_id = "46867" # 我本无意成仙
    # default_id = "76917" # 志怪书
    # default_id = "46957" # 谁让他修仙的！
    # default_id = "56146" # 从斩妖除魔开始长生不死
    # default_id = "74768" # 晋末长剑
    # default_id = "89321" # 我的化身正在成为最终BOSS
    # default_id = "88724" # 苟在初圣魔门当人材
    # default_id = "51584" # 我的诡异人生
    # default_id = "83216" # 捞尸人
    user_input = input(f"请输入书籍 ID (默认 {default_id}) -> ").strip()
    if not user_input:
        book_num = default_id
        print(f"使用默认 ID: {book_num}")
    else:
        book_num = user_input

    if book_num.isdigit():
        asyncio.run(get_book_index(book_num))
    else:
        print("错误：请输入纯数字 ID")
