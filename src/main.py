"""DeepTrender pipeline entrypoint."""

import argparse
import sys
from pathlib import Path
from typing import List
from datetime import datetime

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(errors="replace")
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(errors="replace")

sys.path.insert(0, str(Path(__file__).parent))

from agents import IngestionAgent, StructuringAgent
from agents.analysis_agent import AnalysisAgent
from analysis import get_analyzer
from config import VENUES
from scraper.semantic_scholar import S2_VENUES
from visualization import generate_all_charts
from report import generate_report

FULL_CRAWL_ARXIV_DAYS = 3650
FULL_CRAWL_ARXIV_MAX_RESULTS = 50000
FULL_CRAWL_PROCESSING_LIMIT = 50000


def _full_crawl_venues() -> List[str]:
    return sorted(set(VENUES.keys()) | set(S2_VENUES.keys()))


def _full_crawl_years() -> List[int]:
    years = set()
    for config in list(VENUES.values()) + list(S2_VENUES.values()):
        years.update(config.years)
    return sorted(years, reverse=True)


def resolve_crawl_options(
    sources: List[str] = None,
    arxiv_days: int = 7,
    arxiv_max_results: int = 1000,
    venues: List[str] = None,
    years: List[int] = None,
    limit: int = 5000,
    full_crawl: bool = False,
) -> dict:
    """Resolve incremental defaults versus broad first-run bootstrap defaults."""

    if not full_crawl:
        return {
            "sources": sources,
            "arxiv_days": arxiv_days,
            "arxiv_max_results": arxiv_max_results,
            "venues": venues,
            "years": years,
            "limit": limit,
        }

    return {
        "sources": sources or ["arxiv", "openalex", "s2", "openreview"],
        "arxiv_days": max(arxiv_days or 0, FULL_CRAWL_ARXIV_DAYS),
        "arxiv_max_results": max(arxiv_max_results or 0, FULL_CRAWL_ARXIV_MAX_RESULTS),
        "venues": venues or _full_crawl_venues(),
        "years": years or _full_crawl_years(),
        "limit": max(limit or 0, FULL_CRAWL_PROCESSING_LIMIT),
    }


def run_topic_fact_rebuild(
    *,
    skip_topic_facts: bool = False,
    include_child_topics: bool = False,
    rebuild_func=None,
) -> dict | None:
    """Rebuild persisted topic facts after keyword analysis."""

    if skip_topic_facts:
        print("\n[topic facts] Rebuild skipped")
        return None

    if rebuild_func is None:
        from services.topic_facts import rebuild_paper_topics as rebuild_func

    print("\n[topic facts] Rebuilding paper_topics")
    summary = rebuild_func(include_children=include_child_topics)
    print(
        "   processed={processed_papers} matched={matched_papers} facts={topic_match_count}".format(
            **summary
        )
    )
    if summary.get("warnings"):
        for warning in summary["warnings"]:
            print(f"   warning: {warning.get('code')}: {warning.get('message')}")
    return summary


