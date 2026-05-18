"""Build and persist canonical paper-topic facts."""

from __future__ import annotations

from typing import Any

from database import get_repository
from scraper.models import Paper
from taxonomy.loader import TAXONOMY_VERSION, load_topics
from taxonomy.resolver import match_paper_topics, resolve_topic


def _paper_keywords(paper: Paper, repo: Any | None = None) -> list[str]:
    keywords = set(paper.keywords or [])
    keywords.update(paper.extracted_keywords or [])
    if repo is not None and paper.paper_id:
        try:
            keywords.update(item.keyword for item in repo.analysis.get_paper_keywords(paper.paper_id))
        except Exception:
            pass
    return sorted(keyword for keyword in keywords if keyword)


def _save_shape(
    paper_id: int,
    match: dict[str, Any],
    taxonomy_version: str,
) -> dict[str, Any]:
    evidence_keyword = None
    if match.get("aliases_used"):
        evidence_keyword = match["aliases_used"][0]
    elif match.get("canonical_topic"):
        evidence_keyword = match["canonical_topic"]

    return {
        "paper_id": paper_id,
        "topic_id": match["topic_id"],
        "canonical_topic": match["canonical_topic"],
        "domain": match.get("domain"),
        "match_method": match["match_method"],
        "confidence": match["confidence"],
        "evidence_keyword": evidence_keyword,
        "evidence_source": match["match_method"],
        "taxonomy_version": taxonomy_version,
    }


def _expanded_child_matches(match: dict[str, Any], taxonomy_version: str) -> list[dict[str, Any]]:
    topic_id = match.get("topic_id")
    if not topic_id:
        return []
    resolved = resolve_topic(topic_id, include_children=True)
    child_ids = resolved.get("child_topic_ids", [])
    topics = load_topics()
    expanded = []
    for child_id in child_ids:
        child = topics.get(child_id)
        if not child:
            continue
        expanded.append(
            {
                "topic_id": child_id,
                "canonical_topic": child["canonical_name"],
                "domain": child.get("domain"),
                "secondary_domains": child.get("secondary_domains", []),
                "match_method": "parent_include_children",
                "confidence": match["confidence"],
                "aliases_used": [],
                "warnings": [],
                "taxonomy_version": taxonomy_version,
            }
        )
    return expanded


def build_paper_topic_matches(
    paper: Paper,
    repo: Any | None = None,
    include_children: bool = False,
) -> list[dict]:
    """Return canonical topic matches for one structured paper."""

    repo = repo or get_repository()
    if not paper.paper_id:
        return []

    matches = match_paper_topics(
        paper.title,
        paper.abstract,
        extracted_keywords=_paper_keywords(paper, repo),
        arxiv_categories=None,
    )

    if include_children:
        expanded = []
        for match in matches:
            expanded.extend(_expanded_child_matches(match, TAXONOMY_VERSION))
        matches.extend(expanded)

    deduped: dict[str, dict] = {}
    for match in matches:
        topic_id = match.get("topic_id")
        if not topic_id:
            continue
        current = deduped.get(topic_id)
        if current is None or match.get("confidence", 0) > current.get("confidence", 0):
            deduped[topic_id] = match

    return [
        _save_shape(paper.paper_id, match, TAXONOMY_VERSION)
        for match in sorted(deduped.values(), key=lambda item: item["topic_id"])
    ]


def rebuild_paper_topics(
    repo: Any | None = None,
    taxonomy_version: str | None = None,
    limit: int | None = None,
    include_children: bool = False,
) -> dict:
    """Rebuild persistent paper_topics from structured papers and keywords."""

    repo = repo or get_repository()
    taxonomy_version = taxonomy_version or TAXONOMY_VERSION
    warnings = []
    papers = repo.get_all_papers(limit=limit)
    if not papers:
        warnings.append(
            {
                "code": "no_structured_papers",
                "message": "No structured papers are available for topic fact rebuilding.",
                "severity": "low",
            }
        )

    repo.clear_paper_topics_for_taxonomy_version(taxonomy_version)
    processed_papers = 0
    matched_papers = 0
    topic_match_count = 0

    for paper in papers:
        processed_papers += 1
        matches = build_paper_topic_matches(
            paper,
            repo=repo,
            include_children=include_children,
        )
        for match in matches:
            match["taxonomy_version"] = taxonomy_version
        if matches:
            matched_papers += 1
            topic_match_count += len(repo.save_paper_topics(matches))

    return {
        "processed_papers": processed_papers,
        "matched_papers": matched_papers,
        "topic_match_count": topic_match_count,
        "taxonomy_version": taxonomy_version,
        "include_children": include_children,
        "warnings": warnings,
    }


def get_topic_fact_summary(
    topic_id: str,
    venue: str | None = None,
    year: int | None = None,
    repo: Any | None = None,
) -> dict:
    """Return persisted topic fact counts for a topic and optional scope."""

    repo = repo or get_repository()
    resolved = resolve_topic(topic_id)
    canonical_topic_id = resolved.get("topic_id") or topic_id
    rows = repo.get_topic_counts_by_venue_year(
        canonical_topic_id,
        venue=venue,
        year=year,
        taxonomy_version=TAXONOMY_VERSION,
    )
    total = sum(row["count"] for row in rows)
    warnings = []
    if repo.get_paper_topic_count(taxonomy_version=TAXONOMY_VERSION) == 0:
        warnings.append(
            {
                "code": "paper_topics_unavailable",
                "message": "paper_topics facts are unavailable for the current taxonomy version.",
                "severity": "medium",
            }
        )

    return {
        "topic_id": canonical_topic_id,
        "canonical_topic": resolved.get("canonical_topic"),
        "venue": venue,
        "year": year,
        "total": total,
        "counts": rows,
        "taxonomy_version": TAXONOMY_VERSION,
        "warnings": warnings,
    }
