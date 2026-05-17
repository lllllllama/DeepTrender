"""MCP-ready read-only service functions for DeepTrender v0.1."""

from __future__ import annotations

from collections import Counter
from datetime import datetime
from typing import Any

from database import get_repository
from scraper.models import Paper
from taxonomy.loader import DATA_POLICY_VERSION, TAXONOMY_VERSION
from taxonomy.loader import load_domains as taxonomy_load_domains
from taxonomy.loader import load_topics as taxonomy_load_topics
from taxonomy.resolver import match_paper_topics
from taxonomy.resolver import resolve_topic as taxonomy_resolve_topic

from .quality_report import build_warnings


def _now() -> str:
    return datetime.now().isoformat()


def _meta(
    *,
    source_layer: str,
    limit: int,
    offset: int,
    has_more: bool,
) -> dict[str, Any]:
    return {
        "taxonomy_version": TAXONOMY_VERSION,
        "data_policy_version": DATA_POLICY_VERSION,
        "generated_at": _now(),
        "source_layer": source_layer,
        "limit": limit,
        "offset": offset,
        "has_more": has_more,
    }


def _response(
    *,
    data: dict[str, Any],
    source_layer: str,
    warnings: list[dict] | None = None,
    evidence: list[dict] | None = None,
    limit: int = 100,
    offset: int = 0,
    has_more: bool = False,
) -> dict[str, Any]:
    return {
        "data": data,
        "meta": _meta(
            source_layer=source_layer,
            limit=limit,
            offset=offset,
            has_more=has_more,
        ),
        "warnings": warnings or [],
        "evidence": evidence or [],
    }


def _paginate(items: list[Any], limit: int, offset: int) -> tuple[list[Any], bool]:
    limit = max(0, int(limit))
    offset = max(0, int(offset))
    end = offset + limit
    return items[offset:end], end < len(items)


def list_domains(limit: int = 100, offset: int = 0) -> dict[str, Any]:
    """Return all configured domains."""

    domains = [
        {"domain": domain_id, **domain}
        for domain_id, domain in taxonomy_load_domains().items()
    ]
    page, has_more = _paginate(domains, limit, offset)
    return _response(
        data={
            "domains": page,
            "pagination": {
                "limit": limit,
                "offset": offset,
                "total": len(domains),
                "has_more": has_more,
            },
        },
        source_layer="taxonomy",
        evidence=[{"type": "taxonomy_file", "path": "config/taxonomy/domains.yaml"}],
        limit=limit,
        offset=offset,
        has_more=has_more,
    )


def list_topics(
    domain: str | None = None,
    limit: int = 100,
    offset: int = 0,
) -> dict[str, Any]:
    """Return canonical topics, optionally filtered by domain."""

    domain_norm = domain.upper() if domain else None
    topics = []
    for topic_id, topic in taxonomy_load_topics().items():
        if domain_norm and topic.get("domain", "").upper() != domain_norm:
            continue
        topics.append({"topic_id": topic_id, **topic})

    page, has_more = _paginate(topics, limit, offset)
    return _response(
        data={
            "normalized_query": {"domain": domain_norm},
            "topics": page,
            "pagination": {
                "limit": limit,
                "offset": offset,
                "total": len(topics),
                "has_more": has_more,
            },
        },
        source_layer="taxonomy",
        evidence=[{"type": "taxonomy_file", "path": "config/taxonomy/topics.yaml"}],
        limit=limit,
        offset=offset,
        has_more=has_more,
    )


def resolve_topic(query: str, include_children: bool = False) -> dict[str, Any]:
    """Resolve a query into a canonical topic response."""

    resolved = taxonomy_resolve_topic(query, include_children=include_children)
    warnings = build_warnings({"topic_match_confidence": resolved["confidence"]})
    normalized_query = {
        "input_topic": query,
        "canonical_topic": resolved["canonical_topic"],
        "topic_id": resolved["topic_id"],
        "domain": resolved["domain"],
        "include_children": include_children,
        "aliases_used": resolved["aliases_used"],
    }
    if include_children:
        normalized_query["child_topic_ids"] = resolved.get("child_topic_ids", [])

    return _response(
        data={
            "normalized_query": normalized_query,
            "resolution": resolved,
        },
        source_layer="taxonomy",
        warnings=warnings,
        evidence=[{"type": "taxonomy_resolver", "match_method": resolved["match_method"]}],
        limit=1,
        offset=0,
        has_more=False,
    )


