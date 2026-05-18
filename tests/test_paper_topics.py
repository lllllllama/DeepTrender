"""Persistent paper-topic fact layer tests."""

from datetime import datetime

from scraper.models import RawPaper, create_legacy_paper
from services import mcp_views
from services.topic_facts import rebuild_paper_topics
from taxonomy.loader import TAXONOMY_VERSION


def test_paper_topics_table_exists(repo):
    with repo._get_connection() as conn:
        cursor = conn.execute("SELECT name FROM sqlite_master WHERE type='table'")
        tables = {row[0] for row in cursor.fetchall()}
    assert "paper_topics" in tables


def test_rebuild_topic_facts_persists_matches(repo):
    paper = create_legacy_paper(
        id="transformer_001",
        title="Attention Is All You Need",
        abstract="The Transformer architecture uses attention mechanisms.",
        authors=["A"],
        venue="NeurIPS",
        year=2023,
        url="https://example.com/t",
        keywords=["transformer"],
    )
    repo.save_paper(paper)

    summary = rebuild_paper_topics(repo=repo)
    topics = repo.get_paper_topics(paper.paper_id)

    assert summary["processed_papers"] == 1
    assert summary["matched_papers"] == 1
    assert any(topic["topic_id"] == "transformer" for topic in topics)
    assert all(topic["taxonomy_version"] == TAXONOMY_VERSION for topic in topics)


def test_llm_alias_maps_to_large_language_model(repo):
    paper = create_legacy_paper(
        id="llm_001",
        title="LLM Agents for Planning",
        abstract="We evaluate language model agents.",
        authors=["A"],
        venue="ICLR",
        year=2024,
        url="https://example.com/llm",
        keywords=["llm"],
    )
    repo.save_paper(paper)
    rebuild_paper_topics(repo=repo)

    topics = repo.get_paper_topics(paper.paper_id)
    assert any(topic["topic_id"] == "large_language_model" for topic in topics)


def test_child_topics_are_not_added_by_default(repo):
    paper = create_legacy_paper(
        id="seg_001",
        title="Segmentation for Medical Images",
        abstract="This paper studies image segmentation.",
        authors=["A"],
        venue="CVPR",
        year=2020,
        url="https://example.com/seg",
        keywords=["segmentation"],
    )
    repo.save_paper(paper)
    rebuild_paper_topics(repo=repo, include_children=False)

    topic_ids = {topic["topic_id"] for topic in repo.get_paper_topics(paper.paper_id)}
    assert "segmentation" in topic_ids
    assert "panoptic_segmentation" not in topic_ids


def test_get_venue_year_topic_prefers_persisted_facts(repo):
    paper = create_legacy_paper(
        id="persisted_001",
        title="Transformer Models",
        abstract="A transformer paper.",
        authors=["A"],
        venue="ICLR",
        year=2024,
        url="https://example.com/persisted",
        keywords=["transformer"],
    )
    repo.save_paper(paper)
    raw_id = repo.raw.save_raw_paper(
        RawPaper(
            source="openreview",
            source_paper_id="or-1",
            title=paper.title,
            abstract=paper.abstract,
            authors=paper.authors,
            year=2024,
            venue_raw="ICLR",
            retrieved_at=datetime(2024, 1, 1),
        )
    )
    repo.structured.link_paper_source(paper.paper_id, raw_id, "openreview", confidence=1.0)
    rebuild_paper_topics(repo=repo)

    response = mcp_views.get_venue_year_topic("ICLR", 2024, "transformer", repo=repo)
    warning_codes = {warning["code"] for warning in response["warnings"]}

    assert response["meta"]["source_layer"] == "paper_topics+structured+analysis"
    assert response["data"]["matched_papers"] == 1
    assert "runtime_topic_matching_fallback" not in warning_codes


def test_get_venue_year_topic_runtime_fallback_when_facts_missing(repo_with_data):
    response = mcp_views.get_venue_year_topic("ICLR", 2023, "transformer", repo=repo_with_data)
    warning_codes = {warning["code"] for warning in response["warnings"]}

    assert response["data"]["matched_papers"] == 1
    assert "runtime_topic_matching_fallback" in warning_codes
