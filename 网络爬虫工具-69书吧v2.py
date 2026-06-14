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
import zipfile
import shutil

# --- 配置区域 ---

# 并发数 (建议保持 2-3，不要太高)
SEMAPHORE = asyncio.Semaphore(1)

# 下载目录
BASE_DOWNLOAD_DIR = "download"

# 书籍 ID 列表
BOOKS_TO_DOWNLOAD = [
    "74678",  # 逼我重生是吧
    # "49986",  # 都重生了谁谈恋爱啊
    # "74644",  # 都重生了谁考公务员啊
    # "51567",  # 我的模拟长生路
    # "40345",  # 我的女友来自未来！
    # "51434",  # 玄鉴仙族
    # "51290",  # 国民法医
    # "46867",  # 我本无意成仙
    # "76917",  # 志怪书
    # "46957",  # 谁让他修仙的！
    # "56146",  # 从斩妖除魔开始长生不死
    # "74768",  # 晋末长剑
    # "89321",  # 我的化身正在成为最终BOSS
    # "88724",  # 苟在初圣魔门当人材
    # "51584",  # 我的诡异人生
    # "83216",  # 捞尸人
]

PUBLIC_HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/143.0.0.0 Safari/537.36",
    # ⚠️ 如果 403 报错，请更新 Cookie
    "Cookie": "zh_choose=s; _ga_04LTEL5PWY=GS2.1.s1767008106$o1$g0$t1767008106$j60$l0$h0; _ga=GA1.1.2030536588.1767008106",
    "Referer": "https://www.69shuba.com/",
}

PROXY_URL = "http://127.0.0.1:7890"


# ----------------

def validate_filename(name):
    return re.sub(r'[\\/*?:"<>|]', "", name).strip()


async def download_chapter(session, chapter_url, chapter_title, save_dir, pbar, serial_num):
    """
    带重试机制的下载函数
    """
    safe_title = validate_filename(chapter_title)
    filename = f"{serial_num:05d}_{safe_title}.txt"
    file_path = os.path.join(save_dir, filename)

    # 检查是否存在且不为空
    if os.path.exists(file_path):
        if os.path.getsize(file_path) > 0:
            pbar.update(1)
            return

    async with SEMAPHORE:
        # 🟢 关键修改：增加重试循环，最多重试 5 次
        max_retries = 5
        for attempt in range(max_retries):
            try:
                # 随机延迟
                await asyncio.sleep(random.uniform(2, 5))

                r = await session.get(chapter_url, headers=PUBLIC_HEADERS, proxy=PROXY_URL, timeout=60)

                if r.status_code == 200:
                    content_size = len(r.content)
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

                        pbar.set_postfix_str(f"OK: {serial_num:05d}")
                        pbar.update(1)
                        return  # 🟢 成功后直接返回，结束函数

                    else:
                        pbar.write(f"⚠️ 跳过(无正文): {chapter_title}")
                        pbar.update(1)
                        return  # 无正文也视为处理完成

                elif r.status_code == 429:
                    wait_time = 30 + (attempt * 10)  # 每次重试多等一会
                    pbar.write(f"⛔ 429 限流: {chapter_title} (第{attempt + 1}次重试，暂停{wait_time}秒...)")
                    await asyncio.sleep(wait_time)
                    continue  # 🟢 关键：继续下一次循环重试，而不是退出

                else:
                    pbar.write(f"❌ 失败 [{r.status_code}]: {chapter_title}")
                    # 其他错误也重试一下吧，万一是网络波动
                    continue

            except Exception as e:
                pbar.write(f"❌ 异常 {chapter_title}: {e}")
                await asyncio.sleep(5)
                continue  # 异常也重试

        # 如果 5 次都失败了
        pbar.write(f"💀 彻底失败(放弃): {chapter_title}")
        pbar.update(1)


