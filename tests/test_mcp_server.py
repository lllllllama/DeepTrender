"""
MCP server tool function tests.

Tests the business logic of each MCP tool by calling the underlying
repository and analyzer functions directly (without starting the
MCP transport), using an in-memory/temp-file SQLite database.
"""

import sys
import tempfile
import importlib
from pathlib import Path
from datetime import datetime

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from scraper.models import RawPaper, create_legacy_paper
from database.repository import DatabaseRepository


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_repo(tmp_path: Path) -> DatabaseRepository:
    """Create a fresh DatabaseRepository backed by a temp SQLite file."""
    db_path = tmp_path / "test.db"
    return DatabaseRepository(db_path=db_path)


def _seed_papers(repo: DatabaseRepository):
    """Add a handful of structured papers so keyword queries return data."""
    papers = [
        create_legacy_paper(
            id="p1",
            title="Attention Is All You Need",
            abstract="Transformer architecture based on attention.",
            authors=["Vaswani"],
            venue="NeurIPS",
            year=2023,
            url="https://example.com/1",
            keywords=["transformer", "attention"],
        ),
        create_legacy_paper(
            id="p2",
            title="BERT Language Model",
            abstract="Pre-training of bidirectional transformers.",
            authors=["Devlin"],
            venue="ICLR",
            year=2023,
            url="https://example.com/2",
            keywords=["bert", "language model", "transformer"],
        ),
        create_legacy_paper(
            id="p3",
            title="Diffusion Models for Image Generation",
            abstract="Score-based diffusion model for image synthesis.",
            authors=["Ho"],
            venue="ICLR",
            year=2024,
            url="https://example.com/3",
            keywords=["diffusion", "image generation"],
        ),
    ]
    for p in papers:
        p.extracted_keywords = ["deep learning", "neural network"]
        repo.save_paper(p)
    return papers


def _seed_raw_arxiv(repo: DatabaseRepository):
    """Add a couple of raw arXiv papers for raw-layer tests."""
    papers = [
        RawPaper(
            source="arxiv",
            source_paper_id="2401.00001",
            title="LLM Scaling Laws",
            abstract="We study scaling laws for large language models.",
            authors=["Smith"],
            year=2024,
            categories="cs.LG cs.CL",
            published_at=datetime(2024, 1, 10),
            retrieved_at=datetime(2024, 1, 11),
        ),
        RawPaper(
            source="arxiv",
            source_paper_id="2401.00002",
            title="Vision Transformers",
            abstract="Applying transformers to computer vision.",
            authors=["Doe"],
            year=2024,
            categories="cs.CV cs.LG",
            published_at=datetime(2024, 2, 5),
            retrieved_at=datetime(2024, 2, 6),
        ),
    ]
    for p in papers:
        repo.raw.save_raw_paper(p)
    return papers


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def tmp_repo(tmp_path):
    repo = _make_repo(tmp_path)
    _seed_papers(repo)
    _seed_raw_arxiv(repo)
    return repo


@pytest.fixture(autouse=True)
def _patch_mcp_repo(tmp_repo, monkeypatch):
    """Patch the MCP server module's _repo singleton so all tools use the
    temp database instead of the real one."""
    import mcp_server as ms
    monkeypatch.setattr(ms, "_repo", tmp_repo)


# ---------------------------------------------------------------------------
# Tests – overview & status
# ---------------------------------------------------------------------------

class TestGetOverview:
    def test_returns_required_keys(self):
        import mcp_server as ms
        result = ms.get_overview()
        for key in ("total_papers", "total_keywords", "total_venues", "venues", "years", "year_range"):
            assert key in result

    def test_counts_are_non_negative(self):
        import mcp_server as ms
        result = ms.get_overview()
        assert result["total_papers"] >= 0
        assert result["total_keywords"] >= 0
        assert result["total_venues"] >= 0

    def test_venues_is_list(self):
        import mcp_server as ms
        result = ms.get_overview()
        assert isinstance(result["venues"], list)

    def test_years_is_list(self):
        import mcp_server as ms
        result = ms.get_overview()
        assert isinstance(result["years"], list)

    def test_seeded_papers_counted(self):
        import mcp_server as ms
        result = ms.get_overview()
        # 3 seeded papers
        assert result["total_papers"] == 3
        assert result["total_venues"] == 2  # NeurIPS + ICLR


class TestGetStatus:
    def test_returns_required_keys(self):
        import mcp_server as ms
        result = ms.get_status()
        assert "database" in result
        assert "data" in result
        assert "server_time" in result

    def test_database_has_path(self):
        import mcp_server as ms
        result = ms.get_status()
        assert "path" in result["database"]

    def test_data_has_total_papers(self):
        import mcp_server as ms
        result = ms.get_status()
        assert "total_papers" in result["data"]


# ---------------------------------------------------------------------------
# Tests – venue statistics
# ---------------------------------------------------------------------------

