# 复制此文件为 config.py 并填写你的配置（config.py 不会被提交到 Git）

COOKIE = ""
PROXY_URL = "http://127.0.0.1:7890"  # 留空表示不使用代理
BASE_DOWNLOAD_DIR = "download"
SEMAPHORE_COUNT = 1

# 也可通过环境变量配置（GitHub Actions 使用 Secrets 注入）：
# SHUBA_COOKIE / SHUBA_PROXY / SHUBA_BOOK_IDS / SHUBA_SEMAPHORE
