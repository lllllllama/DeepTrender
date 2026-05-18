"""Unified repository and singleton factories."""

from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from config import ARXIV_CATEGORIES
from scraper.models import Paper, Venue

from .repository import (
    AnalysisRepository,
    BaseRepository,
    RawRepository,
    StructuredRepository,
)


class DatabaseRepository(BaseRepository):
    """
    统一数据库仓库

    整合三层仓库的功能，并提供向后兼容的接口。
    """

    def __init__(self, db_path: Path = None):
        super().__init__(db_path)
        self.raw = RawRepository(self.db_path)
        self.structured = StructuredRepository(self.db_path)
        self.analysis = AnalysisRepository(self.db_path)

    def save_paper(self, paper: Paper) -> bool:
        """保存论文（兼容旧接口）"""
        try:
            if not paper.venue_name and getattr(paper, "venue", None):
                paper.venue_name = paper.venue

            venue_id = None
            if paper.venue_name:
                venue = self.structured.get_venue_by_name(paper.venue_name)
                if not venue:
                    venue_id = self.structured.save_venue(
                        Venue(
                            canonical_name=paper.venue_name,
                            domain=paper.domain,
                        )
                    )
                else:
                    venue_id = venue.venue_id
                paper.venue_id = venue_id

            paper_id = self.structured.find_paper_by_title(
                paper.canonical_title.lower(),
                paper.year,
            )
            if not paper_id:
                paper_id = self.structured.save_paper(paper)
            paper.paper_id = paper_id

            for keyword in paper.keywords:
                self.analysis.save_keyword(paper_id, keyword, "author")
            for keyword in paper.extracted_keywords:
                self.analysis.save_keyword(paper_id, keyword, "extracted")

            return True
        except Exception as exc:
            print(f"保存论文失败: {exc}")
            return False

    def save_papers(self, papers: List[Paper]) -> int:
        """批量保存论文（兼容旧接口）"""
        count = 0
        for paper in papers:
            if self.save_paper(paper):
                count += 1
        return count

    def get_paper(self, paper_id: int) -> Optional[Paper]:
        """获取论文"""
        if isinstance(paper_id, str):
            if not paper_id.isdigit():
                return None
            paper_id = int(paper_id)

        paper = self.structured.get_paper(paper_id)
        if paper:
            keywords = self.analysis.get_paper_keywords(paper_id)
            paper.keywords = [item.keyword for item in keywords if item.method == "author"]
            paper.extracted_keywords = [item.keyword for item in keywords if item.method != "author"]
        return paper

    def get_papers_by_venue_year(self, venue: str, year: int) -> List[Paper]:
        """Compatibility wrapper accepting venue canonical name."""
        venue_obj = self.structured.get_venue_by_name(venue)
        if not venue_obj:
            return []
        return self.structured.get_papers_by_venue_year(venue_obj.venue_id, year)

    def get_all_papers(self, limit: int = None) -> List[Paper]:
        """Return all structured papers."""
        return self.structured.get_all_papers(limit=limit)

    def get_paper_count(self, venue: str = None, year: int = None) -> int:
        """获取论文数量（兼容旧接口）"""
        venue_id = None
        if venue:
            venue_obj = self.structured.get_venue_by_name(venue)
            if venue_obj:
                venue_id = venue_obj.venue_id
        return self.structured.get_paper_count(venue_id=venue_id, year=year)

    def get_top_keywords(
        self,
        venue: str = None,
        year: int = None,
        source: str = None,
        limit: int = 50,
    ) -> List[Tuple[str, int]]:
        """获取 Top-K 关键词（兼容旧接口）"""
        venue_id = None
        if venue:
            venue_obj = self.structured.get_venue_by_name(venue)
            if venue_obj:
                venue_id = venue_obj.venue_id

        method = None
        if source == "author":
            method = "author"
        elif source == "extracted":
            method = "extracted"

        return self.analysis.get_top_keywords(
            venue_id=venue_id,
            year=year,
            method=method,
            limit=limit,
        )

    def get_total_keyword_count(
        self,
        venue: str = None,
        year: int = None,
        source: str = None,
    ) -> int:
        """获取去重后的关键词总数。"""
        venue_id = None
        if venue:
            venue_obj = self.structured.get_venue_by_name(venue)
            if venue_obj:
                venue_id = venue_obj.venue_id

        method = None
        if source == "author":
            method = "author"
        elif source == "extracted":
            method = "extracted"

        return self.analysis.get_total_keyword_count(
            venue_id=venue_id,
            year=year,
            method=method,
        )

    def get_keyword_trend(self, keyword: str, venue: str = None) -> Dict[int, int]:
        """获取关键词趋势（兼容旧接口）"""
        venue_id = None
        if venue:
            venue_obj = self.structured.get_venue_by_name(venue)
            if venue_obj:
                venue_id = venue_obj.venue_id
        return self.analysis.get_keyword_trend(keyword, venue_id)

    def get_all_venues(self) -> List[str]:
        """获取所有会议名称（兼容旧接口）"""
        return [venue.canonical_name for venue in self.structured.get_all_venues()]

    def get_all_years(self, venue: str = None) -> List[int]:
        """获取所有年份（兼容旧接口）"""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            if venue:
                venue_obj = self.structured.get_venue_by_name(venue)
                if venue_obj:
                    cursor.execute(
                        "SELECT DISTINCT year FROM papers WHERE venue_id = ? ORDER BY year DESC",
                        (venue_obj.venue_id,),
                    )
                else:
                    return []
            else:
                cursor.execute("SELECT DISTINCT year FROM papers ORDER BY year DESC")
            return [row["year"] for row in cursor.fetchall()]

    def get_venue_comparison(self, year: int, limit: int = 10) -> Dict[str, List[Tuple[str, int]]]:
        """获取会议对比（兼容旧接口）"""
        result = {}
        for venue in self.structured.get_all_venues():
            keywords = self.analysis.get_top_keywords(
                venue_id=venue.venue_id,
                year=year,
                limit=limit,
            )
            if keywords:
                result[venue.canonical_name] = keywords
        return result

    def save_paper_topic(self, **kwargs) -> int:
        """Persist one canonical paper-topic match."""
        return self.analysis.save_paper_topic(**kwargs)

    def save_paper_topics(self, matches: List[Dict]) -> List[int]:
        """Persist multiple paper-topic matches."""
        return self.analysis.save_paper_topics(matches)

    def get_paper_topics(self, paper_id: int, taxonomy_version: str = None) -> List[Dict]:
        """Return persisted topic facts for one paper."""
        return self.analysis.get_paper_topics(
            paper_id=paper_id,
            taxonomy_version=taxonomy_version,
        )

    def get_papers_by_topic(
        self,
        topic_id: str,
        venue: str = None,
        year: int = None,
        limit: int = 20,
        offset: int = 0,
        taxonomy_version: str = None,
    ) -> List[Dict]:
        """Return structured papers with persisted facts for a topic."""
        return self.analysis.get_papers_by_topic(
            topic_id=topic_id,
            venue=venue,
            year=year,
            limit=limit,
            offset=offset,
            taxonomy_version=taxonomy_version,
        )

    def get_topic_counts_by_venue_year(
        self,
        topic_id: str,
        venue: str = None,
        year: int = None,
        taxonomy_version: str = None,
    ) -> List[Dict]:
        """Return persisted topic counts grouped by venue/year."""
        return self.analysis.get_topic_counts_by_venue_year(
            topic_id=topic_id,
            venue=venue,
            year=year,
            taxonomy_version=taxonomy_version,
        )

    def get_paper_topic_count(
        self,
        taxonomy_version: str = None,
        topic_id: str = None,
    ) -> int:
        """Return count of persisted paper-topic facts."""
        return self.analysis.get_paper_topic_count(
            taxonomy_version=taxonomy_version,
            topic_id=topic_id,
        )

    def clear_paper_topics_for_taxonomy_version(self, taxonomy_version: str) -> int:
        """Delete persisted topic facts for one taxonomy version."""
        return self.analysis.clear_paper_topics_for_taxonomy_version(taxonomy_version)

    def rebuild_paper_topics(
        self,
        taxonomy_version: str = None,
        limit: int = None,
        include_children: bool = False,
    ) -> Dict[str, Any]:
        """Rebuild paper_topics from structured papers and taxonomy."""
        from services.topic_facts import rebuild_paper_topics

        return rebuild_paper_topics(
            repo=self,
            taxonomy_version=taxonomy_version,
            limit=limit,
            include_children=include_children,
        )

    def get_arxiv_stats(self, categories: Optional[List[str]] = None) -> Dict[str, Any]:
        """Return aggregated arXiv stats for API and static export."""
        category_list = categories or ARXIV_CATEGORIES
        category_counts = {}

        with self._get_connection() as conn:
            cursor = conn.cursor()
            for category in category_list:
                cursor.execute(
                    """
                    SELECT COUNT(*) as count
                    FROM raw_papers
                    WHERE source = 'arxiv' AND categories LIKE ?
                    """,
                    (f"%{category}%",),
                )
                category_counts[category] = cursor.fetchone()["count"]

            cursor.execute(
                """
                SELECT MIN(retrieved_at) as min_date, MAX(retrieved_at) as max_date
                FROM raw_papers
                WHERE source = 'arxiv'
                """
            )
            row = cursor.fetchone()

        return {
            "total_papers": self.raw.get_raw_paper_count(source="arxiv"),
            "categories": category_counts,
            "date_range": {
                "min": row["min_date"] if row and row["min_date"] else None,
                "max": row["max_date"] if row and row["max_date"] else None,
            },
            "latest_update": self.analysis.get_meta("arxiv_last_run_ALL_year"),
        }

    def log_scrape(self, venue: str, year: int, paper_count: int):
        """记录爬取日志"""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                """
                INSERT INTO scrape_logs (venue, year, paper_count)
                VALUES (?, ?, ?)
                """,
                (venue, year, paper_count),
            )
            conn.commit()

    def get_last_scrape(self, venue: str, year: int) -> Optional[datetime]:
        """获取上次爬取时间"""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                """
                SELECT scraped_at FROM scrape_logs
                WHERE venue = ? AND year = ?
                ORDER BY scraped_at DESC LIMIT 1
                """,
                (venue, year),
            )
            row = cursor.fetchone()
            if row:
                return datetime.fromisoformat(row["scraped_at"])
            return None

    def should_scrape(self, venue: str, year: int, max_age_days: int = 7) -> bool:
        """检查是否需要爬取"""
        from datetime import timedelta

        last_scrape = self.get_last_scrape(venue, year)
        if last_scrape is None:
            return True

        age = datetime.now() - last_scrape
        return age > timedelta(days=max_age_days)


_repository: Optional[DatabaseRepository] = None
_raw_repository: Optional[RawRepository] = None
_structured_repository: Optional[StructuredRepository] = None
_analysis_repository: Optional[AnalysisRepository] = None


def get_repository(db_path: Path = None) -> DatabaseRepository:
    """获取统一数据库仓库（单例）"""
    global _repository
    if _repository is None:
        _repository = DatabaseRepository(db_path)
    return _repository


def get_raw_repository(db_path: Path = None) -> RawRepository:
    """获取原始数据层仓库"""
    global _raw_repository
    if _raw_repository is None:
        _raw_repository = RawRepository(db_path)
    return _raw_repository


def get_structured_repository(db_path: Path = None) -> StructuredRepository:
    """获取结构化数据层仓库"""
    global _structured_repository
    if _structured_repository is None:
        _structured_repository = StructuredRepository(db_path)
    return _structured_repository


def get_analysis_repository(db_path: Path = None) -> AnalysisRepository:
    """获取分析层仓库"""
    global _analysis_repository
    if _analysis_repository is None:
        _analysis_repository = AnalysisRepository(db_path)
    return _analysis_repository