class TestListVenues:
    def test_returns_list(self):
        import mcp_server as ms
        result = ms.list_venues()
        assert isinstance(result, list)

    def test_venue_entry_has_required_keys(self):
        import mcp_server as ms
        result = ms.list_venues()
        assert len(result) > 0
        entry = result[0]
        assert "name" in entry
        assert "paper_count" in entry
        assert "years" in entry

    def test_iclr_present(self):
        import mcp_server as ms
        result = ms.list_venues()
        names = [v["name"] for v in result]
        assert "ICLR" in names


class TestGetVenueDetail:
    def test_iclr_detail(self):
        import mcp_server as ms
        result = ms.get_venue_detail("ICLR")
        assert result["venue"] == "ICLR"
        assert result["total_papers"] == 2
        assert isinstance(result["yearly_stats"], list)
        assert len(result["yearly_stats"]) > 0

    def test_unknown_venue_returns_empty_yearly_stats(self):
        import mcp_server as ms
        result = ms.get_venue_detail("UNKNOWN_VENUE_XYZ")
        # years is empty for an unknown venue, so yearly_stats must also be empty
        assert result["yearly_stats"] == []
        assert result["years"] == []

    def test_yearly_stats_structure(self):
        import mcp_server as ms
        result = ms.get_venue_detail("ICLR")
        for entry in result["yearly_stats"]:
            assert "year" in entry
            assert "paper_count" in entry
            assert "top_keywords" in entry
            assert isinstance(entry["top_keywords"], list)


class TestGetVenueComparison:
    def test_returns_required_keys(self):
        import mcp_server as ms
        result = ms.get_venue_comparison()
        assert "year" in result
        assert "venues" in result

    def test_venues_is_dict(self):
        import mcp_server as ms
        result = ms.get_venue_comparison()
        assert isinstance(result["venues"], dict)

    def test_specific_year(self):
        import mcp_server as ms
        result = ms.get_venue_comparison(year=2023)
        assert result["year"] == 2023
        assert "NeurIPS" in result["venues"] or "ICLR" in result["venues"]

    def test_limit_respected(self):
        import mcp_server as ms
        result = ms.get_venue_comparison(year=2023, limit=3)
        for kws in result["venues"].values():
            assert len(kws) <= 3


# ---------------------------------------------------------------------------
# Tests – keyword queries
# ---------------------------------------------------------------------------

class TestGetTopKeywords:
    def test_returns_list(self):
        import mcp_server as ms
        result = ms.get_top_keywords()
        assert isinstance(result, list)

    def test_each_entry_has_keyword_and_count(self):
        import mcp_server as ms
        result = ms.get_top_keywords(limit=10)
        for entry in result:
            assert "keyword" in entry
            assert "count" in entry
            assert isinstance(entry["count"], int)

    def test_limit_enforced(self):
        import mcp_server as ms
        result = ms.get_top_keywords(limit=2)
        assert len(result) <= 2

    def test_venue_filter(self):
        import mcp_server as ms
        result = ms.get_top_keywords(venue="ICLR")
        # Should have keywords; transformer appears in both ICLR papers
        assert isinstance(result, list)

    def test_year_filter(self):
        import mcp_server as ms
        result = ms.get_top_keywords(year=2024)
        assert isinstance(result, list)


class TestGetKeywordTrends:
    def test_returns_list(self):
        import mcp_server as ms
        result = ms.get_keyword_trends(["transformer"])
        assert isinstance(result, list)
        assert len(result) == 1

    def test_entry_structure(self):
        import mcp_server as ms
        result = ms.get_keyword_trends(["transformer"])
        entry = result[0]
        assert entry["keyword"] == "transformer"
        assert isinstance(entry["years"], list)
        assert isinstance(entry["counts"], list)
        assert len(entry["years"]) == len(entry["counts"])

    def test_multiple_keywords(self):
        import mcp_server as ms
        result = ms.get_keyword_trends(["transformer", "diffusion"])
        assert len(result) == 2
        kws = {r["keyword"] for r in result}
        assert "transformer" in kws
        assert "diffusion" in kws

    def test_empty_keywords_uses_defaults(self):
        import mcp_server as ms
        result = ms.get_keyword_trends([])
        assert isinstance(result, list)
        # should auto-pick top keywords

    def test_venue_filter(self):
        import mcp_server as ms
        result = ms.get_keyword_trends(["transformer"], venue="ICLR")
        assert isinstance(result, list)


class TestGetKeywordWordcloud:
    def test_returns_list(self):
        import mcp_server as ms
        result = ms.get_keyword_wordcloud()
        assert isinstance(result, list)

    def test_entry_has_name_and_value(self):
        import mcp_server as ms
        result = ms.get_keyword_wordcloud(limit=10)
        for entry in result:
            assert "name" in entry
            assert "value" in entry

    def test_limit_enforced(self):
        import mcp_server as ms
        result = ms.get_keyword_wordcloud(limit=2)
        assert len(result) <= 2


