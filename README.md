# 69shuba-crawler

69书吧（[69shuba.com](https://www.69shuba.com/)）小说异步爬虫工具，支持批量下载、章节合并与 ZIP 打包。

## 功能特性

- 基于 `curl_cffi` + `asyncio` 的异步下载，模拟 Chrome 浏览器指纹
- 自动检测 GBK / UTF-8 编码
- 智能章节倒序修正、断点续传、429 限流重试
- 下载完成后自动合并全本 TXT 并打包分章 ZIP
- 支持代理访问（国内环境通常需要翻墙）

## 项目结构

```
69shuba-crawler/
├── crawler.py                  # 主程序：批量下载多本书
├── crawler_interactive.py      # 交互式：输入单本书 ID 下载
├── merge_chapters.py           # 工具：合并已下载的分章文件夹
├── settings.py                 # 全局配置加载
├── config.example.py           # 配置模板（复制为 config.py）
├── requirements.txt
├── legacy/                     # 历史版本与实验代码
│   ├── crawler_v1.py
│   ├── crawler_v2.py
│   ├── crawler_interactive_legacy.py
│   ├── merge_generic.py
│   └── experiments/
└── download/                   # 下载输出目录（已 gitignore）
```

## 环境要求

- Python 3.9+
- 可访问 69书吧 的网络环境（通常需要代理）

## 安装

```bash
pip install -r requirements.txt
```

## 配置

**方式一：配置文件（推荐）**

```bash
cp config.example.py config.py
```

编辑 `config.py`，填写 Cookie 和代理地址：

```python
COOKIE = "你的 Cookie"
PROXY_URL = "http://127.0.0.1:7890"
```

**方式二：环境变量**

```bash
set SHUBA_COOKIE=你的Cookie
set SHUBA_PROXY=http://127.0.0.1:7890
```

> Cookie 获取方式：浏览器登录 69书吧 后，在开发者工具 Network 面板复制请求头中的 Cookie。

## 使用方法

### 批量下载

1. 编辑 `crawler.py` 中的 `BOOKS_TO_DOWNLOAD` 列表，填入书籍 ID
2. 书籍 ID 可从 URL 获取，例如 `https://www.69shuba.com/book/88724/` 中的 `88724`
3. 运行：

```bash
python crawler.py
```

### 单本交互下载

```bash
python crawler_interactive.py
```

按提示输入书籍 ID 即可。

### 合并已下载章节

如果已有分章文件夹需要手动合并：

```bash
python merge_chapters.py
```

## 输出文件

下载完成后，`download/` 目录下会生成：

| 文件 | 说明 |
|------|------|
| `{书名}_全本by69书吧.txt` | 合并后的全本小说 |
| `{书名}_分章包.zip` | 分章 TXT 压缩备份 |

## 注意事项

- 请合理控制并发数（`SEMAPHORE_COUNT` 建议 1~3），避免被限流
- 本项目仅供学习交流，请尊重版权，勿用于商业用途
- 请勿将 `config.py` 提交到公开仓库

## License

MIT
