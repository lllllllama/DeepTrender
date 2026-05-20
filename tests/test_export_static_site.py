"""
Tests for static site export functionality
"""

import pytest
import json
import tempfile
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from tools.export_static_site import StaticSiteExporter


class TestStaticSiteExporter:
    
    @pytest.fixture
    def temp_output_dir(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            yield Path(tmpdir)
    
    @pytest.fixture
    def exporter(self, temp_output_dir, repo_with_data):
        return StaticSiteExporter(
            output_dir=str(temp_output_dir),
            top_keywords=50,
            repository=repo_with_data,
        )
    
    def test_exporter_initialization(self, exporter, temp_output_dir):
        assert exporter.output_dir == temp_output_dir
        assert exporter.data_dir.exists()
        assert exporter.venues_data_dir.exists()
        assert exporter.arxiv_data_dir.exists()
        assert exporter.top_keywords == 50
    
    def test_export_venues_index(self, exporter):
        count = exporter.export_venues_index()
        assert count > 0
        
        venues_file = exporter.venues_data_dir / "venues_index.json"
        assert venues_file.exists()
        
        with open(venues_file, 'r', encoding='utf-8') as f:
            venues_data = json.load(f)
        
        assert isinstance(venues_data, list)
        assert len(venues_data) > 0
        
        venue = venues_data[0]
        assert "name" in venue
        assert "full_name" in venue
        assert "domain" in venue
        assert "tier" in venue
        assert "years_available" in venue
        assert "paper_count" in venue
        assert "top_keywords" in venue
    
    def test_export_venue_top_keywords(self, exporter, repo_with_data):
        venue_name = "ICLR"
        result = exporter.export_venue_top_keywords(venue_name, top_n=10)
        assert result is True
        
        output_file = exporter.venues_data_dir / f"venue_{venue_name}_top_keywords.json"
        assert output_file.exists()
        
        with open(output_file, 'r', encoding='utf-8') as f:
            data = json.load(f)
        
        assert isinstance(data, dict)
        
        for year, keywords in data.items():
            assert year.isdigit()
            assert isinstance(keywords, list)
            
            for item in keywords:
                assert "keyword" in item
                assert "count" in item
                assert "rank" in item
                assert isinstance(item["rank"], int)
                assert item["rank"] > 0
    
    def test_export_venue_keyword_trends(self, exporter, repo_with_data):
        venue_name = "ICLR"
        result = exporter.export_venue_keyword_trends(venue_name, max_keywords=20)
        assert result is True
        
        output_file = exporter.venues_data_dir / f"venue_{venue_name}_keyword_trends.json"
        assert output_file.exists()
        
        with open(output_file, 'r', encoding='utf-8') as f:
            data = json.load(f)
        
        assert isinstance(data, dict)
        assert len(data) <= 20
        
        for keyword, trend in data.items():
            assert isinstance(keyword, str)
            assert isinstance(trend, list)
            
            for point in trend:
                assert "year" in point
                assert "count" in point
                assert "rank" in point
    
    def test_export_creates_directory_structure(self, exporter):
        exporter.export_all_venues()
        
        assert exporter.output_dir.exists()
        assert exporter.data_dir.exists()
        assert exporter.venues_data_dir.exists()
        assert exporter.arxiv_data_dir.exists()

    def test_exported_venues_index_matches_detail_artifacts(self, exporter):
        result = exporter.export_all_venues()

        venues_file = exporter.venues_data_dir / "venues_index.json"
        with open(venues_file, 'r', encoding='utf-8') as f:
            venues_data = json.load(f)

        names = {venue["name"] for venue in venues_data}
        assert names == set(result["venues_exported"])
        assert names == {"ICLR", "NeurIPS"}

        for venue in venues_data:
            assert venue["years_available"]
            assert (exporter.venues_data_dir / f"venue_{venue['name']}_top_keywords.json").exists()
            assert (exporter.venues_data_dir / f"venue_{venue['name']}_keyword_trends.json").exists()

    def test_export_global_static_trend_files(self, exporter):
        exporter.export_all_venues()

        trends_file = exporter.venues_data_dir / "global_keyword_trends.json"
        emerging_file = exporter.venues_data_dir / "global_emerging_keywords.json"

        assert trends_file.exists()
        assert emerging_file.exists()

        with open(trends_file, 'r', encoding='utf-8') as f:
            trends = json.load(f)
        with open(emerging_file, 'r', encoding='utf-8') as f:
            emerging = json.load(f)

        assert trends
        assert all({"keyword", "years", "counts", "total"} <= set(row) for row in trends)
        assert emerging
        assert all({"keyword", "growth_rate", "recent_count"} <= set(row) for row in emerging)
    
    def test_export_handles_empty_venue(self, exporter):
        result = exporter.export_venue_top_keywords("NONEXISTENT_VENUE", top_n=10)
        assert result is False

    def test_export_arxiv_stats(self, exporter):
        result = exporter.export_arxiv_stats()
        assert result is True

        output_file = exporter.arxiv_data_dir / "arxiv_stats.json"
        assert output_file.exists()

        with open(output_file, 'r', encoding='utf-8') as f:
            data = json.load(f)

        assert "total_papers" in data
        assert "categories" in data
        assert "date_range" in data
        assert "exported_at" in data
    
    def test_json_structure_validation(self, exporter):
        exporter.export_venues_index()
        
        venues_file = exporter.venues_data_dir / "venues_index.json"
        with open(venues_file, 'r', encoding='utf-8') as f:
            data = json.load(f)
        
        required_fields = ["name", "full_name", "domain", "tier", "years_available", "paper_count", "top_keywords"]
        
        for venue in data:
            for field in required_fields:
                assert field in venue, f"Missing field: {field}"
            
            assert isinstance(venue["paper_count"], int)
            assert venue["paper_count"] >= 0
            
            assert isinstance(venue["years_available"], list)
            assert isinstance(venue["top_keywords"], list)

    def test_exported_html_uses_relative_paths(self, exporter):
        exporter.copy_static_assets()

        index_file = exporter.output_dir / "index.html"
        venue_file = exporter.output_dir / "venue.html"

        assert index_file.exists()
        assert venue_file.exists()

        index_html = index_file.read_text(encoding="utf-8")
        venue_html = venue_file.read_text(encoding="utf-8")

        assert 'href="./css/style.css"' in index_html
        assert 'src="./js/api.js"' in index_html
        assert 'href="./index.html"' in venue_html
        assert 'href="/static/' not in index_html
        assert 'src="/static/' not in index_html
        assert 'href="/"' not in venue_html


@pytest.fixture
def temp_output_dir():
    with tempfile.TemporaryDirectory() as tmpdir:
        yield Path(tmpdir)