def _paper_status(paper: Paper) -> str:
    quality_flag = (paper.quality_flag or "unknown").lower()
    venue_type = (paper.venue_type or "unknown").lower()
    if quality_flag in {"accepted", "submitted", "filtered"}:
        return quality_flag
    if venue_type == "preprint":
        return "preprint"
    if venue_type == "journal":
        return "published"
    return "unknown"


def _paper_sources(repo: Any, paper_id: int | None) -> list[str]:
    if not paper_id:
        return ["unknown"]
    try:
        sources = repo.structured.get_paper_sources(paper_id)
    except Exception:
        return ["unknown"]
    names = sorted({source.source for source in sources if source.source})
    return names or ["unknown"]


def _quality_scope(papers: list[Paper]) -> dict[str, int]:
    scope = {
        "accepted": 0,
        "submitted": 0,
        "preprint": 0,
        "published": 0,
        "unknown": 0,
        "filtered": 0,
        "mixed": 0,
    }
    for paper in papers:
        scope[_paper_status(paper)] += 1
    return scope


def _paper_keywords(repo: Any, paper: Paper) -> list[str]:
    keywords = set(paper.keywords or [])
    keywords.update(paper.extracted_keywords or [])
    if paper.paper_id:
        try:
            keywords.update(item.keyword for item in repo.analysis.get_paper_keywords(paper.paper_id))
        except Exception:
            pass
    return sorted(keywords)


def get_venue_year_topic(
    venue: str,
    year: int,
    topic: str,
    include_children: bool = False,
    limit: int = 20,
    offset: int = 0,
    repo: Any | None = None,
) -> dict[str, Any]:
    """Return venue/year/topic facts with source evidence and warnings."""

    repo = repo or get_repository()
    resolved = taxonomy_resolve_topic(topic, include_children=include_children)
    topic_ids = {resolved["topic_id"]} if resolved["topic_id"] else set()
    topic_ids.update(resolved.get("child_topic_ids", []))

    papers = repo.get_papers_by_venue_year(venue, int(year))
    total_venue_papers = len(papers)
    matched_items: list[dict[str, Any]] = []
    matched_papers: list[Paper] = []
    source_counts: Counter[str] = Counter()

    for paper in papers:
        paper_keywords = _paper_keywords(repo, paper)
        matches = match_paper_topics(
            paper.title,
            paper.abstract,
            extracted_keywords=paper_keywords,
        )
        selected = next((match for match in matches if match["topic_id"] in topic_ids), None)
        if not selected:
            continue
        sources = _paper_sources(repo, paper.paper_id)
        source_counts.update(sources)
        matched_papers.append(paper)
        matched_items.append(
            {
                "paper_id": paper.paper_id,
                "title": paper.title,
                "venue": venue,
                "year": paper.year,
                "status": _paper_status(paper),
                "source_evidence": sources,
                "topic_match": selected,
            }
        )

    page, has_more = _paginate(matched_items, limit, offset)
    matched_count = len(matched_items)
    relative_frequency = matched_count / total_venue_papers if total_venue_papers else 0.0
    source_breakdown = dict(sorted(source_counts.items())) or {}
    known_sources = {source for source in source_breakdown if source != "unknown"}
    only_arxiv = bool(matched_count and known_sources == {"arxiv"} and "unknown" not in source_breakdown)
    warnings = build_warnings(
        {
            "matched_papers": matched_count,
            "topic_match_confidence": resolved["confidence"],
            "only_arxiv_evidence_for_conference_query": only_arxiv,
        }
    )

    normalized_query = {
        "venue": venue,
        "year": int(year),
        "input_topic": topic,
        "canonical_topic": resolved["canonical_topic"],
        "topic_id": resolved["topic_id"],
        "domain": resolved["domain"],
        "include_children": include_children,
        "aliases_used": resolved["aliases_used"],
    }
    if include_children:
        normalized_query["child_topic_ids"] = resolved.get("child_topic_ids", [])

    return _response(
        data={
            "normalized_query": normalized_query,
            "matched_papers": matched_count,
            "total_venue_papers": total_venue_papers,
            "relative_frequency": relative_frequency,
            "items": page,
            "source_breakdown": source_breakdown,
            "conference_source_policy": {
                "arxiv": "preprint evidence by default",
                "accepted": "OpenReview or official proceedings evidence required",
                "auxiliary": "OpenAlex and Semantic Scholar require high confidence",
            },
            "quality_scope": _quality_scope(matched_papers),
            "pagination": {
                "limit": limit,
                "offset": offset,
                "total": matched_count,
                "has_more": has_more,
            },
        },
        source_layer="taxonomy+structured+analysis",
        warnings=warnings,
        evidence=[
            {"type": "taxonomy_resolver", "match_method": resolved["match_method"]},
            {
                "type": "repository_query",
                "venue": venue,
                "year": int(year),
                "source_policy": "conference queries distinguish accepted, preprint, unknown, and mixed evidence",
            },
        ],
        limit=limit,
        offset=offset,
        has_more=has_more,
    )


