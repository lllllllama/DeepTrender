"""Unified repository and singleton factories."""

from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from config import ARXIV_CATEGORIES
from scraper.models import Paper, Venue
from taxonomy.keyword_normalizer import get_keyword_canonicalizer

from .repository import (
    AnalysisRepository,
    BaseRepository,
    RawRepository,
    StructuredRepository,
)


class DatabaseRepository(BaseRepository):
    """Compatibility facade that combines raw, structured, and analysis repos."""

    def __init__(self, db_path: Path = None):
        super().__init__(db_path)
        self.raw = RawRepository(self.db_path)
        self.structured = StructuredRepository(self.db_path)
        self.analysis = AnalysisRepository(self.db_path)

    def save_paper(self, paper: Paper) -> bool:
        """Save a structured paper and its keywords."""
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
            print(f"Failed to save paper: {exc}")
            return False

    def save_papers(self, papers: List[Paper]) -> int:
        count = 0
        for paper in papers:
            if self.save_paper(paper):
                count += 1
        return count

    def get_paper(self, paper_id: int) -> Optional[Paper]:
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
        venue_obj = self.structured.get_venue_by_name(venue)
        if not venue_obj:
            return []
        return self.structured.get_papers_by_venue_year(venue_obj.venue_id, year)

    def get_all_papers(self, limit: int = None) -> List[Paper]:
        return self.structured.get_all_papers(limit=limit)

    def get_paper_count(self, venue: str = None, year: int = None) -> int:
        venue_id = None
        if venue:
            venue_obj = self.structured.get_venue_by_name(venue)
            if not venue_obj:
                return 0
            venue_id = venue_obj.venue_id
        return self.structured.get_paper_count(venue_id=venue_id, year=year)

    def _get_venue_id_for_query(self, venue: str = None) -> Optional[int]:
        if not venue:
            return None
        venue_obj = self.structured.get_venue_by_name(venue)
        return venue_obj.venue_id if venue_obj else -1

    def _keyword_method_for_source(self, source: str = None) -> Optional[str]:
        if source == "author":
            return "author"
        if source == "extracted":
            return "extracted"
        return None

    def _keyword_paper_rows(
        self,
        venue_id: Optional[int] = None,
        year: Optional[int] = None,
        method: Optional[str] = None,
    ) -> List[Tuple[str, int]]:
        if venue_id == -1:
            return []

        query = """
            SELECT pk.keyword, pk.paper_id
            FROM paper_keywords pk
            JOIN papers p ON pk.paper_id = p.paper_id
            WHERE 1=1
        """
        params: list[Any] = []
        if venue_id is not None:
            query += " AND p.venue_id = ?"
            params.append(venue_id)
        if year:
            query += " AND p.year = ?"
            params.append(year)
        if method:
            query += " AND pk.method = ?"
            params.append(method)

        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(query, params)
            return [(row["keyword"], row["paper_id"]) for row in cursor.fetchall()]

    def _raw_keyword_count_rows(
        self,
        venue_id: Optional[int] = None,
        year: Optional[int] = None,
        method: Optional[str] = None,
    ) -> List[Tuple[str, int]]:
        if venue_id == -1:
            return []

        query = """
            SELECT pk.keyword, COUNT(DISTINCT pk.paper_id) as count
            FROM paper_keywords pk
            JOIN papers p ON pk.paper_id = p.paper_id
            WHERE 1=1
        """
        params: list[Any] = []
        if venue_id is not None:
            query += " AND p.venue_id = ?"
            params.append(venue_id)
        if year:
            query += " AND p.year = ?"
            params.append(year)
        if method:
            query += " AND pk.method = ?"
            params.append(method)

        query += " GROUP BY pk.keyword ORDER BY count DESC, pk.keyword ASC"
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(query, params)
            return [(row["keyword"], row["count"]) for row in cursor.fetchall()]

    def get_top_keywords(
        self,
        venue: str = None,
        year: int = None,
        source: str = None,
        limit: int = 50,
    ) -> List[Tuple[str, int]]:
        """Return canonical Top-K keywords counted once per paper."""
        venue_id = self._get_venue_id_for_query(venue)
        method = self._keyword_method_for_source(source)
        rows = self._keyword_paper_rows(venue_id=venue_id, year=year, method=method)
        canonicalizer = get_keyword_canonicalizer()
        return [
            item.as_pair()
            for item in canonicalizer.aggregate_paper_keyword_rows(rows, limit=limit)
        ]

    def get_total_keyword_count(
        self,
        venue: str = None,
        year: int = None,
        source: str = None,
    ) -> int:
        """Return the canonical distinct keyword count for the requested scope."""
        venue_id = self._get_venue_id_for_query(venue)
        method = self._keyword_method_for_source(source)
        rows = self._keyword_paper_rows(venue_id=venue_id, year=year, method=method)
        return len(get_keyword_canonicalizer().aggregate_paper_keyword_rows(rows))

    def get_keyword_trend(self, keyword: str, venue: str = None) -> Dict[int, int]:
        """Return a canonical keyword trend counted once per paper/year."""
        venue_id = self._get_venue_id_for_query(venue)
        if venue_id == -1:
            return {}

        surface_forms = get_keyword_canonicalizer().equivalent_surface_forms(keyword)
        if not surface_forms:
            return {}

        placeholders = ",".join("?" for _ in surface_forms)
        query = f"""
            SELECT p.year, COUNT(DISTINCT pk.paper_id) as count
            FROM paper_keywords pk
            JOIN papers p ON pk.paper_id = p.paper_id
            WHERE LOWER(pk.keyword) IN ({placeholders})
        """
        params: list[Any] = [form.lower() for form in surface_forms]
        if venue_id is not None:
            query += " AND p.venue_id = ?"
            params.append(venue_id)
        query += " GROUP BY p.year ORDER BY p.year"

        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(query, params)
            return {row["year"]: row["count"] for row in cursor.fetchall()}

    def get_all_venues(self) -> List[str]:
        return [venue.canonical_name for venue in self.structured.get_all_venues()]

    def get_all_years(self, venue: str = None) -> List[int]:
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
        result = {}
        for venue in self.structured.get_all_venues():
            keywords = self.get_top_keywords(
                venue=venue.canonical_name,
                year=year,
                limit=limit,
            )
            if keywords:
                result[venue.canonical_name] = keywords
        return result

    def get_keyword_normalization_audit(
        self,
        venue: str = None,
        year: int = None,
        source: str = None,
        limit: int = 25,
    ) -> Dict[str, Any]:
        """Return raw-vs-canonical keyword evidence for QA artifacts."""
        venue_id = self._get_venue_id_for_query(venue)
        method = self._keyword_method_for_source(source)
        raw_rows = self._raw_keyword_count_rows(venue_id=venue_id, year=year, method=method)
        paper_rows = self._keyword_paper_rows(venue_id=venue_id, year=year, method=method)
        canonicalizer = get_keyword_canonicalizer()
        canonical_rows = canonicalizer.aggregate_paper_keyword_rows(paper_rows)

        noise_total = 0
        noise_examples = []
        for keyword, count in raw_rows:
            if canonicalizer.normalize(keyword) is None:
                noise_total += count
                if len(noise_examples) < limit:
                    noise_examples.append({"keyword": keyword, "count": count})

        merged_groups = [
            item.as_dict(include_variants=True)
            for item in canonical_rows
            if len(item.variants) > 1
        ][:limit]

        return {
            "scope": {"venue": venue, "year": year, "source": source},
            "counting_rule": "canonical_keyword_counted_once_per_paper",
            "raw_top_keywords": [
                {"keyword": keyword, "count": count}
                for keyword, count in raw_rows[:limit]
            ],
            "canonical_top_keywords": [
                item.as_dict(include_variants=True)
                for item in canonical_rows[:limit]
            ],
            "merged_groups": merged_groups,
            "filtered_noise": {
                "row_count": noise_total,
                "examples": noise_examples,
            },
            "raw_distinct_keywords": len(raw_rows),
            "canonical_distinct_keywords": len(canonical_rows),
        }

    def save_paper_topic(self, **kwargs) -> int:
        return self.analysis.save_paper_topic(**kwargs)

    def save_paper_topics(self, matches: List[Dict]) -> List[int]:
        return self.analysis.save_paper_topics(matches)

    def get_paper_topics(self, paper_id: int, taxonomy_version: str = None) -> List[Dict]:
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
        return self.analysis.get_paper_topic_count(
            taxonomy_version=taxonomy_version,
            topic_id=topic_id,
        )

    def clear_paper_topics_for_taxonomy_version(self, taxonomy_version: str) -> int:
        return self.analysis.clear_paper_topics_for_taxonomy_version(taxonomy_version)

    def rebuild_paper_topics(
        self,
        taxonomy_version: str = None,
        limit: int = None,
        include_children: bool = False,
    ) -> Dict[str, Any]:
        from services.topic_facts import rebuild_paper_topics

        return rebuild_paper_topics(
            repo=self,
            taxonomy_version=taxonomy_version,
            limit=limit,
            include_children=include_children,
        )

    def get_arxiv_stats(self, categories: Optional[List[str]] = None) -> Dict[str, Any]:
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
        last_scrape = self.get_last_scrape(venue, year)
        if last_scrape is None:
            return True
        return datetime.now() - last_scrape > timedelta(days=max_age_days)


_repository: Optional[DatabaseRepository] = None
_raw_repository: Optional[RawRepository] = None
_structured_repository: Optional[StructuredRepository] = None
_analysis_repository: Optional[AnalysisRepository] = None


def get_repository(db_path: Path = None) -> DatabaseRepository:
    global _repository
    if _repository is None:
        _repository = DatabaseRepository(db_path)
    return _repository


def get_raw_repository(db_path: Path = None) -> RawRepository:
    global _raw_repository
    if _raw_repository is None:
        _raw_repository = RawRepository(db_path)
    return _raw_repository


def get_structured_repository(db_path: Path = None) -> StructuredRepository:
    global _structured_repository
    if _structured_repository is None:
        _structured_repository = StructuredRepository(db_path)
    return _structured_repository


def get_analysis_repository(db_path: Path = None) -> AnalysisRepository:
    global _analysis_repository
    if _analysis_repository is None:
        _analysis_repository = AnalysisRepository(db_path)
    return _analysis_repository
