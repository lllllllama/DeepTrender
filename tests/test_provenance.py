"""Provenance service tests."""

from datetime import datetime

from scraper.models import RawPaper, create_legacy_paper
from services import mcp_views
from services.topic_facts import rebuild_paper_topics


def _assert_contract(response):
    assert set(response) == {"data", "meta", "warnings", "evidence"}
    for key in (
        "taxonomy_version",
        "data_policy_version",
        "generated_at",
        "source_layer",
        "limit",
        "offset",
        "has_more",
    ):
        assert key in response["meta"]


def test_get_paper_provenance_includes_paper_sources_topics_and_warnings(repo):
    paper = create_legacy_paper(
        id="prov_001",
        title="Transformer Models",
        abstract="A transformer paper.",
        authors=["A"],
        venue="ICLR",
        year=2024,
        url="https://example.com/prov",
        keywords=["transformer"],
    )
    repo.save_paper(paper)
    raw_id = repo.raw.save_raw_paper(
        RawPaper(
            source="openreview",
            source_paper_id="or-prov",
            title=paper.title,
            abstract=paper.abstract,
            authors=paper.authors,
            year=2024,
            venue_raw="ICLR",
            retrieved_at=datetime(2024, 1, 1),
        )
    )
    repo.structured.link_paper_source(paper.paper_id, raw_id, "openreview", confidence=0.95)
    rebuild_paper_topics(repo=repo)

    response = mcp_views.get_paper_provenance(paper.paper_id, repo=repo)
    _assert_contract(response)

    assert response["data"]["paper"]["paper_id"] == paper.paper_id
    assert response["data"]["sources"]
    assert response["data"]["sources"][0]["source"] == "openreview"
    assert response["data"]["sources"][0]["source_url"] is None
    assert response["data"]["topics"]
    assert any(topic["topic_id"] == "transformer" for topic in response["data"]["topics"])
    assert "source_url_unavailable" in {warning["code"] for warning in response["warnings"]}


def test_get_paper_provenance_source_list_present_when_missing(repo):
    paper = create_legacy_paper(
        id="prov_002",
        title="LLM Paper",
        abstract="An LLM paper.",
        authors=["A"],
        venue="ICLR",
        year=2024,
        url="https://example.com/prov2",
        keywords=["llm"],
    )
    repo.save_paper(paper)
    rebuild_paper_topics(repo=repo)

    response = mcp_views.get_paper_provenance(paper.paper_id, repo=repo)
    _assert_contract(response)

    assert "sources" in response["data"]
    assert response["data"]["sources"] == []
    assert "topics" in response["data"]
    assert "source_links_unavailable" in {warning["code"] for warning in response["warnings"]}
