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


def _status_from_values(quality_flag: str | None, venue_type: str | None) -> str:
    quality_flag = (quality_flag or "unknown").lower()
    venue_type = (venue_type or "unknown").lower()
    if quality_flag in {"accepted", "submitted", "filtered"}:
        return quality_flag
    if venue_type == "preprint":
        return "preprint"
    if venue_type == "journal":
        return "published"
    return "unknown"


def _paper_status(paper: Paper) -> str:
    return _status_from_values(paper.quality_flag, paper.venue_type)


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


def _runtime_topic_matching_fallback_warning() -> dict[str, Any]:
    return {
        "code": "runtime_topic_matching_fallback",
        "message": "paper_topics facts are unavailable; using runtime topic matching fallback.",
        "severity": "medium",
    }


def _paper_topics_available(repo: Any) -> bool:
    try:
        return repo.get_paper_topic_count(taxonomy_version=TAXONOMY_VERSION) > 0
    except Exception:
        return False


def _normalized_venue_year_topic_query(
    *,
    venue: str,
    year: int,
    topic: str,
    resolved: dict[str, Any],
    include_children: bool,
) -> dict[str, Any]:
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
    return normalized_query


def _conference_source_policy() -> dict[str, str]:
    return {
        "arxiv": "preprint evidence by default",
        "accepted": "OpenReview or official proceedings evidence required",
        "auxiliary": "OpenAlex and Semantic Scholar require high confidence",
    }


def _only_arxiv_source_breakdown(source_breakdown: dict[str, int], matched_count: int) -> bool:
    known_sources = {source for source in source_breakdown if source != "unknown"}
    return bool(matched_count and known_sources == {"arxiv"} and "unknown" not in source_breakdown)


def _runtime_venue_year_topic(
    *,
    repo: Any,
    venue: str,
    year: int,
    topic: str,
    resolved: dict[str, Any],
    include_children: bool,
    limit: int,
    offset: int,
) -> dict[str, Any]:
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

    return _build_venue_year_topic_response(
        normalized_query=_normalized_venue_year_topic_query(
            venue=venue,
            year=year,
            topic=topic,
            resolved=resolved,
            include_children=include_children,
        ),
        matched_items=matched_items,
        matched_papers=matched_papers,
        total_venue_papers=total_venue_papers,
        source_breakdown=dict(sorted(source_counts.items())) or {},
        resolved=resolved,
        source_layer="taxonomy+structured+analysis",
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
        extra_warnings=[_runtime_topic_matching_fallback_warning()],
    )


