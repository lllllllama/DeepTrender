<div align="center">

# 🔬 DeepTrender

**AI 论文关键词追踪 & 趋势分析平台**

[![Python](https://img.shields.io/badge/Python-3.11%2B-3776AB?logo=python&logoColor=white)](https://www.python.org/)
[![Flask](https://img.shields.io/badge/Flask-3.0%2B-000000?logo=flask&logoColor=white)](https://flask.palletsprojects.com/)
[![SQLite](https://img.shields.io/badge/SQLite-database-003B57?logo=sqlite&logoColor=white)](https://www.sqlite.org/)
[![MCP](https://img.shields.io/badge/MCP-server-6B4FBB?logo=anthropic&logoColor=white)](https://modelcontextprotocol.io/)
[![GitHub Actions](https://img.shields.io/badge/GitHub_Actions-CI%2FCD-2088FF?logo=githubactions&logoColor=white)](https://github.com/features/actions)
[![GitHub Pages](https://img.shields.io/badge/GitHub_Pages-static_site-222222?logo=github&logoColor=white)](https://pages.github.com/)
[![License](https://img.shields.io/badge/License-MIT-green.svg)](LICENSE)
[![Tests](https://img.shields.io/badge/Tests-53%2B_passing-brightgreen?logo=pytest&logoColor=white)](tests/)

[中文](#-中文说明) · [English](#-english)

</div>

---

## 🇨🇳 中文说明

DeepTrender 是一个面向 AI/ML 论文的**关键词追踪与趋势分析**平台，覆盖多源数据采集、结构化存储、关键词提取、趋势分析、Flask REST API、MCP 服务器，以及面向 GitHub Pages 的静态站点导出。

### ✨ 核心功能

| 功能 | 说明 |
|------|------|
| 📥 多源采集 | `arxiv`、`openreview`、`openalex`、`s2` |
| 🔑 关键词提取 | `YAKE`（快速）、`KeyBERT`（语义）、`both`（两者合并） |
| 🗄️ 数据存储 | SQLite 三层架构（raw / structured / analysis） |
| 📊 趋势分析 | 年 / 月 / 周 / 日 多粒度时间序列 + 新兴话题检测 |
| 🌐 Web 服务 | Flask REST API + 静态前端（ECharts 可视化） |
| 🤖 MCP 服务器 | 14 个工具，供 AI Agent 直接查询统计数据 |
| 📄 静态导出 | 输出到 `docs/`，无需后端即可在 GitHub Pages 访问 |
| ⚙️ 自动更新 | GitHub Actions 定时抓取并自动部署 |

### 🏗️ 项目结构

```text
deeptrender/
├── src/
│   ├── agents/          # 采集、结构化、分析 Agent
│   ├── analysis/        # arXiv 趋势分析、统计模块
│   ├── database/        # SQLite 仓库（三层架构）
│   ├── extractor/       # YAKE / KeyBERT 关键词提取
│   ├── scraper/         # arXiv / OpenReview / OpenAlex / S2 客户端
│   ├── tools/           # 静态站点导出、CCF 注册表导入
│   ├── visualization/   # 图表生成（matplotlib + ECharts）
│   ├── web/             # Flask 应用 & 静态前端
│   ├── mcp_server.py    # MCP 服务器（14 个工具）
│   └── main.py          # 主流程入口
├── tests/               # 单元测试 & 集成测试
├── docs/                # 静态站点（GitHub Pages）
├── data/                # SQLite 数据库
├── output/              # 图表 & 报告
└── .github/workflows/   # GitHub Actions 工作流
```

### 📋 环境要求

- 🐍 Python 3.11+
- 虚拟环境（推荐）
- `KeyBERT` 首次运行会自动下载 `all-MiniLM-L6-v2` 模型（约 80 MB）

### 🚀 快速开始

**1. 安装依赖**

```bash
pip install -r requirements.txt
```

**2. 运行主流程**

```bash
# 默认：采集 arxiv + openalex，提取关键词，生成报告
python src/main.py
```

**3. 启动 Web 界面**

```bash
python src/web/app.py
# 访问 http://localhost:5000
```

**4. 启动 MCP 服务器（供 AI Agent 调用）**

```bash
# stdio 模式（Claude Desktop / 标准 MCP SDK）
python src/mcp_server.py

# HTTP 模式
python src/mcp_server.py --transport streamable-http --port 8090
```

### ⚙️ 常用命令

<details>
<summary>📥 按数据源采集</summary>

```bash
# 采集近 7 天 arXiv 论文
python src/main.py --source arxiv --arxiv-days 7

# 采集 OpenReview 会议数据
python src/main.py --source openreview --venue ICLR NeurIPS --year 2024

# 采集 OpenAlex 数据
python src/main.py --source openalex --venue ICLR NeurIPS --year 2024

# 采集 Semantic Scholar 数据
python src/main.py --source s2 --venue CVPR ACL --year 2024
```

</details>

<details>
<summary>🔑 控制关键词提取器</summary>

```bash
python src/main.py --extractor yake      # 快速，基于统计
python src/main.py --extractor keybert   # 语义，基于 BERT
python src/main.py --extractor both      # 两者合并（最准确，较慢）
```

</details>

<details>
<summary>🔧 跳过阶段 / 限制规模</summary>

```bash
python src/main.py --skip-ingestion      # 跳过数据采集
python src/main.py --skip-structuring   # 跳过结构化处理
python src/main.py --limit 100          # 限制处理量（测试用）
```

</details>

### 🌐 REST API

启动服务后，可访问以下端点：

| 端点 | 说明 |
|------|------|
| `GET /api/health` | 健康检查 |
| `GET /api/status` | 数据库状态与统计 |
| `GET /api/stats/overview` | 总体概览 |
| `GET /api/stats/venues` | 所有会议列表 |
| `GET /api/stats/venue/<venue>` | 单个会议详情 |
| `GET /api/keywords/top` | Top-N 关键词 |
| `GET /api/keywords/trends` | 关键词趋势时间序列 |
| `GET /api/keywords/comparison` | 跨会议关键词对比 |
| `GET /api/keywords/emerging` | 新兴关键词检测 |
| `GET /api/arxiv/timeseries` | arXiv 多粒度时间序列 |
| `GET /api/arxiv/emerging` | arXiv 新兴话题 |
| `POST /api/refresh` | 刷新数据缓存 |

> 完整 API 文档见 [docs/API_CONTRACT.md](docs/API_CONTRACT.md)

### 🤖 MCP 服务器

DeepTrender 内置 MCP 服务器，AI Agent 可直接查询所有统计数据与中间数据，无需手动解析 API。

**Claude Desktop 配置：**

```json
{
  "mcpServers": {
    "deeptrender": {
      "command": "python",
      "args": ["src/mcp_server.py"],
      "cwd": "/path/to/deeptrender"
    }
  }
}
```

**提供的 14 个工具：**

| 分类 | 工具 |
|------|------|
| 📊 概览 | `get_overview`、`get_status` |
| 🏛️ 会议统计 | `list_venues`、`get_venue_detail`、`get_venue_comparison` |
| 🔑 关键词 | `get_top_keywords`、`get_keyword_trends`、`get_emerging_keywords`、`get_keyword_wordcloud` |
| 📈 arXiv 专项 | `get_arxiv_timeseries`、`get_arxiv_stats`、`get_arxiv_emerging` |
| 🗄️ 中间数据 | `get_analysis_meta`、`get_venue_summaries`、`get_keyword_trend_cached`、`get_raw_paper_count`、`get_scrape_log`、`list_configured_venues` |

### 📄 静态站点导出

```bash
# 导出到 docs/（GitHub Pages 根目录）
python src/tools/export_static_site.py

# 自定义参数
python src/tools/export_static_site.py --output-dir dist --top-keywords 100
```

导出后，可用任意静态服务器预览：

```bash
python -m http.server -d docs 8000
# 访问 http://localhost:8000
```

### 🧪 测试

```bash
# 运行全部测试
pytest -q

# 运行核心模块测试
pytest tests/test_database.py tests/test_web_api.py

# 运行 MCP 服务器测试
pytest tests/test_mcp_server.py -v

# 生成覆盖率报告
pytest --cov=src --cov-report=html
```

### ⚙️ GitHub Actions 自动更新

工作流每周日 UTC 00:00 自动运行，也可手动触发并指定参数：

| 参数 | 说明 | 默认值 |
|------|------|--------|
| `source` | 数据源 | `all` |
| `arxiv_days` | arXiv 采集天数 | `7` |
| `venues` | 指定会议（逗号分隔） | 全部 |
| `years` | 指定年份（逗号分隔） | 全部 |
| `ccf_tier` | CCF 等级过滤 (A/B/C/all) | `all` |
| `export_only` | 仅导出静态站点 | `false` |

运行完成后自动 commit `data/`、`output/`、`docs/` 并更新 GitHub Pages。

### 📁 数据与输出

| 路径 | 说明 |
|------|------|
| `data/keywords.db` | SQLite 主数据库 |
| `output/figures/` | 生成的可视化图表（PNG） |
| `output/reports/` | 生成的 Markdown 分析报告 |
| `docs/` | 静态站点（GitHub Pages） |
| `docs/data/` | 前端所需 JSON 数据文件 |

---

## 🇬🇧 English

DeepTrender is an **AI/ML paper keyword tracking & trend analysis** platform. It ingests papers from multiple sources, extracts keywords, runs multi-granularity trend analysis, serves a Flask REST API, exposes an MCP server for AI agents, and exports a static site for GitHub Pages.

### ✨ Highlights

| Feature | Details |
|---------|---------|
| 📥 Multi-source ingestion | `arxiv`, `openreview`, `openalex`, `s2` |
| 🔑 Keyword extraction | `YAKE` (fast), `KeyBERT` (semantic), `both` |
| 🗄️ Storage | SQLite with 3-layer architecture (raw / structured / analysis) |
| 📊 Trend analysis | Year / month / week / day timeseries + emerging topic detection |
| 🌐 Web service | Flask REST API + static frontend (ECharts) |
| 🤖 MCP server | 14 tools for AI agents to query stats directly |
| 📄 Static export | Outputs to `docs/` for GitHub Pages (no backend needed) |
| ⚙️ Auto-update | GitHub Actions scheduled pipeline with auto-deploy |

### 📋 Requirements

- 🐍 Python 3.11+
- Virtual environment recommended
- `KeyBERT` downloads `all-MiniLM-L6-v2` (~80 MB) on first run

### 🚀 Quick Start

```bash
# Install
pip install -r requirements.txt

# Run the full pipeline
python src/main.py

# Start the web UI  →  http://localhost:5000
python src/web/app.py

# Start the MCP server (stdio, for AI agents)
python src/mcp_server.py

# Export static site  →  docs/
python src/tools/export_static_site.py

# Run tests
pytest -q
```

### 🤖 MCP Server

Add to your Claude Desktop config (`claude_desktop_config.json`):

```json
{
  "mcpServers": {
    "deeptrender": {
      "command": "python",
      "args": ["src/mcp_server.py"],
      "cwd": "/path/to/deeptrender"
    }
  }
}
```

For HTTP transport (remote agents):

```bash
python src/mcp_server.py --transport streamable-http --port 8090
```

### 🌐 REST API (selected endpoints)

| Endpoint | Description |
|----------|-------------|
| `GET /api/stats/overview` | Total papers, keywords, venues |
| `GET /api/keywords/top` | Top-N keywords (filter by venue/year) |
| `GET /api/keywords/trends` | Yearly trend series for keywords |
| `GET /api/keywords/emerging` | Fast-growing keyword detection |
| `GET /api/arxiv/timeseries` | arXiv paper counts by bucket |
| `GET /api/arxiv/emerging` | Emerging topics in arXiv data |

> Full documentation in [docs/API_CONTRACT.md](docs/API_CONTRACT.md) and [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md).

### 🧪 Tests

```bash
pytest -q                          # all tests
pytest tests/test_mcp_server.py   # MCP server (53 tests)
pytest --cov=src                  # with coverage
```

---

<div align="center">

Made with ❤️ for the AI research community

[![Star on GitHub](https://img.shields.io/github/stars/lllllllama/deeptrender?style=social)](https://github.com/lllllllama/deeptrender)

</div>
