"""项目全局配置，优先读取 config.py，否则使用环境变量。"""

import os

try:
    from config import COOKIE, PROXY_URL, BASE_DOWNLOAD_DIR, SEMAPHORE_COUNT
except ImportError:
    COOKIE = os.environ.get("SHUBA_COOKIE", "")
    PROXY_URL = os.environ.get("SHUBA_PROXY", "http://127.0.0.1:7890")
    BASE_DOWNLOAD_DIR = os.environ.get("SHUBA_DOWNLOAD_DIR", "download")
    SEMAPHORE_COUNT = int(os.environ.get("SHUBA_SEMAPHORE", "1"))

PUBLIC_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/143.0.0.0 Safari/537.36"
    ),
    "Cookie": COOKIE,
    "Referer": "https://www.69shuba.com/",
}
