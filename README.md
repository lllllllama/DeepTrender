# DeepTrender

DeepTrender is an AI/ML paper trend-tracking project. It crawls papers from arXiv, OpenReview, OpenAlex, and Semantic Scholar, stores them in SQLite, extracts keywords, builds trend statistics, serves a Flask API/MCP server, and exports a static site for GitHub Pages.

Live site: https://lllllllama.github.io/DeepTrender/

## What It Provides

| Area | Details |
| --- | --- |
| Data ingestion | arXiv, OpenReview, OpenAlex, Semantic Scholar |
| Storage | SQLite raw, structured, and analysis layers |
| Keyword extraction | YAKE by default, optional KeyBERT, or both |
| Trend analysis | year/month/week/day arXiv series, venue keyword trends, emerging keywords |
| Interfaces | Flask REST API, MCP server, static GitHub Pages frontend |
| Automation | GitHub Actions crawls, exports `docs/`, deploys GitHub Pages, and commits updated artifacts |

## GitHub Pages

The public dashboard is deployed from the static files in `docs/`:

```text
src/web/static/  ->  src/tools/export_static_site.py  ->  docs/  ->  GitHub Pages
```

Pages is static-only. It does not run Flask, React, Vite, or Node at runtime. The exported frontend reads JSON from `docs/data/` using relative paths such as `./data/venues/venues_index.json`.

Preview locally:

```bash
python src/tools/export_static_site.py --output-dir docs --top-keywords 300
python -m http.server 8000 -d docs
```

Then open http://localhost:8000.

## First Online Crawl Policy

The scheduled GitHub Actions workflow must not treat an empty or small database as a normal incremental update. On the first online crawl, it should bootstrap a broad dataset and target at least tens of thousands of structured papers.

Current workflow defaults:

| Setting | Bootstrap behavior |
| --- | --- |
| `crawl_mode` | `auto` |
| `full_crawl_target` | `20000` structured papers |
| arXiv window | at least `3650` days in full mode |
| arXiv cap | `50000` papers in full mode |
| processing cap | `50000` papers in full mode |
| sources | `all` by default |

When `crawl_mode=auto`, the workflow checks the current structured paper count in `data/keywords.db`. If it is below `full_crawl_target`, it runs:

```bash
python src/main.py --source all --full-crawl --arxiv-days 3650 --arxiv-max-results 50000 --limit 50000
```

After the database is above the target, `auto` mode returns to incremental updates. To force a full run manually, open GitHub Actions, choose `Update Keywords`, set `crawl_mode=full`, and run the workflow.

## Local Usage

Install dependencies:

```bash
pip install -r requirements.txt
```

Run a normal update:

```bash
python src/main.py --source arxiv --arxiv-days 7
```

Run a broad bootstrap locally:

```bash
python src/main.py --source all --full-crawl
```

Limit a test run:

```bash
python src/main.py --source arxiv --arxiv-days 7 --arxiv-max-results 200 --limit 200
```

Start the Flask app:

```bash
python src/web/app.py
```

Then open http://localhost:5000.

Start the MCP server:

```bash
python src/mcp_server.py
```

HTTP transport:

```bash
python src/mcp_server.py --transport streamable-http --port 8090
```

## GitHub Actions

Main workflows:

| Workflow | Purpose |
| --- | --- |
| `.github/workflows/update.yml` | Crawl/update data, export `docs/`, deploy GitHub Pages, commit artifacts |
| `.github/workflows/pytest.yml` | Python test suite |
| `.github/workflows/test.yml` | broader CI pipeline and smoke checks |

Useful `Update Keywords` inputs:

| Input | Meaning | Default |
| --- | --- | --- |
| `source` | `arxiv`, `openalex`, `s2`, `openreview`, or `all` | `all` |
| `crawl_mode` | `auto`, `full`, or `incremental` | `auto` |
| `full_crawl_target` | structured paper threshold before auto mode switches to incremental | `20000` |
| `arxiv_days` | arXiv lookback window | `7`, raised to `3650` in full mode |
| `arxiv_max_results` | arXiv fetch cap | blank, resolved by workflow |
| `limit` | per-run processing cap | blank, raised to `50000` in full mode |
| `export_only` | export and deploy static site without crawling | `false` |

## Project Layout

```text
deeptrender/
├── src/
│   ├── agents/          # ingestion, structuring, analysis agents
│   ├── analysis/        # trend and statistics modules
│   ├── database/        # SQLite repositories and schema
│   ├── extractor/       # YAKE / KeyBERT keyword extraction
│   ├── scraper/         # arXiv / OpenReview / OpenAlex / Semantic Scholar clients
│   ├── tools/           # static site exporter and utility scripts
│   ├── web/             # Flask app and static frontend
│   └── main.py          # pipeline entrypoint
├── docs/                # exported GitHub Pages site
├── data/                # SQLite database
├── output/              # figures and reports
├── tests/               # test suite
└── .github/workflows/   # CI, update, and deployment workflows
```

## Tests

```bash
pytest -q
python -m compileall -q src
```

On Windows, use UTF-8 mode for the test suite:

```powershell
$env:PYTHONUTF8='1'
$env:PYTHONIOENCODING='utf-8'
python -m pytest -q
```
