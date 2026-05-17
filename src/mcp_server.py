"""
DeepTrender MCP Server

Exposes DeepTrender's statistical and intermediate data via the Model Context Protocol
so that agents can query paper trends, keyword statistics, and analysis results directly.

Usage:
    python src/mcp_server.py           # stdio transport (for Claude Desktop / agent SDKs)
    python src/mcp_server.py --port 8080  # HTTP/SSE transport

Tools exposed:
  Database status & overview
    - get_overview            : total papers, keywords, venues, years
    - get_status              : DB path, size, last modified, server time

  Venue statistics
    - list_venues             : all venues with paper counts and year ranges
    - get_venue_detail        : per-venue yearly stats + top keywords
    - get_venue_comparison    : side-by-side top keywords across venues for a year

  Keyword queries
    - get_top_keywords        : top-N keywords (optionally filtered by venue/year)
    - get_keyword_trends      : yearly count series for one or more keywords
    - get_emerging_keywords   : fast-growing keywords (venue-level analysis)
    - get_keyword_wordcloud   : keyword weight list for word-cloud rendering

  arXiv-specific (multi-granularity timeseries)
    - get_arxiv_timeseries    : paper count by year/month/week/day bucket + top kws
    - get_arxiv_stats         : raw arXiv counts by category and date range
    - get_arxiv_emerging      : emerging topics detected in arXiv data

  Intermediate / raw data
    - get_analysis_meta       : all key-value metadata stored by the analysis pipeline
    - get_venue_summaries     : cached venue summary objects from analysis layer
    - get_keyword_trend_cached: raw cached trend buckets (scope/venue/granularity)
    - get_raw_paper_count     : count of raw ingested papers (optionally by source)
    - get_scrape_log          : last scrape timestamp for a venue+year combination
"""

import sys
import argparse
import json
from pathlib import Path
from typing import Optional

# Allow importing from src/
sys.path.insert(0, str(Path(__file__).parent))

from mcp.server.fastmcp import FastMCP

from database import get_repository, DatabaseRepository
from config import VENUES

# ---------------------------------------------------------------------------
# Server bootstrap
# ---------------------------------------------------------------------------

mcp = FastMCP(
    name="deeptrender",
    instructions=(
        "DeepTrender tracks keyword and paper trends from AI/ML conferences "
        "(ICLR, NeurIPS, ICML …) and arXiv. Use these tools to retrieve "
        "statistical summaries, keyword rankings, trend time-series, and "
        "emerging topic signals."
    ),
)

# Lazy singleton – initialised on first tool call so that import is fast.
_repo: Optional[DatabaseRepository] = None


def _get_repo() -> DatabaseRepository:
    global _repo
    if _repo is None:
        _repo = get_repository()
    return _repo


# ---------------------------------------------------------------------------
# Helper
# ---------------------------------------------------------------------------

def _safe(value):
    """Return value as-is; convert sets/non-JSON-serialisable types."""
    if isinstance(value, set):
        return list(value)
    return value


# ---------------------------------------------------------------------------
# Tools – overview & status
# ---------------------------------------------------------------------------

@mcp.tool()
def get_overview() -> dict:
    """
    Return a high-level summary of the DeepTrender database.

    Returns a dict with:
      - total_papers   (int)
      - total_keywords (int)
      - total_venues   (int)
      - venues         (list[str])
      - years          (list[int])
      - year_range     (str, e.g. "2021-2025")
    """
    repo = _get_repo()
    venues = repo.get_all_venues()
    years = repo.get_all_years()
    return {
        "total_papers": repo.get_paper_count(),
        "total_keywords": repo.get_total_keyword_count(),
        "total_venues": len(venues),
        "venues": venues,
        "years": years,
        "year_range": f"{min(years)}-{max(years)}" if years else "N/A",
    }


@mcp.tool()
def get_status() -> dict:
    """
    Return database file info and server time.

    Returns a dict with:
      - database.path, database.size_bytes, database.last_modified
      - data.total_papers, data.total_venues, data.venues, data.year_range
      - server_time
    """
    import os
    from datetime import datetime

    repo = _get_repo()
    db_path = repo.db_path
    years = repo.get_all_years()
    return {
        "database": {
            "path": str(db_path),
            "size_bytes": os.path.getsize(db_path) if os.path.exists(db_path) else 0,
            "last_modified": (
                datetime.fromtimestamp(os.path.getmtime(db_path)).isoformat()
                if os.path.exists(db_path)
                else None
            ),
        },
        "data": {
            "total_papers": repo.get_paper_count(),
            "total_venues": len(repo.get_all_venues()),
            "venues": repo.get_all_venues(),
            "year_range": [min(years), max(years)] if years else None,
        },
        "server_time": __import__("datetime").datetime.now().isoformat(),
    }


