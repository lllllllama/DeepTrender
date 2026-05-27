"""
Tests for arXiv timeseries analysis with published_at bucketing
"""

import pytest
from datetime import datetime
from collections import defaultdict


class TestArxivTimeseries:
    """Test arXiv timeseries bucketing with published_at"""
    
    def test_group_by_month_with_published_at(self):
        """Test month bucketing uses published_at"""
        from analysis.arxiv_agent import ArxivAnalysisAgent
        
        agent = ArxivAnalysisAgent()
        
        # Sample papers with published_at
        papers = [
            {
                "raw_id": 1,
                "title": "Paper 1",
                "abstract": "Test",
                "year": 2024,
                "categories": "cs.LG",
                "published_at": datetime(2024, 1, 15),
                "retrieved_at": datetime(2024, 2, 1)
            },
            {
                "raw_id": 2,
                "title": "Paper 2",
                "abstract": "Test",
                "year": 2024,
                "categories": "cs.LG",
                "published_at": datetime(2024, 1, 20),
                "retrieved_at": datetime(2024, 2, 1)
            },
            {
                "raw_id": 3,
                "title": "Paper 3",
                "abstract": "Test",
                "year": 2024,
                "categories": "cs.LG",
                "published_at": datetime(2024, 2, 10),
                "retrieved_at": datetime(2024, 2, 15)
            }
        ]
        
        buckets = agent._group_by_month(papers)
        
        # Should bucket by published_at month, not retrieved_at
        assert "2024-01" in buckets
        assert "2024-02" in buckets
        assert len(buckets["2024-01"]) == 2
        assert len(buckets["2024-02"]) == 1
    
    def test_group_by_month_fallback_to_retrieved_at(self):
        """Test month bucketing falls back to retrieved_at when published_at missing"""
        from analysis.arxiv_agent import ArxivAnalysisAgent
        
        agent = ArxivAnalysisAgent()
        
        # Papers without published_at
        papers = [
            {
                "raw_id": 1,
                "title": "Paper 1",
                "abstract": "Test",
                "year": 2024,
                "categories": "cs.LG",
                "retrieved_at": datetime(2024, 3, 15)
            },
            {
                "raw_id": 2,
                "title": "Paper 2",
                "abstract": "Test",
                "year": 2024,
                "categories": "cs.LG",
                "retrieved_at": datetime(2024, 3, 20)
            }
        ]
        
        buckets = agent._group_by_month(papers)
        
        # Should use retrieved_at as fallback
        assert "2024-03" in buckets
        assert len(buckets["2024-03"]) == 2
    
    def test_group_by_day_with_published_at(self):
        """Test day bucketing uses published_at"""
        from analysis.arxiv_agent import ArxivAnalysisAgent
        
        agent = ArxivAnalysisAgent()
        
        papers = [
            {
                "raw_id": 1,
                "title": "Paper 1",
                "abstract": "Test",
                "year": 2024,
                "categories": "cs.LG",
                "published_at": datetime(2024, 1, 15),
                "retrieved_at": datetime(2024, 2, 1)
            },
            {
                "raw_id": 2,
                "title": "Paper 2",
                "abstract": "Test",
                "year": 2024,
                "categories": "cs.LG",
                "published_at": datetime(2024, 1, 15),
                "retrieved_at": datetime(2024, 2, 2)
            }
        ]
        
        buckets = agent._group_by_day(papers)
        
        # Should bucket by published_at day
        assert "2024-01-15" in buckets
        assert len(buckets["2024-01-15"]) == 2
    
    def test_group_by_week_with_published_at(self):
        """Test week bucketing uses published_at"""
        from analysis.arxiv_agent import ArxivAnalysisAgent
        
        agent = ArxivAnalysisAgent()
        
        papers = [
            {
        "raw_id": 1,
                "title": "Paper 1",
                "abstract": "Test",
                "year": 2024,
                "categories": "cs.LG",
                "published_at": datetime(2024, 1, 15),  # Week 3
                "retrieved_at": datetime(2024, 2, 1)
            },
            {
                "raw_id": 2,
                "title": "Paper 2",
                "abstract": "Test",
                "year": 2024,
                "categories": "cs.LG",
                "published_at": datetime(2024, 1, 16),  # Week 3
                "retrieved_at": datetime(2024, 2, 1)
            }
        ]
        
        buckets = agent._group_by_week(papers)
        
        # Should bucket by published_at ISO week
        assert "2024-W03" in buckets
        assert len(buckets["2024-W03"]) == 2
    
    def test_group_by_year(self):
        """Test year bucketing"""
        from analysis.arxiv_agent import ArxivAnalysisAgent
        
        agent = ArxivAnalysisAgent()
        
        papers = [
            {"raw_id": 1, "title": "P1", "abstract": "T", "year": 2024, "categories": "cs.LG", "published_at": datetime(2023, 1, 1)},
            {"raw_id": 2, "title": "P2", "abstract": "T", "year": 2024, "categories": "cs.LG", "published_at": datetime(2023, 2, 1)},
            {"raw_id": 3, "title": "P3", "abstract": "T", "year": 2024, "categories": "cs.LG", "published_at": datetime(2024, 1, 1)}
        ]
        
        buckets = agent._group_by_year(papers)
        
        assert "2023" in buckets
        assert "2024" in buckets
        assert len(buckets["2023"]) == 2
        assert len(buckets["2024"]) == 1
    
    def test_month_bucket_format(self):
        """Test month bucket key format is YYYY-MM"""
        from analysis.arxiv_agent import ArxivAnalysisAgent
        
        agent = ArxivAnalysisAgent()
        
        papers = [
            {
                "raw_id": 1,
                "title": "Paper",
                "abstract": "Test",
                "year": 2024,
                "categories": "cs.LG",
                "published_at": datetime(2024, 3, 5)
            }
        ]
        
        buckets = agent._group_by_month(papers)
        
        # Check format
        assert "2024-03" in buckets
        assert "2024-3" not in buckets  # Should be zero-padded
    
    def test_empty_papers_list(self):
        """Test handling of empty papers list"""
        from analysis.arxiv_agent import ArxivAnalysisAgent
        
        agent = ArxivAnalysisAgent()
        
        buckets_month = agent._group_by_month([])
        buckets_day = agent._group_by_day([])
        buckets_week = agent._group_by_week([])
        buckets_year = agent._group_by_year([])
        
        assert buckets_month == {}
        assert buckets_day == {}
        assert buckets_week == {}
        assert buckets_year == {}
    
    def test_mixed_published_and_retrieved(self):
        """Test handling mix of papers with and without published_at"""
        from analysis.arxiv_agent import ArxivAnalysisAgent
        
        agent = ArxivAnalysisAgent()
        
        papers = [
            {
                "raw_id": 1,
                "title": "Paper 1",
                "abstract": "Test",
                "year": 2024,
                "categories": "cs.LG",
                "published_at": datetime(2024, 1, 15),
                "retrieved_at": datetime(2024, 2, 1)
            },
            {
                "raw_id": 2,
                "title": "Paper 2",
                "abstract": "Test",
                "year": 2024,
                "categories": "cs.LG",
                # No published_at
                "retrieved_at": datetime(2024, 1, 20)
            }
        ]
        
        buckets = agent._group_by_month(papers)
        
        # Both should be in 2024-01 (one from published_at, one from retrieved_at)
        assert "2024-01" in buckets
        assert len(buckets["2024-01"]) == 2

