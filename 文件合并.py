import os
import re
import zipfile
import shutil

# --- 配置区域 ---
# 你的下载目录（即包含那一堆txt文件夹的父目录）
BASE_DIR = "download"


# ----------------

def extract_number(filename):
    """
    智能排序核心：从文件名中提取第一个数字。
    例如：
    "第1章.txt" -> 1
    "第10章.txt" -> 10
    "00005_第5章.txt" -> 5
    """
    # 匹配文件名里的数字
    match = re.search(r'(\d+)', filename)
    if match:
        return int(match.group(1))
    return 0


def process_existing_folder(book_folder_name):
    # 1. 确定路径
    # 假设你的书在 download/都重生了谁考公务员啊/ 里面
    # 也可以兼容直接输入完整路径的情况
    if os.path.isabs(book_folder_name):
        folder_path = book_folder_name
        book_title = os.path.basename(folder_path)
    else:
        folder_path = os.path.join(BASE_DIR, book_folder_name)
        book_title = book_folder_name

    if not os.path.exists(folder_path):
        print(f"❌ 找不到文件夹: {folder_path}")
        return

    print(f"📂 正在处理: {book_title}")

    # 2. 获取所有txt文件
    files = [f for f in os.listdir(folder_path) if f.endswith(".txt")]
    if not files:
        print("⚠️ 文件夹里没有TXT文件。")
        return

    print(f"📊 找到 {len(files)} 个文件，正在智能排序...")

    # 3. 智能排序 (关键步骤)
    # 使用 extract_number 函数作为 key，确保 2 排在 10 前面
    files.sort(key=extract_number)

    # 4. 准备输出文件路径
    # 输出到 download/ 同级目录，而不是文件夹里面
    parent_dir = os.path.dirname(folder_path)
    merged_file = os.path.join(parent_dir, f"{book_title}_全本by69书吧.txt")
    zip_file = os.path.join(parent_dir, f"{book_title}_分章备份.zip")

    # 5. 开始合并
    print(f"✍️ 正在合并到: {os.path.basename(merged_file)} ...")
    with open(merged_file, 'w', encoding='utf-8') as outfile:
        for filename in files:
            file_path = os.path.join(folder_path, filename)
            # 获取去除后缀的标题
            chapter_title = filename.replace('.txt', '')

            # 尝试去除文件名前面的 "00001_" 这种序号（如果有的话），让标题更干净
            # 如果文件名是 "001_第1章"，这里会处理成 "第1章"
            clean_title = re.sub(r'^\d+_', '', chapter_title)

            try:
                with open(file_path, 'r', encoding='utf-8') as infile:
                    content = infile.read()
                    outfile.write(clean_title + "\n\n")
                    outfile.write(content)
                    outfile.write("\n\n\n")
            except Exception as e:
                print(f"  读取出错 {filename}: {e}")

    # 6. 打包 ZIP
    print(f"📦 正在压缩备份: {os.path.basename(zip_file)} ...")
    with zipfile.ZipFile(zip_file, 'w', zipfile.ZIP_DEFLATED) as zf:
        for filename in files:
            file_path = os.path.join(folder_path, filename)
            zf.write(file_path, arcname=filename)

    # 7. 删除源文件夹
    print(f"🗑️ 正在清理零散文件...")
    try:
        shutil.rmtree(folder_path)
        print(f"✅ 已删除源文件夹: {folder_path}")
    except Exception as e:
        print(f"❌ 删除文件夹失败: {e}")

    print("\n🎉 处理完成！")
    print(f"📘 全本: {merged_file}")
    print(f"🗂️ 备份: {zip_file}")


if __name__ == "__main__":
    # 列出 download 目录下所有的文件夹供选择
    if os.path.exists(BASE_DIR):
        subfolders = [f for f in os.listdir(BASE_DIR) if os.path.isdir(os.path.join(BASE_DIR, f))]

        if not subfolders:
            print(f"在 {BASE_DIR} 下没有找到任何书籍文件夹。")
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
            # 也可以手动输入文件夹名字
            process_existing_folder(choice)
    else:
        print(f"没找到 {BASE_DIR} 目录，请修改脚本中的 BASE_DIR 配置。")