# ---------------------------------------------------------------------------
# Tools – venue statistics
# ---------------------------------------------------------------------------

@mcp.tool()
def list_venues() -> list:
    """
    List all venues with their paper counts and available years.

    Returns a list of dicts, each with:
      - name        (str)  canonical venue name, e.g. "ICLR"
      - paper_count (int)
      - years       (list[int])
    """
    repo = _get_repo()
    venues = repo.get_all_venues()
    result = []
    for venue in venues:
        result.append({
            "name": venue,
            "paper_count": repo.get_paper_count(venue=venue),
            "years": repo.get_all_years(venue),
        })
    return result


@mcp.tool()
def get_venue_detail(venue: str) -> dict:
    """
    Return detailed statistics for a single venue, broken down by year.

    Args:
        venue: Canonical venue name (e.g. "ICLR", "NeurIPS", "ICML").

    Returns a dict with:
      - venue         (str)
      - total_papers  (int)
      - years         (list[int])
      - yearly_stats  list of {year, paper_count, top_keywords:[{keyword,count}]}
    """
    repo = _get_repo()
    years = repo.get_all_years(venue)
    yearly_stats = []
    for year in sorted(years, reverse=True):
        top_kw = repo.get_top_keywords(venue=venue, year=year, limit=10)
        yearly_stats.append({
            "year": year,
            "paper_count": repo.get_paper_count(venue=venue, year=year),
            "top_keywords": [{"keyword": kw, "count": cnt} for kw, cnt in top_kw],
        })
    return {
        "venue": venue,
        "total_papers": repo.get_paper_count(venue=venue),
        "years": years,
        "yearly_stats": yearly_stats,
    }


@mcp.tool()
def get_venue_comparison(year: Optional[int] = None, limit: int = 10) -> dict:
    """
    Compare top keywords across all venues for a given year.

    Args:
        year:  Target year (defaults to most recent year in the database).
        limit: Number of top keywords per venue (default 10, max 50).

    Returns a dict with:
      - year   (int)
      - venues dict[venue_name → list[{keyword, count}]]
    """
    repo = _get_repo()
    limit = min(int(limit), 50)
    if not year:
        years = repo.get_all_years()
        year = max(years) if years else 2024
    comparison = repo.get_venue_comparison(int(year), limit)
    return {
        "year": year,
        "venues": {
            v: [{"keyword": kw, "count": cnt} for kw, cnt in kws]
            for v, kws in comparison.items()
        },
    }


# ---------------------------------------------------------------------------
# Tools – keyword queries
# ---------------------------------------------------------------------------

@mcp.tool()
def get_top_keywords(
    venue: Optional[str] = None,
    year: Optional[int] = None,
    limit: int = 50,
    source: Optional[str] = None,
) -> list:
    """
    Return the top-N keywords, optionally filtered by venue and/or year.

    Args:
        venue:  Venue name filter (e.g. "ICLR"). None = all venues.
        year:   Year filter (e.g. 2024). None = all years.
        limit:  Number of keywords to return (default 50, max 200).
        source: Keyword source filter: "author", "extracted", or None for both.

    Returns a list of {keyword: str, count: int} sorted by count descending.
    """
    repo = _get_repo()
    limit = min(int(limit), 200)
    keywords = repo.get_top_keywords(
        venue=venue,
        year=int(year) if year else None,
        source=source,
        limit=limit,
    )
    return [{"keyword": kw, "count": cnt} for kw, cnt in keywords]