def _persisted_venue_year_topic(
    *,
    repo: Any,
    venue: str,
    year: int,
    topic: str,
    resolved: dict[str, Any],
    include_children: bool,
    limit: int,
    offset: int,
) -> dict[str, Any]:
    topic_ids = [resolved["topic_id"]] if resolved["topic_id"] else []
    topic_ids.extend(resolved.get("child_topic_ids", []))
    total_venue_papers = repo.get_paper_count(venue=venue, year=int(year))
    rows_by_paper: dict[int, dict[str, Any]] = {}

    for topic_id in topic_ids:
        rows = repo.get_papers_by_topic(
            topic_id,
            venue=venue,
            year=int(year),
            limit=100000,
            offset=0,
            taxonomy_version=TAXONOMY_VERSION,
        )
        for row in rows:
            paper_id = row["paper_id"]
            current = rows_by_paper.get(paper_id)
            if current is None or row["confidence"] > current["confidence"]:
                rows_by_paper[paper_id] = row

    matched_items: list[dict[str, Any]] = []
    matched_papers: list[Paper] = []
    source_counts: Counter[str] = Counter()
    for row in rows_by_paper.values():
        sources = _paper_sources(repo, row["paper_id"])
        source_counts.update(sources)
        matched_papers.append(
            Paper(
                paper_id=row["paper_id"],
                canonical_title=row["canonical_title"],
                abstract=row.get("abstract") or "",
                year=row["year"],
                venue_id=row.get("venue_id"),
                venue_type=row.get("venue_type") or "unknown",
                domain=row.get("paper_domain"),
                quality_flag=row.get("quality_flag") or "unknown",
                url=row.get("url"),
                pdf_url=row.get("pdf_url"),
                venue_name=row.get("venue"),
            )
        )
        matched_items.append(
            {
                "paper_id": row["paper_id"],
                "title": row["canonical_title"],
                "venue": row.get("venue"),
                "year": row["year"],
                "status": _status_from_values(row.get("quality_flag"), row.get("venue_type")),
                "source_evidence": sources,
                "topic_match": {
                    "topic_id": row["topic_id"],
                    "canonical_topic": row["canonical_topic"],
                    "domain": row.get("topic_domain"),
                    "match_method": row["match_method"],
                    "confidence": row["confidence"],
                    "evidence_keyword": row.get("evidence_keyword"),
                    "evidence_source": row.get("evidence_source"),
                    "taxonomy_version": row["taxonomy_version"],
                },
            }
        )

    return _build_venue_year_topic_response(
        normalized_query=_normalized_venue_year_topic_query(
            venue=venue,
            year=year,
            topic=topic,
            resolved=resolved,
            include_children=include_children,
        ),
        matched_items=matched_items,
        matched_papers=matched_papers,
        total_venue_papers=total_venue_papers,
        source_breakdown=dict(sorted(source_counts.items())) or {},
        resolved=resolved,
        source_layer="paper_topics+structured+analysis",
        evidence=[
            {
                "type": "paper_topics",
                "taxonomy_version": TAXONOMY_VERSION,
                "topic_ids": topic_ids,
            },
            {
                "type": "repository_query",
                "venue": venue,
                "year": int(year),
                "source_policy": "conference queries distinguish accepted, preprint, unknown, and mixed evidence",
            },
        ],
        limit=limit,
        offset=offset,
        extra_warnings=[],
    )


