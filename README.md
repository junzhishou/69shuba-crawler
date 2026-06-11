# 69shuba-crawler

69书吧（[69shuba.com](https://www.69shuba.com/)）小说异步爬虫工具，支持 **GitHub Actions 云端下载**、本地批量下载、章节合并与 ZIP 打包。

## 功能特性

- 支持 **GitHub Actions** 手动触发下载，结果以 Artifact 形式下载
- 基于 `curl_cffi` + `asyncio` 异步下载，模拟 Chrome 浏览器指纹
- 自动检测 GBK / UTF-8 编码
- 智能章节倒序修正、断点续传、429 限流重试
- 下载完成后自动合并全本 TXT 并打包分章 ZIP
- 支持代理访问（国内本地环境通常需要翻墙，云端 Runner 通常可直连）

## 项目结构

```
69shuba-crawler/
├── .github/
│   └── workflows/
│       └── download.yml        # GitHub Actions 云端下载工作流
├── crawler.py                  # 主程序：批量下载多本书
├── crawler_interactive.py      # 交互式：输入单本书 ID 下载
├── merge_chapters.py           # 工具：合并已下载的分章文件夹
├── settings.py                 # 全局配置加载
├── config.example.py           # 配置模板（复制为 config.py）
├── requirements.txt
├── legacy/                     # 历史版本与实验代码
└── download/                   # 下载输出目录（已 gitignore）
```

## 快速开始：GitHub Actions 云端下载

> 推荐方式。无需本地运行，在 GitHub 云端完成下载后从 Artifacts 取回文件。

### 1. 配置 Secrets

进入仓库 **Settings → Secrets and variables → Actions → New repository secret**，添加：

| Secret 名称 | 是否必填 | 说明 |
|-------------|----------|------|
| `SHUBA_COOKIE` | ✅ 必填 | 69书吧 的 Cookie |
| `SHUBA_PROXY` | 选填 | 远程代理地址；海外 Runner 通常可留空 |

Cookie 获取：浏览器登录 69书吧 → 开发者工具 Network → 复制请求头中的 `Cookie`。

### 2. 手动触发工作流

1. 打开仓库 **Actions** 页
2. 左侧选择 **Download Novels**
3. 点击 **Run workflow**
4. 填写参数：
   - `book_ids`：书籍 ID，逗号分隔，如 `88724` 或 `88724,74678`
   - `semaphore`：并发数，建议 `1`（默认）
5. 等待运行完成
6. 进入该次 Run 详情页，在底部 **Artifacts** 区域下载 `novels-*` 压缩包

书籍 ID 从 URL 获取，例如 `https://www.69shuba.com/book/88724/` 中的 `88724`。

### 3. 注意事项

- 单本书章节较多时耗时较长（每章约 2~5 秒防封延迟）
- 工作流最长运行 **6 小时**
- 建议先用单本、章节较少的书测试
- 若出现 403 或无法访问，在 Secrets 中补充 `SHUBA_PROXY`

---

## 本地运行

### 环境要求

- Python 3.9+
- 可访问 69书吧 的网络环境（国内通常需要代理）

### 安装

```bash
pip install -r requirements.txt
```

### 配置

**方式一：配置文件（推荐）**

```bash
cp config.example.py config.py
```

编辑 `config.py`：

```python
COOKIE = "你的 Cookie"
PROXY_URL = "http://127.0.0.1:7890"  # 留空表示不使用代理
SEMAPHORE_COUNT = 1
```

**方式二：环境变量**

| 变量名 | 说明 | 示例 |
|--------|------|------|
| `SHUBA_COOKIE` | 69书吧 Cookie | `zh_choose=s; ...` |
| `SHUBA_PROXY` | 代理地址，留空则直连 | `http://127.0.0.1:7890` |
| `SHUBA_BOOK_IDS` | 书籍 ID，逗号分隔 | `88724,74678` |
| `SHUBA_SEMAPHORE` | 并发数 | `1` |
| `SHUBA_DOWNLOAD_DIR` | 下载目录 | `download` |

```bash
set SHUBA_COOKIE=你的Cookie
set SHUBA_PROXY=http://127.0.0.1:7890
set SHUBA_BOOK_IDS=88724,74678
python crawler.py
```

### 批量下载

```bash
# 通过环境变量指定书籍
set SHUBA_BOOK_IDS=88724
python crawler.py

# 或编辑 crawler.py 中的 BOOKS_TO_DOWNLOAD 列表后运行
python crawler.py
```

### 单本交互下载

```bash
python crawler_interactive.py
```

### 合并已下载章节

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

- 请合理控制并发数（建议 1~3），避免被限流
- 本项目仅供学习交流，请尊重版权，勿用于商业用途
- 请勿将 `config.py` 或 Cookie 提交到公开仓库

## License

MIT
