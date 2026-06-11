"""项目全局配置，优先读取 config.py，否则使用环境变量。"""

import os

try:
    from config import COOKIE, PROXY_URL, BASE_DOWNLOAD_DIR, SEMAPHORE_COUNT
except ImportError:
    COOKIE = os.environ.get("SHUBA_COOKIE", "")
    PROXY_URL = os.environ.get("SHUBA_PROXY", "http://127.0.0.1:7890")
    BASE_DOWNLOAD_DIR = os.environ.get("SHUBA_DOWNLOAD_DIR", "download")
    SEMAPHORE_COUNT = int(os.environ.get("SHUBA_SEMAPHORE", "1"))

# CI 环境（如 GitHub Actions）通常不需要本地代理，留空即可直连
if os.environ.get("CI") == "true" and not os.environ.get("SHUBA_PROXY"):
    PROXY_URL = ""

PUBLIC_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/143.0.0.0 Safari/537.36"
    ),
    "Cookie": COOKIE,
    "Referer": "https://www.69shuba.com/",
}


def get_proxy_kwargs():
    """返回请求代理参数，未配置代理时返回空字典。"""
    if PROXY_URL:
        return {"proxy": PROXY_URL}
    return {}


def parse_book_ids(raw_ids: str) -> list[str]:
    """解析逗号、分号或空格分隔的书籍 ID。"""
    if not raw_ids:
        return []
    return [
        book_id.strip()
        for part in raw_ids.replace(";", ",").split(",")
        for book_id in part.split()
        if book_id.strip().isdigit()
    ]
