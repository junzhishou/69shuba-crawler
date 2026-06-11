"""将 download/ 目录下已下载的分章文件夹合并为全本 TXT。"""

import os
import re
import zipfile
import shutil

from settings import BASE_DOWNLOAD_DIR


def extract_number(filename):
    """从文件名中提取第一个数字，用于章节排序。"""
    match = re.search(r'(\d+)', filename)
    return int(match.group(1)) if match else 0


def process_existing_folder(book_folder_name):
    if os.path.isabs(book_folder_name):
        folder_path = book_folder_name
        book_title = os.path.basename(folder_path)
    else:
        folder_path = os.path.join(BASE_DOWNLOAD_DIR, book_folder_name)
        book_title = book_folder_name

    if not os.path.exists(folder_path):
        print(f"❌ 找不到文件夹: {folder_path}")
        return

    print(f"📂 正在处理: {book_title}")

    files = [f for f in os.listdir(folder_path) if f.endswith(".txt")]
    if not files:
        print("⚠️ 文件夹里没有 TXT 文件。")
        return

    print(f"📊 找到 {len(files)} 个文件，正在智能排序...")
    files.sort(key=extract_number)

    parent_dir = os.path.dirname(folder_path)
    merged_file = os.path.join(parent_dir, f"{book_title}_全本by69书吧.txt")
    zip_file = os.path.join(parent_dir, f"{book_title}_分章备份.zip")

    print(f"✍️ 正在合并到: {os.path.basename(merged_file)} ...")
    with open(merged_file, 'w', encoding='utf-8') as outfile:
        for filename in files:
            file_path = os.path.join(folder_path, filename)
            chapter_title = filename.replace('.txt', '')
            clean_title = re.sub(r'^\d+_', '', chapter_title)

            try:
                with open(file_path, 'r', encoding='utf-8') as infile:
                    content = infile.read()
                    outfile.write(clean_title + "\n\n")
                    outfile.write(content)
                    outfile.write("\n\n\n")
            except Exception as e:
                print(f"  读取出错 {filename}: {e}")

    print(f"📦 正在压缩备份: {os.path.basename(zip_file)} ...")
    with zipfile.ZipFile(zip_file, 'w', zipfile.ZIP_DEFLATED) as zf:
        for filename in files:
            zf.write(os.path.join(folder_path, filename), arcname=filename)

    print("🗑️ 正在清理零散文件...")
    try:
        shutil.rmtree(folder_path)
        print(f"✅ 已删除源文件夹: {folder_path}")
    except Exception as e:
        print(f"❌ 删除文件夹失败: {e}")

    print("\n🎉 处理完成！")
    print(f"📘 全本: {merged_file}")
    print(f"🗂️ 备份: {zip_file}")


if __name__ == "__main__":
    if not os.path.exists(BASE_DOWNLOAD_DIR):
        print(f"没找到 {BASE_DOWNLOAD_DIR} 目录，请先运行爬虫下载章节。")
        exit()

    subfolders = [
        f for f in os.listdir(BASE_DOWNLOAD_DIR)
        if os.path.isdir(os.path.join(BASE_DOWNLOAD_DIR, f))
    ]

    if not subfolders:
        print(f"在 {BASE_DOWNLOAD_DIR} 下没有找到任何书籍文件夹。")
        exit()

    print("发现以下书籍文件夹：")
    for i, name in enumerate(subfolders):
        print(f"{i + 1}. {name}")

    choice = input("\n请输入序号(输入 all 处理全部): ").strip()

    if choice.lower() == 'all':
        for name in subfolders:
            process_existing_folder(name)
    elif choice.isdigit():
        idx = int(choice) - 1
        if 0 <= idx < len(subfolders):
            process_existing_folder(subfolders[idx])
        else:
            print("序号无效")
    else:
        process_existing_folder(choice)