def _safe_ratio(numerator: int, denominator: int) -> float | None:
    if denominator <= 0:
        return None
    return numerator / denominator


def _query_one(cursor: Any, sql: str, params: tuple[Any, ...] = ()) -> Any:
    cursor.execute(sql, params)
    row = cursor.fetchone()
    if not row:
        return None
    return row[0]


def get_data_quality_report(
    scope: dict | None = None,
    repo: Any | None = None,
) -> dict[str, Any]:
    """Return global or scoped quality metrics without fabricating data."""

    repo = repo or get_repository()
    scope = scope or {}
    with repo._get_connection() as conn:
        cursor = conn.cursor()
        raw_paper_count = int(_query_one(cursor, "SELECT COUNT(*) FROM raw_papers") or 0)
        structured_paper_count = int(_query_one(cursor, "SELECT COUNT(*) FROM papers") or 0)
        unknown_count = int(
            _query_one(
                cursor,
                "SELECT COUNT(*) FROM papers WHERE quality_flag IS NULL OR quality_flag = 'unknown'",
            )
            or 0
        )
        empty_abstract_count = int(
            _query_one(
                cursor,
                "SELECT COUNT(*) FROM papers WHERE abstract IS NULL OR TRIM(abstract) = ''",
            )
            or 0
        )
        cursor.execute("SELECT source, COUNT(*) FROM raw_papers GROUP BY source")
        source_counts = {row[0]: row[1] for row in cursor.fetchall()}
        last_ingestion_time = _query_one(
            cursor,
            "SELECT MAX(completed_at) FROM ingestion_logs",
        )
        last_analysis_time = _query_one(
            cursor,
            "SELECT MAX(updated_at) FROM analysis_meta",
        )

    max_source_count = max(source_counts.values()) if source_counts else 0
    metrics = {
        "raw_paper_count": raw_paper_count,
        "structured_paper_count": structured_paper_count,
        "unknown_quality_ratio": _safe_ratio(unknown_count, structured_paper_count),
        "empty_abstract_ratio": _safe_ratio(empty_abstract_count, structured_paper_count),
        "single_source_ratio": _safe_ratio(max_source_count, raw_paper_count),
        "last_ingestion_time": last_ingestion_time,
        "last_analysis_time": last_analysis_time,
        "source_breakdown": source_counts,
        "scope": scope,
    }
    warnings = build_warnings(metrics)

    return _response(
        data={"metrics": metrics},
        source_layer="raw+structured+analysis",
        warnings=warnings,
        evidence=[
            {"type": "database_tables", "tables": ["raw_papers", "papers", "analysis_meta"]},
        ],
        limit=1,
        offset=0,
        has_more=False,
    )