def _build_venue_year_topic_response(
    *,
    normalized_query: dict[str, Any],
    matched_items: list[dict[str, Any]],
    matched_papers: list[Paper],
    total_venue_papers: int,
    source_breakdown: dict[str, int],
    resolved: dict[str, Any],
    source_layer: str,
    evidence: list[dict[str, Any]],
    limit: int,
    offset: int,
    extra_warnings: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    page, has_more = _paginate(matched_items, limit, offset)
    matched_count = len(matched_items)
    relative_frequency = matched_count / total_venue_papers if total_venue_papers else 0.0
    warnings = build_warnings(
        {
            "matched_papers": matched_count,
            "topic_match_confidence": resolved["confidence"],
            "only_arxiv_evidence_for_conference_query": _only_arxiv_source_breakdown(
                source_breakdown,
                matched_count,
            ),
        }
    )
    warnings.extend(extra_warnings or [])

    return _response(
        data={
            "normalized_query": normalized_query,
            "matched_papers": matched_count,
            "total_venue_papers": total_venue_papers,
            "relative_frequency": relative_frequency,
            "items": page,
            "source_breakdown": source_breakdown,
            "conference_source_policy": _conference_source_policy(),
            "quality_scope": _quality_scope(matched_papers),
            "pagination": {
                "limit": limit,
                "offset": offset,
                "total": matched_count,
                "has_more": has_more,
            },
        },
        source_layer=source_layer,
        warnings=warnings,
        evidence=evidence,
        limit=limit,
        offset=offset,
        has_more=has_more,
    )


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
    if _paper_topics_available(repo):
        return _persisted_venue_year_topic(
            repo=repo,
            venue=venue,
            year=int(year),
            topic=topic,
            resolved=resolved,
            include_children=include_children,
            limit=limit,
            offset=offset,
        )

    return _runtime_venue_year_topic(
        repo=repo,
        venue=venue,
        year=int(year),
        topic=topic,
        resolved=resolved,
        include_children=include_children,
        limit=limit,
        offset=offset,
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


def _low_warning(code: str, message: str) -> dict[str, Any]:
    return {"code": code, "message": message, "severity": "low"}


def _medium_warning(code: str, message: str) -> dict[str, Any]:
    return {"code": code, "message": message, "severity": "medium"}


def _paper_source_details(repo: Any, paper_id: int) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    warnings = []
    with repo._get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute(
            """
            SELECT
                ps.source,
                ps.raw_id,
                ps.confidence,
                r.source_paper_id,
                r.retrieved_at
            FROM paper_sources ps
            LEFT JOIN raw_papers r ON ps.raw_id = r.raw_id
            WHERE ps.paper_id = ?
            ORDER BY ps.source, ps.raw_id
            """,
            (int(paper_id),),
        )
        rows = cursor.fetchall()

    if not rows:
        warnings.append(
            _low_warning(
                "source_links_unavailable",
                "No paper_sources rows are available for this paper.",
            )
        )
        return [], warnings

    warnings.append(
        _low_warning(
            "source_url_unavailable",
            "source_url is not available in the current schema and is returned as null.",
        )
    )
    return [
        {
            "source": row["source"],
            "raw_id": row["raw_id"],
            "source_paper_id": row["source_paper_id"],
            "confidence": row["confidence"],
            "retrieved_at": row["retrieved_at"],
            "source_url": None,
        }
        for row in rows
    ], warnings


def get_paper_provenance(paper_id: int, repo: Any | None = None) -> dict[str, Any]:
    """Return paper, source, and persisted topic provenance."""

    repo = repo or get_repository()
    warnings: list[dict[str, Any]] = []
    paper = repo.get_paper(int(paper_id))
    sources: list[dict[str, Any]] = []
    topics: list[dict[str, Any]] = []
    paper_data = None

    if paper is None:
        warnings.append(
            _medium_warning(
                "paper_not_found",
                f"Paper {paper_id} was not found in structured papers.",
            )
        )
    else:
        sources, source_warnings = _paper_source_details(repo, int(paper_id))
        warnings.extend(source_warnings)
        topics = [
            {
                "topic_id": topic["topic_id"],
                "canonical_topic": topic["canonical_topic"],
                "match_method": topic["match_method"],
                "confidence": topic["confidence"],
                "taxonomy_version": topic["taxonomy_version"],
            }
            for topic in repo.get_paper_topics(int(paper_id), taxonomy_version=TAXONOMY_VERSION)
        ]
        paper_data = {
            "paper_id": paper.paper_id,
            "title": paper.title,
            "year": paper.year,
            "venue": paper.venue,
            "status": _paper_status(paper),
        }

    return _response(
        data={
            "normalized_query": {"paper_id": int(paper_id)},
            "paper": paper_data,
            "sources": sources,
            "topics": topics,
        },
        source_layer="structured+raw+paper_topics",
        warnings=warnings,
        evidence=[
            {
                "type": "database_tables",
                "tables": ["papers", "paper_sources", "raw_papers", "paper_topics"],
            }
        ],
        limit=1,
        offset=0,
        has_more=False,
    )


def _source_coverage_from_paper_ids(repo: Any, paper_ids: list[int]) -> dict[str, int]:
    if not paper_ids:
        return {}
    placeholders = ",".join("?" for _ in paper_ids)
    with repo._get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute(
            f"""
            SELECT source, COUNT(*) AS count
            FROM paper_sources
            WHERE paper_id IN ({placeholders})
            GROUP BY source
            ORDER BY source
            """,
            tuple(paper_ids),
        )
        return {row["source"]: row["count"] for row in cursor.fetchall()}


def get_topic_source_coverage(
    topic: str,
    venue: str | None = None,
    year: int | None = None,
    repo: Any | None = None,
) -> dict[str, Any]:
    """Return source coverage for persisted topic facts."""

    repo = repo or get_repository()
    resolved = taxonomy_resolve_topic(topic)
    topic_id = resolved.get("topic_id") or topic
    warnings = build_warnings({"topic_match_confidence": resolved["confidence"]})
    rows: list[dict[str, Any]] = []
    if _paper_topics_available(repo):
        rows = repo.get_papers_by_topic(
            topic_id,
            venue=venue,
            year=year,
            limit=100000,
            offset=0,
            taxonomy_version=TAXONOMY_VERSION,
        )
    else:
        warnings.append(
            _medium_warning(
                "paper_topics_unavailable",
                "paper_topics facts are unavailable for the current taxonomy version.",
            )
        )
    paper_ids = sorted({row["paper_id"] for row in rows})
    source_breakdown = _source_coverage_from_paper_ids(repo, paper_ids)
    total_sources = sum(source_breakdown.values())
    coverage = {
        source: count / total_sources if total_sources else 0.0
        for source, count in source_breakdown.items()
    }
    return _response(
        data={
            "normalized_query": {
                "input_topic": topic,
                "topic_id": topic_id,
                "canonical_topic": resolved.get("canonical_topic"),
                "venue": venue,
                "year": year,
            },
            "matched_papers": len(paper_ids),
            "source_breakdown": source_breakdown,
            "source_coverage": coverage,
            "taxonomy_version": TAXONOMY_VERSION,
        },
        source_layer="paper_topics+paper_sources",
        warnings=warnings,
        evidence=[
            {"type": "paper_topics", "taxonomy_version": TAXONOMY_VERSION},
            {"type": "paper_sources"},
        ],
        limit=1,
        offset=0,
        has_more=False,
    )


def get_venue_year_source_coverage(
    venue: str,
    year: int,
    repo: Any | None = None,
) -> dict[str, Any]:
    """Return source coverage for a venue/year structured paper scope."""

    repo = repo or get_repository()
    papers = repo.get_papers_by_venue_year(venue, int(year))
    paper_ids = sorted({paper.paper_id for paper in papers if paper.paper_id})
    source_breakdown = _source_coverage_from_paper_ids(repo, paper_ids)
    total_sources = sum(source_breakdown.values())
    coverage = {
        source: count / total_sources if total_sources else 0.0
        for source, count in source_breakdown.items()
    }
    warnings = []
    if not source_breakdown and paper_ids:
        warnings.append(
            _low_warning(
                "source_links_unavailable",
                "No paper_sources rows are available for this venue/year scope.",
            )
        )
    return _response(
        data={
            "normalized_query": {"venue": venue, "year": int(year)},
            "structured_paper_count": len(paper_ids),
            "source_breakdown": source_breakdown,
            "source_coverage": coverage,
            "quality_scope": _quality_scope(papers),
        },
        source_layer="structured+paper_sources",
        warnings=warnings,
        evidence=[{"type": "database_tables", "tables": ["papers", "venues", "paper_sources"]}],
        limit=1,
        offset=0,
        has_more=False,
    )


def _metric_not_available_warning(metric: str) -> dict[str, Any]:
    return {
        "code": "metric_not_available_for_scope",
        "message": f"{metric} is not available for this scope.",
        "severity": "low",
    }


def _paper_ids_for_scope(repo: Any, scope: dict[str, Any]) -> tuple[list[int], list[dict[str, Any]]]:
    warnings: list[dict[str, Any]] = []
    scope = scope or {}
    params: list[Any] = []

    if scope.get("topic"):
        resolved = taxonomy_resolve_topic(str(scope["topic"]))
        topic_id = resolved.get("topic_id") or scope["topic"]
        if not _paper_topics_available(repo):
            warnings.append(
                _medium_warning(
                    "paper_topics_unavailable",
                    "paper_topics facts are unavailable for the current taxonomy version.",
                )
            )
            return [], warnings
        query = """
            SELECT DISTINCT p.paper_id
            FROM paper_topics pt
            JOIN papers p ON pt.paper_id = p.paper_id
            LEFT JOIN venues v ON p.venue_id = v.venue_id
            WHERE pt.topic_id = ?
              AND pt.taxonomy_version = ?
        """
        params.extend([topic_id, TAXONOMY_VERSION])
    elif scope.get("source"):
        query = """
            SELECT DISTINCT p.paper_id
            FROM paper_sources ps
            JOIN papers p ON ps.paper_id = p.paper_id
            LEFT JOIN venues v ON p.venue_id = v.venue_id
            WHERE ps.source = ?
        """
        params.append(scope["source"])
    else:
        query = """
            SELECT DISTINCT p.paper_id
            FROM papers p
            LEFT JOIN venues v ON p.venue_id = v.venue_id
            WHERE 1=1
        """

    if scope.get("venue"):
        query += " AND v.canonical_name = ?"
        params.append(scope["venue"])
    if scope.get("year") is not None:
        query += " AND p.year = ?"
        params.append(int(scope["year"]))
    if scope.get("domain"):
        query += " AND (p.domain = ? OR v.domain = ?)"
        params.extend([scope["domain"], scope["domain"]])

    with repo._get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute(query, tuple(params))
        return [row["paper_id"] for row in cursor.fetchall()], warnings


def _count_scoped_papers(repo: Any, paper_ids: list[int]) -> dict[str, Any]:
    if not paper_ids:
        return {
            "structured_paper_count": 0,
            "unknown_count": 0,
            "empty_abstract_count": 0,
            "quality_scope": {
                "accepted": 0,
                "submitted": 0,
                "preprint": 0,
                "published": 0,
                "unknown": 0,
                "filtered": 0,
                "mixed": 0,
            },
        }

    placeholders = ",".join("?" for _ in paper_ids)
    with repo._get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute(
            f"""
            SELECT
                COUNT(*) AS total,
                SUM(CASE WHEN quality_flag IS NULL OR quality_flag = 'unknown' THEN 1 ELSE 0 END) AS unknown_count,
                SUM(CASE WHEN abstract IS NULL OR TRIM(abstract) = '' THEN 1 ELSE 0 END) AS empty_abstract_count
            FROM papers
            WHERE paper_id IN ({placeholders})
            """,
            tuple(paper_ids),
        )
        row = cursor.fetchone()
        cursor.execute(
            f"""
            SELECT quality_flag, venue_type, COUNT(*) AS count
            FROM papers
            WHERE paper_id IN ({placeholders})
            GROUP BY quality_flag, venue_type
            """,
            tuple(paper_ids),
        )
        quality_scope = {
            "accepted": 0,
            "submitted": 0,
            "preprint": 0,
            "published": 0,
            "unknown": 0,
            "filtered": 0,
            "mixed": 0,
        }
        for status_row in cursor.fetchall():
            quality_scope[_status_from_values(status_row["quality_flag"], status_row["venue_type"])] += status_row["count"]

    return {
        "structured_paper_count": row["total"] if row else 0,
        "unknown_count": row["unknown_count"] if row and row["unknown_count"] is not None else 0,
        "empty_abstract_count": row["empty_abstract_count"] if row and row["empty_abstract_count"] is not None else 0,
        "quality_scope": quality_scope,
    }


def _raw_count_for_scope(
    repo: Any,
    scope: dict[str, Any],
    paper_ids: list[int],
    warnings: list[dict[str, Any]],
) -> int | None:
    scope = scope or {}
    with repo._get_connection() as conn:
        cursor = conn.cursor()
        if not scope:
            return int(_query_one(cursor, "SELECT COUNT(*) FROM raw_papers") or 0)
        if scope.get("source") and not any(key in scope for key in ("venue", "year", "topic", "domain")):
            return int(
                _query_one(
                    cursor,
                    "SELECT COUNT(*) FROM raw_papers WHERE source = ?",
                    (scope["source"],),
                )
                or 0
            )
        if scope.get("domain") and not any(key in scope for key in ("venue", "year", "topic", "source")):
            warnings.append(_metric_not_available_warning("raw_paper_count"))
            return None
        if not paper_ids:
            return 0
        placeholders = ",".join("?" for _ in paper_ids)
        return int(
            _query_one(
                cursor,
                f"""
                SELECT COUNT(DISTINCT raw_id)
                FROM paper_sources
                WHERE paper_id IN ({placeholders})
                """,
                tuple(paper_ids),
            )
            or 0
        )


def get_data_quality_report(
    scope: dict | None = None,
    repo: Any | None = None,
) -> dict[str, Any]:
    """Return global or scoped quality metrics without fabricating data."""

    repo = repo or get_repository()
    scope = scope or {}
    scope_warnings: list[dict[str, Any]] = []
    paper_ids, scope_warnings = _paper_ids_for_scope(repo, scope)
    counts = _count_scoped_papers(repo, paper_ids)
    raw_paper_count = _raw_count_for_scope(repo, scope, paper_ids, scope_warnings)
    source_counts = _source_coverage_from_paper_ids(repo, paper_ids)

    with repo._get_connection() as conn:
        cursor = conn.cursor()
        if not scope:
            cursor.execute("SELECT source, COUNT(*) FROM raw_papers GROUP BY source")
            source_counts = {row[0]: row[1] for row in cursor.fetchall()}
        last_ingestion_time = _query_one(cursor, "SELECT MAX(completed_at) FROM ingestion_logs")
        last_analysis_time = _query_one(cursor, "SELECT MAX(updated_at) FROM analysis_meta")

    source_total = sum(source_counts.values())
    max_source_count = max(source_counts.values()) if source_counts else 0
    structured_paper_count = counts["structured_paper_count"]
    metrics = {
        "raw_paper_count": raw_paper_count,
        "structured_paper_count": structured_paper_count,
        "matched_papers": structured_paper_count if scope.get("topic") else None,
        "unknown_quality_ratio": _safe_ratio(counts["unknown_count"], structured_paper_count),
        "empty_abstract_ratio": _safe_ratio(counts["empty_abstract_count"], structured_paper_count),
        "single_source_ratio": _safe_ratio(max_source_count, source_total),
        "last_ingestion_time": last_ingestion_time,
        "last_analysis_time": last_analysis_time,
        "source_breakdown": source_counts,
        "quality_scope": counts["quality_scope"],
        "taxonomy_version": TAXONOMY_VERSION,
        "data_policy_version": DATA_POLICY_VERSION,
        "scope": scope,
    }
    warnings = build_warnings(metrics)
    warnings.extend(scope_warnings)

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


def get_overview_v01(repo: Any | None = None) -> dict[str, Any]:
    """Contract-compliant version of the legacy get_overview tool."""

    repo = repo or get_repository()
    venues = repo.get_all_venues()
    years = repo.get_all_years()
    return _response(
        data={
            "normalized_query": {},
            "total_papers": repo.get_paper_count(),
            "total_keywords": repo.get_total_keyword_count(),
            "total_venues": len(venues),
            "venues": venues,
            "years": years,
            "year_range": f"{min(years)}-{max(years)}" if years else "N/A",
        },
        source_layer="structured+analysis",
        evidence=[{"type": "legacy_wrapper", "tool": "get_overview"}],
        limit=1,
        offset=0,
        has_more=False,
    )


def get_status_v01(repo: Any | None = None) -> dict[str, Any]:
    """Contract-compliant version of the legacy get_status tool."""

    import os

    repo = repo or get_repository()
    db_path = repo.db_path
    years = repo.get_all_years()
    return _response(
        data={
            "normalized_query": {},
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
            "server_time": datetime.now().isoformat(),
        },
        source_layer="database+structured",
        evidence=[{"type": "legacy_wrapper", "tool": "get_status"}],
        limit=1,
        offset=0,
        has_more=False,
    )


def list_venues_v01(
    limit: int = 100,
    offset: int = 0,
    repo: Any | None = None,
) -> dict[str, Any]:
    """Contract-compliant version of the legacy list_venues tool."""

    repo = repo or get_repository()
    venue_names = repo.get_all_venues()
    venues = [
        {
            "name": venue,
            "paper_count": repo.get_paper_count(venue=venue),
            "years": repo.get_all_years(venue),
        }
        for venue in venue_names
    ]
    page, has_more = _paginate(venues, limit, offset)
    return _response(
        data={
            "normalized_query": {},
            "venues": page,
            "pagination": {
                "limit": limit,
                "offset": offset,
                "total": len(venues),
                "has_more": has_more,
            },
        },
        source_layer="structured",
        evidence=[{"type": "legacy_wrapper", "tool": "list_venues"}],
        limit=limit,
        offset=offset,
        has_more=has_more,
    )