def run_pipeline(
    sources: List[str] = None,
    arxiv_days: int = 7,
    arxiv_max_results: int = 1000,
    venues: List[str] = None,
    years: List[int] = None,
    extractor: str = "yake",
    limit: int = 5000,
    full_crawl: bool = False,
    skip_ingestion: bool = False,
    skip_structuring: bool = False,
    skip_topic_facts: bool = False,
    include_child_topics: bool = False,
) -> str:
    print("=" * 60)
    print("DeepTrender - Three-stage Pipeline")
    print("=" * 60)
    print(f"Start: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")

    crawl_options = resolve_crawl_options(
        sources=sources,
        arxiv_days=arxiv_days,
        arxiv_max_results=arxiv_max_results,
        venues=venues,
        years=years,
        limit=limit,
        full_crawl=full_crawl,
    )

    sources = crawl_options["sources"]
    arxiv_days = crawl_options["arxiv_days"]
    arxiv_max_results = crawl_options["arxiv_max_results"]
    venues = crawl_options["venues"]
    years = crawl_options["years"]
    limit = crawl_options["limit"]

    if full_crawl:
        print("\n[mode] Full bootstrap crawl")
        print(f"   arXiv days: {arxiv_days}")
        print(f"   arXiv max results: {arxiv_max_results}")
        print(f"   processing limit: {limit}")

    if not skip_ingestion:
        print("\n[1/3] Ingestion")
        ingestion_agent = IngestionAgent()
        ingestion_agent.run(
            sources=sources or ["arxiv", "openalex"],
            arxiv_days=arxiv_days,
            arxiv_max_results=arxiv_max_results,
            venues=venues,
            years=years,
        )
    else:
        print("\n[1/3] Ingestion skipped")

    if not skip_structuring:
        print("\n[2/3] Structuring")
        structuring_agent = StructuringAgent()
        structuring_agent.run(limit=limit)
    else:
        print("\n[2/3] Structuring skipped")

    print("\n[3/3] Analysis")
    analysis_agent = AnalysisAgent()

    if extractor == "yake":
        analysis_agent.run(method="yake", limit=limit)
    elif extractor == "keybert":
        analysis_agent.run(method="keybert", limit=limit)
    elif extractor == "both":
        analysis_agent.run(method="yake", limit=limit)
        analysis_agent.run(method="keybert", limit=limit)

    run_topic_fact_rebuild(
        skip_topic_facts=skip_topic_facts,
        include_child_topics=include_child_topics,
    )

    try:
        from analysis.arxiv_agent import ArxivAnalysisAgent

        arxiv_agent = ArxivAnalysisAgent()
        arxiv_agent.run_all_granularities(category="ALL", force=False)
        arxiv_agent.detect_emerging_topics(category="ALL", threshold=1.5)
    except Exception as exc:
        print(f"arXiv analysis warning: {exc}")

    analyzer = get_analyzer()
    result = analyzer.analyze()

    charts = generate_all_charts(result)
    report_path = generate_report(result, charts)

    print("\nPipeline completed")
    print(f"Report: {report_path}")
    print(f"End: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")

    return str(report_path)


def main():
    parser = argparse.ArgumentParser(description="DeepTrender pipeline")
    parser.add_argument(
        "--source",
        type=str,
        choices=["arxiv", "openalex", "s2", "openreview", "all"],
        default="all",
        help="Data source (default: all)",
    )
    parser.add_argument("--arxiv-days", type=int, default=7, help="Recent arXiv days")
    parser.add_argument(
        "--arxiv-max-results",
        type=int,
        default=1000,
        help="Maximum arXiv papers to fetch before date filtering",
    )
    parser.add_argument("--venue", type=str, nargs="+", help="Venues to include")
    parser.add_argument("--year", type=int, nargs="+", help="Years to include")
    parser.add_argument("--limit", type=int, default=5000, help="Processing limit")
    parser.add_argument(
        "--extractor",
        type=str,
        choices=["yake", "keybert", "both"],
        default="yake",
        help="Keyword extractor",
    )
    parser.add_argument(
        "--full-crawl",
        action="store_true",
        help="Use broad first-run crawl defaults for GitHub Actions/bootstrap runs",
    )
    parser.add_argument(
        "--skip-ingestion", action="store_true", help="Skip ingestion stage"
    )
    parser.add_argument(
        "--skip-structuring", action="store_true", help="Skip structuring stage"
    )
    parser.add_argument(
        "--skip-topic-facts",
        action="store_true",
        help="Skip rebuilding the derived paper_topics fact layer",
    )
    parser.add_argument(
        "--include-child-topics",
        action="store_true",
        help="Explicitly include child taxonomy topics when rebuilding paper_topics",
    )

    args = parser.parse_args()
    sources = None if args.source == "all" else [args.source]

    run_pipeline(
        sources=sources,
        arxiv_days=args.arxiv_days,
        arxiv_max_results=args.arxiv_max_results,
        venues=args.venue,
        years=args.year,
        extractor=args.extractor,
        limit=args.limit,
        full_crawl=args.full_crawl,
        skip_ingestion=args.skip_ingestion,
        skip_structuring=args.skip_structuring,
        skip_topic_facts=args.skip_topic_facts,
        include_child_topics=args.include_child_topics,
    )


if __name__ == "__main__":
    main()