# ---------------------------------------------------------------------------
# Tests – arXiv-specific
# ---------------------------------------------------------------------------

class TestGetArxivTimeseries:
    def test_returns_list(self):
        import mcp_server as ms
        result = ms.get_arxiv_timeseries(granularity="year", category="ALL")
        assert isinstance(result, list)

    def test_invalid_granularity_returns_error(self):
        import mcp_server as ms
        result = ms.get_arxiv_timeseries(granularity="decade")
        assert len(result) == 1
        assert "error" in result[0]

    def test_empty_when_no_analysis_run(self):
        import mcp_server as ms
        # analysis pipeline has not run on this temp DB → cache is empty
        result = ms.get_arxiv_timeseries(granularity="month")
        assert result == []


class TestGetArxivStats:
    def test_returns_required_keys(self):
        import mcp_server as ms
        result = ms.get_arxiv_stats()
        assert "total_papers" in result
        assert "categories" in result
        assert "date_range" in result

    def test_total_papers_counts_raw(self):
        import mcp_server as ms
        result = ms.get_arxiv_stats()
        # We seeded 2 arXiv raw papers
        assert result["total_papers"] == 2

    def test_custom_categories(self):
        import mcp_server as ms
        result = ms.get_arxiv_stats(categories=["cs.LG"])
        assert "cs.LG" in result["categories"]
        # Both seeded papers have cs.LG
        assert result["categories"]["cs.LG"] == 2

    def test_date_range_present(self):
        import mcp_server as ms
        result = ms.get_arxiv_stats()
        assert "min" in result["date_range"]
        assert "max" in result["date_range"]


class TestGetArxivEmerging:
    def test_returns_list(self):
        import mcp_server as ms
        result = ms.get_arxiv_emerging()
        assert isinstance(result, list)

    def test_limit_respected(self):
        import mcp_server as ms
        result = ms.get_arxiv_emerging(limit=5)
        assert len(result) <= 5


# ---------------------------------------------------------------------------
# Tests – intermediate / raw data
# ---------------------------------------------------------------------------

class TestGetAnalysisMeta:
    def test_returns_dict(self):
        import mcp_server as ms
        result = ms.get_analysis_meta()
        assert isinstance(result, dict)


class TestGetVenueSummaries:
    def test_returns_list(self):
        import mcp_server as ms
        result = ms.get_venue_summaries()
        assert isinstance(result, list)

    def test_venue_filter(self):
        import mcp_server as ms
        result = ms.get_venue_summaries(venue="ICLR")
        for entry in result:
            assert entry["venue"] == "ICLR"

    def test_year_filter(self):
        import mcp_server as ms
        result = ms.get_venue_summaries(year=2023)
        for entry in result:
            assert entry.get("year") == 2023


class TestGetKeywordTrendCached:
    def test_returns_list(self):
        import mcp_server as ms
        result = ms.get_keyword_trend_cached(
            scope="venue", keyword="transformer", granularity="year"
        )
        assert isinstance(result, list)

    def test_each_entry_has_bucket_and_count(self):
        import mcp_server as ms
        result = ms.get_keyword_trend_cached(
            scope="arxiv", keyword="llm", granularity="month"
        )
        for entry in result:
            assert "bucket" in entry
            assert "count" in entry


class TestGetRawPaperCount:
    def test_total_count(self):
        import mcp_server as ms
        result = ms.get_raw_paper_count()
        assert result["source"] == "all"
        assert result["count"] == 2  # two seeded raw arXiv papers

    def test_arxiv_source_count(self):
        import mcp_server as ms
        result = ms.get_raw_paper_count(source="arxiv")
        assert result["source"] == "arxiv"
        assert result["count"] == 2

    def test_unknown_source_returns_zero(self):
        import mcp_server as ms
        result = ms.get_raw_paper_count(source="unknown_source")
        assert result["count"] == 0


class TestGetScrapeLog:
    def test_no_scrape_yet(self):
        import mcp_server as ms
        result = ms.get_scrape_log("ICLR", 2024)
        assert result["venue"] == "ICLR"
        assert result["year"] == 2024
        assert result["last_scraped"] is None
        assert result["should_scrape"] is True


class TestListConfiguredVenues:
    def test_returns_list(self):
        import mcp_server as ms
        result = ms.list_configured_venues()
        assert isinstance(result, list)
        assert len(result) > 0

    def test_entry_structure(self):
        import mcp_server as ms
        result = ms.list_configured_venues()
        for entry in result:
            assert "key" in entry
            assert "name" in entry
            assert "full_name" in entry
            assert "venue_id_pattern" in entry
            assert "years" in entry

    def test_iclr_in_list(self):
        import mcp_server as ms
        result = ms.list_configured_venues()
        keys = [v["key"] for v in result]
        assert "ICLR" in keys
