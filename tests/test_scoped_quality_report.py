"""Scoped data quality report tests."""

from datetime import datetime

from scraper.models import RawPaper, create_legacy_paper
from services import mcp_views
from services.topic_facts import rebuild_paper_topics


def _warning_codes(response):
    return {warning["code"] for warning in response["warnings"]}


def test_global_quality_report_still_works(repo_with_data):
    response = mcp_views.get_data_quality_report(repo=repo_with_data)

    assert response["data"]["metrics"]["structured_paper_count"] == 3
    assert response["data"]["metrics"]["scope"] == {}


def test_venue_year_scoped_quality_report(repo_with_data):
    response = mcp_views.get_data_quality_report(
        scope={"venue": "ICLR", "year": 2023},
        repo=repo_with_data,
    )

    metrics = response["data"]["metrics"]
    assert metrics["structured_paper_count"] == 1
    assert metrics["quality_scope"]["unknown"] == 1


def test_topic_scoped_quality_report(repo_with_data):
    rebuild_paper_topics(repo=repo_with_data)
    response = mcp_views.get_data_quality_report(
        scope={"topic": "transformer"},
        repo=repo_with_data,
    )

    metrics = response["data"]["metrics"]
    assert metrics["matched_papers"] >= 2
    assert metrics["taxonomy_version"]


def test_scoped_unknown_and_empty_abstract_thresholds(repo):
    paper = create_legacy_paper(
        id="quality_001",
        title="Transformer Quality",
        abstract="",
        authors=["A"],
        venue="ICLR",
        year=2024,
        url="https://example.com/q",
        keywords=["transformer"],
    )
    repo.save_paper(paper)

    response = mcp_views.get_data_quality_report(
        scope={"venue": "ICLR", "year": 2024},
        repo=repo,
    )
    codes = _warning_codes(response)

    assert "unknown_quality_ratio_high" in codes
    assert "empty_abstract_ratio_high" in codes


def test_scoped_single_source_threshold(repo):
    papers = []
    for index in range(2):
        paper = create_legacy_paper(
            id=f"source_{index}",
            title=f"Transformer Source {index}",
            abstract="A transformer paper.",
            authors=["A"],
            venue="ICLR",
            year=2024,
            url=f"https://example.com/source/{index}",
            keywords=["transformer"],
        )
        repo.save_paper(paper)
        raw_id = repo.raw.save_raw_paper(
            RawPaper(
                source="arxiv",
                source_paper_id=f"2401.0000{index}",
                title=paper.title,
                abstract=paper.abstract,
                authors=paper.authors,
                year=2024,
                categories="cs.LG",
                retrieved_at=datetime(2024, 1, 1),
            )
        )
        repo.structured.link_paper_source(paper.paper_id, raw_id, "arxiv")
        papers.append(paper)

    response = mcp_views.get_data_quality_report(
        scope={"venue": "ICLR", "year": 2024},
        repo=repo,
    )

    assert "single_source_ratio_high" in _warning_codes(response)


def test_unsupported_metric_returns_warning(repo_with_data):
    response = mcp_views.get_data_quality_report(scope={"domain": "CV"}, repo=repo_with_data)

    assert response["data"]["metrics"]["raw_paper_count"] is None
    assert "metric_not_available_for_scope" in _warning_codes(response)
