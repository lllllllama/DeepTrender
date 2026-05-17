"""Database repository tests."""

from datetime import datetime
from pathlib import Path

from scraper.models import RawPaper


class TestDatabaseRepository:

    def test_database_init(self, repo):
        with repo._get_connection() as conn:
            cursor = conn.execute("SELECT name FROM sqlite_master WHERE type='table'")
            tables = [row[0] for row in cursor.fetchall()]

        assert "papers" in tables
        assert "paper_keywords" in tables
        assert "raw_papers" in tables

    def test_schema_text_is_clean_utf8(self):
        schema_path = Path(__file__).parents[1] / "src" / "database" / "schema.sql"
        schema = schema_path.read_text(encoding="utf-8")

        assert "Raw -> Structured -> Analysis" in schema
        assert "鈫" not in schema
        assert "鏂" not in schema
        assert "CREATE INDEX IF NOT EXISTS idx_papers_domain" in schema
        assert "CREATE INDEX IF NOT EXISTS idx_trend_cache_keyword_year" in schema

    def test_database_indexes_created(self, repo):
        with repo._get_connection() as conn:
            cursor = conn.execute("SELECT name FROM sqlite_master WHERE type='index'")
            indexes = {row[0] for row in cursor.fetchall()}

        assert {
            "idx_papers_domain",
            "idx_trend_cache_keyword_year",
            "idx_paper_keywords_keyword_paper",
        }.issubset(indexes)

    def test_save_paper(self, repo, sample_paper):
        sample_paper.extracted_keywords = ["test keyword"]
        result = repo.save_paper(sample_paper)
        assert result is True

    def test_get_paper(self, repo, sample_paper):
        sample_paper.extracted_keywords = ["deep learning"]
        repo.save_paper(sample_paper)

        paper_ids = repo.get_papers_by_venue_year("ICLR", 2024)
        assert len(paper_ids) == 1
        retrieved = repo.get_paper(paper_ids[0].paper_id)

        assert retrieved is not None
        assert retrieved.title == sample_paper.title
        assert retrieved.venue == sample_paper.venue
        assert retrieved.year == sample_paper.year

    def test_get_paper_not_found(self, repo):
        assert repo.get_paper("non_existent_id") is None

    def test_save_papers_batch(self, repo, sample_papers):
        for paper in sample_papers:
            paper.extracted_keywords = ["machine learning"]

        saved_count = repo.save_papers(sample_papers)
        assert saved_count == len(sample_papers)

    def test_get_paper_count(self, repo_with_data):
        assert repo_with_data.get_paper_count() == 3

    def test_get_paper_count_by_venue(self, repo_with_data):
        assert repo_with_data.get_paper_count(venue="ICLR") == 2
        assert repo_with_data.get_paper_count(venue="NeurIPS") == 1

    def test_get_paper_count_by_year(self, repo_with_data):
        assert repo_with_data.get_paper_count(year=2023) == 2
        assert repo_with_data.get_paper_count(year=2024) == 1

    def test_get_top_keywords(self, repo_with_data):
        keywords = repo_with_data.get_top_keywords(limit=10)
        assert isinstance(keywords, list)
        assert len(keywords) > 0
        for kw, count in keywords:
            assert isinstance(kw, str)
            assert isinstance(count, int)
            assert count > 0

    def test_get_top_keywords_by_venue(self, repo_with_data):
        keywords = repo_with_data.get_top_keywords(venue="ICLR", limit=10)
        assert isinstance(keywords, list)

    def test_get_total_keyword_count(self, repo_with_data):
        assert repo_with_data.get_total_keyword_count() == 9
        assert repo_with_data.get_total_keyword_count(venue="ICLR") == 8
        assert repo_with_data.get_total_keyword_count(venue="NeurIPS") == 4

    def test_get_keyword_trend(self, repo_with_data):
        trend = repo_with_data.get_keyword_trend("transformer")
        assert isinstance(trend, dict)
        for year, count in trend.items():
            assert isinstance(year, int)
            assert isinstance(count, int)

    def test_get_all_venues(self, repo_with_data):
        venues = repo_with_data.get_all_venues()
        assert isinstance(venues, list)
        assert "ICLR" in venues
        assert "NeurIPS" in venues

    def test_get_all_years(self, repo_with_data):
        years = repo_with_data.get_all_years()
        assert isinstance(years, list)
        assert 2023 in years
        assert 2024 in years

    def test_get_all_years_by_venue(self, repo_with_data):
        iclr_years = repo_with_data.get_all_years(venue="ICLR")
        assert isinstance(iclr_years, list)
        assert 2023 in iclr_years
        assert 2024 in iclr_years

    def test_get_papers_by_venue_year(self, repo_with_data):
        papers = repo_with_data.get_papers_by_venue_year("ICLR", 2024)
        assert isinstance(papers, list)
        assert len(papers) == 1
        assert papers[0].venue == "ICLR"
        assert papers[0].year == 2024

    def test_save_duplicate_paper(self, repo, sample_paper):
        sample_paper.extracted_keywords = ["keyword1"]
        repo.save_paper(sample_paper)

        sample_paper.extracted_keywords = ["keyword2"]
        result = repo.save_paper(sample_paper)

        assert result is True
        assert repo.get_paper_count() == 1

    def test_get_venue_comparison(self, repo_with_data):
        comparison = repo_with_data.get_venue_comparison(year=2023, limit=5)
        assert isinstance(comparison, dict)
        assert "ICLR" in comparison or "NeurIPS" in comparison

    def test_get_arxiv_stats(self, repo):
        repo.raw.save_raw_paper(
            RawPaper(
                source="arxiv",
                source_paper_id="2401.00001",
                title="Test arXiv Paper",
                categories="cs.LG cs.CL",
                year=2024,
                retrieved_at=datetime(2024, 1, 2, 3, 4, 5),
            )
        )

        stats = repo.get_arxiv_stats()

        assert stats["total_papers"] == 1
        assert stats["categories"]["cs.LG"] == 1
        assert stats["categories"]["cs.CL"] == 1
        assert stats["categories"]["cs.CV"] == 0
        assert stats["date_range"]["min"] is not None
        assert stats["date_range"]["max"] is not None
