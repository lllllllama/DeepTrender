"""Frontend-ready v0.1 view builders."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from database import get_repository
from taxonomy.loader import load_topics

from . import mcp_views


def _data_updated_at() -> str:
    return datetime.now().isoformat()


def build_domain_overview_view(domain: str) -> dict[str, Any]:
    topics_response = mcp_views.list_topics(domain=domain)
    quality_response = mcp_views.get_data_quality_report()
    return {
        "view": "domain_overview",
        "domain": domain,
        "topics": topics_response["data"]["topics"],
        "primary_metric": "relative_frequency",
        "secondary_metric": "count",
        "warnings": quality_response["warnings"],
        "data_updated_at": _data_updated_at(),
        "source_scope": "taxonomy+quality",
    }


def build_topic_page_view(topic_id: str) -> dict[str, Any]:
    topic = load_topics().get(topic_id)
    return {
        "view": "topic_page",
        "topic_id": topic_id,
        "topic": topic,
        "primary_metric": "relative_frequency",
        "secondary_metric": "count",
        "warnings": [] if topic else [{"code": "topic_not_found", "message": "Topic not found."}],
        "data_updated_at": _data_updated_at(),
        "source_scope": "taxonomy",
    }


def build_venue_year_topic_view(
    venue: str,
    year: int,
    topic: str,
    repo: Any | None = None,
) -> dict[str, Any]:
    response = mcp_views.get_venue_year_topic(venue, year, topic, repo=repo)
    return {
        "view": "venue_year_topic",
        "primary_metric": "relative_frequency",
        "secondary_metric": "count",
        "data": response["data"],
        "warnings": response["warnings"],
        "data_updated_at": response["meta"]["generated_at"],
        "source_scope": response["meta"]["source_layer"],
    }


def build_venue_topic_chart_view(
    venue: str,
    topic_id: str,
    repo: Any | None = None,
) -> dict[str, Any]:
    repo = repo or get_repository()
    years = sorted(repo.get_all_years(venue))
    topic = load_topics().get(topic_id, {})
    relative_frequency: list[float] = []
    counts: list[int] = []
    warnings: list[dict] = []

    for year in years:
        response = mcp_views.get_venue_year_topic(venue, year, topic_id, repo=repo)
        relative_frequency.append(response["data"]["relative_frequency"])
        counts.append(response["data"]["matched_papers"])
        warnings.extend(response["warnings"])

    return {
        "view": "venue_topic_chart",
        "chart_type": "line",
        "primary_metric": "relative_frequency",
        "x": [str(year) for year in years],
        "series": [
            {
                "name": topic.get("canonical_name", topic_id),
                "relative_frequency": relative_frequency,
                "count": counts,
            }
        ],
        "warnings": warnings,
        "data_updated_at": _data_updated_at(),
        "source_scope": "taxonomy+structured+analysis",
    }
