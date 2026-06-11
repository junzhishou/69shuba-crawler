import os
import re
import zipfile
import shutil


def sort_key(s):
    """
    实现自然排序算法，将文件名中的数字按数值大小排序，而不是按字符顺序。
    例如：确保 '10.txt' 排在 '2.txt' 后面。
    """
    return [int(text) if text.isdigit() else text.lower()
            for text in re.split(r'(\d+)', s)]


def merge_and_backup_files():
    # --- 配置区域 ---
    # 目标文件夹路径
    target_dir = r"C:\Users\hongch\Desktop\桌面文件\live\小说\3改\4\娱乐春秋番外&同人\番外"

    # 合并后的文件名
    merged_filename = "全本.txt"

    # 备份压缩包的文件名
    backup_zip_name = "原始章节备份.zip"
    # ----------------

    # 检查路径是否存在
    if not os.path.exists(target_dir):
        print(f"错误：找不到路径 {target_dir}")
        return

    # 获取所有txt文件 (排除掉可能已经存在的合并文件)
    files = [f for f in os.listdir(target_dir)
             if f.endswith('.txt') and f != merged_filename]

    if not files:
        print("未在指定目录下找到任何 .txt 文件。")
        return

    # 按自然顺序排序文件名
    files.sort(key=sort_key)
    print(f"共找到 {len(files)} 个文件，准备合并...")

    output_path = os.path.join(target_dir, merged_filename)
    backup_path = os.path.join(target_dir, backup_zip_name)

    # 1. 执行合并
    try:
        with open(output_path, 'w', encoding='utf-8') as outfile:
            for filename in files:
                file_path = os.path.join(target_dir, filename)

                # 提取文件名作为章节名（去除后缀）
                chapter_title = os.path.splitext(filename)[0]

                # 写入章节名
                outfile.write(f"{chapter_title}\n\n")

                # 读取内容（尝试多种编码以防乱码）
                content = ""
                try:
                    with open(file_path, 'r', encoding='utf-8') as infile:
                        content = infile.read()
                except UnicodeDecodeError:
                    # 如果UTF-8失败，尝试GBK/GB18030（常见于中文Windows）
                    with open(file_path, 'r', encoding='gb18030') as infile:
                        content = infile.read()

                # 写入内容
                outfile.write(content)

                # 写入章节分隔符（两个空行 = 3个换行符）
                outfile.write("\n\n\n")

        print(f"合并完成！已生成文件：{output_path}")

    except Exception as e:
        print(f"合并过程中发生错误：{e}")
        return

    # 2. 打包备份
    try:
        print("正在打包备份原文件...")
        with zipfile.ZipFile(backup_path, 'w', zipfile.ZIP_DEFLATED) as zipf:
            for filename in files:
                file_path = os.path.join(target_dir, filename)
                zipf.write(file_path, arcname=filename)
        print(f"备份完成！已生成压缩包：{backup_path}")

    except Exception as e:
        print(f"打包备份失败，将取消删除操作。错误：{e}")
        return

    # 3. 删除原文件 (仅在备份成功后执行)
    print("正在清理零散文件...")
    deleted_count = 0
    for filename in files:
        file_path = os.path.join(target_dir, filename)
        try:
            os.remove(file_path)
            deleted_count += 1
        except Exception as e:
            print(f"无法删除文件 {filename}: {e}")

    print(f"处理完毕！清理了 {deleted_count} 个文件。")


if __name__ == "__main__":
    merge_and_backup_files()