@mcp.tool()
def get_keyword_trends(
    keywords: list,
    venue: Optional[str] = None,
) -> list:
    """
    Return the yearly count trend for one or more keywords.

    Args:
        keywords: List of keyword strings (e.g. ["transformer", "diffusion"]).
                  If empty, defaults to the top 5 keywords overall.
        venue:    Venue filter. None = all venues combined.

    Returns a list of dicts, one per keyword:
      {keyword, years: list[int], counts: list[int]}
    """
    repo = _get_repo()
    if not keywords:
        keywords = [kw for kw, _ in repo.get_top_keywords(venue=venue, limit=5)]
    result = []
    for keyword in keywords:
        trend = repo.get_keyword_trend(str(keyword), venue)
        years_sorted = sorted(trend.keys())
        result.append({
            "keyword": keyword,
            "years": years_sorted,
            "counts": [trend[y] for y in years_sorted],
        })
    return result


@mcp.tool()
def get_emerging_keywords(top_n: int = 20) -> list:
    """
    Return keywords that are growing rapidly in recent years (venue-level analysis).

    Args:
        top_n: Number of emerging keywords to return (default 20, max 100).

    Returns a list of dicts with keyword and growth metadata.
    """
    from analysis import get_analyzer

    top_n = min(int(top_n), 100)
    analyzer = get_analyzer(_get_repo())
    return analyzer.get_emerging_keywords(top_n=top_n)


@mcp.tool()
def get_keyword_wordcloud(
    venue: Optional[str] = None,
    year: Optional[int] = None,
    limit: int = 100,
) -> list:
    """
    Return keyword weights suitable for word-cloud rendering.

    Args:
        venue:  Venue filter. None = all venues.
        year:   Year filter. None = all years.
        limit:  Max keywords to return (default 100, max 500).

    Returns a list of {name: str, value: int} sorted by value descending.
    """
    repo = _get_repo()
    limit = min(int(limit), 500)
    keywords = repo.get_top_keywords(
        venue=venue,
        year=int(year) if year else None,
        limit=limit,
    )
    return [{"name": kw, "value": cnt} for kw, cnt in keywords]


# ---------------------------------------------------------------------------
# Tools – arXiv-specific
# ---------------------------------------------------------------------------

@mcp.tool()
def get_arxiv_timeseries(
    granularity: str = "year",
    category: str = "ALL",
) -> list:
    """
    Return arXiv paper-count time-series from the analysis cache.

    Args:
        granularity: Time bucket size – one of "year", "month", "week", "day".
                     Default "year".
        category:    arXiv category filter – e.g. "cs.LG", "cs.CV", "cs.CL",
                     "cs.AI", "cs.RO", or "ALL" (default).

    Returns a list of buckets sorted chronologically:
      [{bucket: str, paper_count: int, top_keywords: list[{keyword,score}]}]

    Note: data is only available after the analysis pipeline has run at least once
    (python src/main.py).  Returns [] if no cache exists yet.
    """
    valid_granularities = {"year", "month", "week", "day"}
    if granularity not in valid_granularities:
        return [{"error": f"granularity must be one of {sorted(valid_granularities)}"}]
    repo = _get_repo()
    return repo.analysis.get_arxiv_timeseries(category, granularity)


@mcp.tool()
def get_arxiv_stats(categories: Optional[list] = None) -> dict:
    """
    Return aggregated counts of arXiv papers per category with date range.

    Args:
        categories: List of arXiv category strings to count.
                    Defaults to ["cs.LG", "cs.CL", "cs.CV", "cs.AI", "cs.RO"].

    Returns a dict with:
      - total_papers (int)   total raw arXiv papers ingested
      - categories   dict[category → count]
      - date_range   {min, max} ISO date strings of retrieved_at
      - latest_update (str|None) last pipeline run timestamp
    """
    repo = _get_repo()
    return repo.get_arxiv_stats(categories or None)


@mcp.tool()
def get_arxiv_emerging(
    category: str = "ALL",
    limit: int = 20,
    min_growth_rate: float = 1.5,
) -> list:
    """
    Return emerging topics detected in arXiv data by the analysis pipeline.

    Args:
        category:        arXiv category (e.g. "cs.LG") or "ALL".
        limit:           Max results (default 20, max 100).
        min_growth_rate: Minimum growth-rate multiplier (default 1.5×).

    Returns a list of dicts:
      {category, keyword, growth_rate, first_seen, recent_count, trend, updated_at}
    """
    repo = _get_repo()
    limit = min(int(limit), 100)
    return repo.analysis.get_emerging_topics(
        category=category,
        limit=limit,
        min_growth_rate=float(min_growth_rate),
    )