def post_process_files(temp_chapter_dir, book_title):
    print(f"\n✅ [{book_title}] 下载完成！开始合并...")

    merged_file_path = os.path.join(BASE_DOWNLOAD_DIR, f"{book_title}_全本by69书吧.txt")
    zip_file_path = os.path.join(BASE_DOWNLOAD_DIR, f"{book_title}_分章包.zip")

    all_files = [f for f in os.listdir(temp_chapter_dir) if f.endswith(".txt")]
    all_files.sort()  # 按文件名排序(00001...)

    if not all_files:
        print("⚠️ 目录下没有文件，跳过合并。")
        return

    files_to_clean = []

    # --- 合并 ---
    with open(merged_file_path, 'w', encoding='utf-8') as outfile:
        for filename in all_files:
            file_path = os.path.join(temp_chapter_dir, filename)
            chapter_title_in_txt = filename.split('_', 1)[1].replace('.txt', '')

            if os.path.exists(file_path):
                with open(file_path, 'r', encoding='utf-8') as infile:
                    content = infile.read()
                    outfile.write(chapter_title_in_txt + "\n\n")
                    outfile.write(content)
                    outfile.write("\n\n\n")
                    files_to_clean.append(file_path)

    # --- 打包 ---
    print(f"正在压缩: {os.path.basename(zip_file_path)} ...")
    with zipfile.ZipFile(zip_file_path, 'w', zipfile.ZIP_DEFLATED) as zf:
        for file_path in files_to_clean:
            file_name = os.path.basename(file_path)
            zf.write(file_path, arcname=file_name)

    # --- 清理 ---
    try:
        if os.path.exists(temp_chapter_dir):
            shutil.rmtree(temp_chapter_dir)
            print(f"🗑️ 已删除临时文件夹")
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

            # 检查跳过 (如果全本txt已存在，说明已经下完了)
            final_txt_path = os.path.join(BASE_DOWNLOAD_DIR, f"{safe_book_title}_全本by69书吧.txt")
            if os.path.exists(final_txt_path):
                print(f"⏭️  跳过已完成: 《{safe_book_title}》")
                return

            temp_chapter_dir = os.path.join(BASE_DOWNLOAD_DIR, safe_book_title)
            if not os.path.exists(temp_chapter_dir):
                os.makedirs(temp_chapter_dir)

            chapter_list = soup.select('.catalog li a')
            if not chapter_list:
                chapter_list = soup.select('#catalog li a')

            # 🟢 智能检测倒序并修正
            if chapter_list:
                first_text = chapter_list[0].text
                last_text = chapter_list[-1].text
                is_reversed = False

                if "第1章" in last_text or "第一章" in last_text:
                    is_reversed = True
                try:
                    first_num = int(re.search(r'(\d+)', first_text).group(1))
                    last_num = int(re.search(r'(\d+)', last_text).group(1))
                    if first_num > last_num:
                        is_reversed = True
                except:
                    pass

                if is_reversed:
                    print(f"🔄 修正倒序列表...")
                    chapter_list.reverse()

            print(f"📚 书名: 《{safe_book_title}》")
            print(f"📊 章节数: {len(chapter_list)} 章")

            tasks = []
            with tqdm(total=len(chapter_list), unit="章", desc="下载中", ncols=100, mininterval=0.5) as pbar:
                for idx, link in enumerate(chapter_list):
                    href = link.get('href')
                    c_title = link.text.strip()
                    if href and href != "#":
                        tasks.append(download_chapter(session, href, c_title, temp_chapter_dir, pbar, idx + 1))

                # 倒序执行任务防封
                tasks.reverse()
                await asyncio.gather(*tasks)

            post_process_files(temp_chapter_dir, safe_book_title)

        except Exception as e:
            print(f"❌ 运行错误 (ID: {book_num}): {e}")
            import traceback
            traceback.print_exc()


async def main():
    if not os.path.exists(BASE_DOWNLOAD_DIR):
        os.makedirs(BASE_DOWNLOAD_DIR)

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