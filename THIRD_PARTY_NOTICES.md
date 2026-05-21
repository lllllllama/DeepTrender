# Third-Party Notices

DeepTrender depends on open-source libraries and public research metadata
services. This file is a project-level notice, not a substitute for each
dependency's own license text. For redistribution, verify the package metadata
installed in your environment.

## Python Dependencies

The runtime and test dependencies are declared in `requirements.txt`.

| Package | Role |
| --- | --- |
| `openreview-py` | OpenReview API client |
| `yake` | Keyword extraction |
| `keybert` | Optional embedding-based keyword extraction |
| `sentence-transformers` | KeyBERT embedding backend |
| `pandas` | Data processing |
| `matplotlib` | Plotting |
| `wordcloud` | Word cloud generation |
| `flask` | REST API and local web server |
| `flask-cors` | Optional CORS support |
| `requests` | HTTP client |
| `gunicorn` | Production WSGI server |
| `python-dotenv` | Environment variable loading |
| `tqdm` | Progress display |
| `feedparser` | arXiv feed parsing support |
| `PyYAML` | Taxonomy and registry config loading |
| `mcp` | Model Context Protocol server support |
| `pytest`, `pytest-cov` | Test runner and coverage tooling |

## Browser-Side Libraries

The static dashboard uses browser-side charting assets served from the static
site. Review the corresponding asset files and upstream package notices before
redistribution if vendored files are changed.

## Data Sources

DeepTrender stores metadata retrieved from research-index services. The source
records remain governed by each provider's terms and citation guidance.

| Source | Project use |
| --- | --- |
| arXiv | Preprint metadata and category evidence |
| OpenReview | Conference submission and decision metadata where available |
| OpenAlex | Auxiliary scholarly metadata |
| Semantic Scholar | Auxiliary paper and venue metadata |

## Project License

DeepTrender's own source code is licensed under the MIT License. See `LICENSE`.