# ---------------------------------------------------------------------------
# Tools – intermediate / raw data
# ---------------------------------------------------------------------------

@mcp.tool()
def get_analysis_meta() -> dict:
    """
    Return all key-value metadata stored by the analysis pipeline.

    This includes last-run timestamps, last retrieved_at watermarks, and
    any other bookkeeping values written by ArxivAnalysisAgent or AnalysisAgent.

    Returns a dict[str → str].
    """
    repo = _get_repo()
    return repo.analysis.get_all_meta()


@mcp.tool()
def get_venue_summaries(venue: Optional[str] = None, year: Optional[int] = None) -> list:
    """
    Return cached venue summary objects produced by the analysis pipeline.

    Args:
        venue: Filter by venue name. None = all venues.
        year:  Filter by year. None = all years (including aggregate rows).

    Returns a list of dicts:
      {venue, year, paper_count, top_keywords, emerging_keywords, updated_at}
    """
    repo = _get_repo()
    all_summaries = repo.analysis.get_all_venue_summaries()
    result = []
    for s in all_summaries:
        if venue and s.get("venue") != venue:
            continue
        if year is not None:
            # year=None in summary means aggregate; match explicitly
            if s.get("year") != year:
                continue
        result.append(s)
    return result


@mcp.tool()
def get_keyword_trend_cached(
    scope: str,
    keyword: str,
    granularity: str,
    venue: Optional[str] = None,
) -> list:
    """
    Return raw cached trend data points for a keyword from the analysis layer.

    Args:
        scope:       Data scope – "venue" or "arxiv".
        keyword:     Keyword string (case-insensitive).
        granularity: Time bucket – "year", "month", "week", or "day".
        venue:       Venue name (relevant when scope="venue"). None = all.

    Returns a list of {bucket: str, count: int} sorted chronologically.
    """
    repo = _get_repo()
    return repo.analysis.get_keyword_trends_cached(
        scope=scope,
        keyword=keyword,
        granularity=granularity,
        venue=venue,
    )


@mcp.tool()
def get_raw_paper_count(source: Optional[str] = None) -> dict:
    """
    Return the count of raw papers ingested by the pipeline.

    Args:
        source: Data source filter – "arxiv", "openreview", "openalex", "s2",
                or None for total across all sources.

    Returns {source: str|"all", count: int}.
    """
    repo = _get_repo()
    count = repo.raw.get_raw_paper_count(source=source)
    return {"source": source or "all", "count": count}


@mcp.tool()
def get_scrape_log(venue: str, year: int) -> dict:
    """
    Return the last scrape timestamp recorded for a venue + year pair.

    Args:
        venue: Canonical venue name (e.g. "ICLR").
        year:  Publication year (e.g. 2024).

    Returns {venue, year, last_scraped: ISO string or null, should_scrape: bool}.
    """
    repo = _get_repo()
    last = repo.get_last_scrape(venue, int(year))
    return {
        "venue": venue,
        "year": int(year),
        "last_scraped": last.isoformat() if last else None,
        "should_scrape": repo.should_scrape(venue, int(year)),
    }


@mcp.tool()
def list_configured_venues() -> list:
    """
    Return the list of venues defined in config.py (the canonical registry).

    Returns a list of dicts:
      {key, name, full_name, venue_id_pattern, years: list[int]}
    """
    return [
        {
            "key": k,
            "name": v.name,
            "full_name": v.full_name,
            "venue_id_pattern": v.venue_id_pattern,
            "years": v.years,
        }
        for k, v in VENUES.items()
    ]


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(
        description="DeepTrender MCP Server – exposes trend data to AI agents via MCP"
    )
    parser.add_argument(
        "--transport",
        choices=["stdio", "streamable-http"],
        default="stdio",
        help="Transport type (default: stdio)",
    )
    parser.add_argument(
        "--host",
        default="127.0.0.1",
        help="Host for HTTP transport (default: 127.0.0.1)",
    )
    parser.add_argument(
        "--port",
        type=int,
        default=8090,
        help="Port for HTTP transport (default: 8090)",
    )
    args = parser.parse_args()

    if args.transport == "streamable-http":
        mcp.run(transport="streamable-http", host=args.host, port=args.port)
    else:
        mcp.run(transport="stdio")


if __name__ == "__main__":
    main()
