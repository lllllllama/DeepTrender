"""arXiv trend analysis.

All final trend metrics are based on distinct structured ``paper_id`` counts.
Raw arXiv rows without a ``paper_sources`` mapping are surfaced as warnings
instead of being silently counted.
"""

from __future__ import annotations

from collections import Counter, defaultdict
from datetime import datetime
import logging
import re
from typing import Any, Dict, List, Literal, Optional

from database.repository import (
    AnalysisRepository,
    RawRepository,
    get_analysis_repository,
    get_raw_repository,
)
from taxonomy.keyword_normalizer import get_keyword_canonicalizer

logger = logging.getLogger(__name__)

GranularityType = Literal["year", "month", "week", "day"]


class ArxivAnalysisAgent:
    """Build arXiv paper and keyword trend caches."""

    CATEGORIES = ["ALL", "cs.LG", "cs.CV", "cs.CL", "cs.AI", "cs.RO"]
    GRANULARITIES = ["year", "month", "week", "day"]

    def __init__(
        self,
        analysis_repo: AnalysisRepository = None,
        raw_repo: RawRepository = None,
    ):
        self.analysis_repo = analysis_repo or get_analysis_repository()
        self.raw_repo = raw_repo or get_raw_repository()

    def run(
        self,
        granularity: GranularityType = "year",
        category: str = "ALL",
        force: bool = False,
    ) -> Dict:
        """Run one arXiv category/granularity analysis."""
        logger.info("Starting arXiv analysis: granularity=%s category=%s", granularity, category)

        if granularity not in self.GRANULARITIES:
            raise ValueError(f"granularity must be one of {self.GRANULARITIES}")

        if not force and not self._should_run(granularity, category):
            logger.info("No new data, skipping arXiv analysis")
            return {"status": "skipped", "reason": "no_new_data"}

        papers = self._get_arxiv_papers(category)
        if not papers:
            self.analysis_repo.clear_arxiv_analysis_scope(category, granularity)
            return {
                "status": "completed",
                "granularity": granularity,
                "category": category,
                "paper_count": 0,
                "buckets": 0,
                "warnings": [
                    {
                        "code": "registered_no_papers",
                        "message": "No raw arXiv papers matched this category.",
                    }
                ],
            }

        buckets = self._group_papers(papers, granularity)
        timeseries_data = []
        keyword_trends = []

        for bucket, bucket_papers in sorted(buckets.items()):
            linked_paper_ids = {
                int(paper["paper_id"])
                for paper in bucket_papers
                if paper.get("paper_id") is not None
            }
            top_keywords = self._extract_bucket_keywords(bucket_papers, limit=300)
            warnings = self._bucket_warnings(bucket_papers, len(linked_paper_ids), top_keywords)

            timeseries_data.append(
                {
                    "category": category,
                    "granularity": granularity,
                    "bucket": bucket,
                    "paper_count": len(linked_paper_ids),
                    "top_keywords": top_keywords,
                    "warnings": warnings,
                }
            )
            for item in top_keywords:
                keyword_trends.append(
                    {
                        "scope": "arxiv",
                        "venue": category,
                        "keyword": item["keyword"],
                        "granularity": granularity,
                        "bucket": bucket,
                        "count": item["count"],
                        "relative_frequency": item["relative_frequency"],
                        "rank": item["rank"],
                    }
                )

        self.analysis_repo.clear_arxiv_analysis_scope(category, granularity)
        self.analysis_repo.save_arxiv_timeseries_batch(timeseries_data)
        self.analysis_repo.save_keyword_trends_batch(keyword_trends)
        self._update_meta(granularity, category)

        return {
            "status": "completed",
            "granularity": granularity,
            "category": category,
            "paper_count": len({paper.get("paper_id") for paper in papers if paper.get("paper_id") is not None}),
            "buckets": len(buckets),
        }

    def run_all_granularities(self, category: str = "ALL", force: bool = False) -> Dict:
        """Run year/month/week/day for a category."""
        return {
            granularity: self.run(granularity, category, force)
            for granularity in self.GRANULARITIES
        }

    def run_default_categories(self, force: bool = False) -> Dict[str, Dict]:
        """Run the required ALL/cs.* category set."""
        return {
            category: self.run_all_granularities(category=category, force=force)
            for category in self.CATEGORIES
        }

    def _should_run(self, granularity: str, category: str) -> bool:
        meta_key = f"arxiv_last_retrieved_{category}_{granularity}"
        last_retrieved = self.analysis_repo.get_meta(meta_key)
        current_max = self.analysis_repo.get_max_retrieved_at()
        if not last_retrieved:
            return True
        if not current_max:
            return False
        return current_max > last_retrieved

    def _update_meta(self, granularity: str, category: str) -> None:
        current_max = self.analysis_repo.get_max_retrieved_at()
        if current_max:
            self.analysis_repo.set_meta(f"arxiv_last_retrieved_{category}_{granularity}", current_max)
        self.analysis_repo.set_meta(f"arxiv_last_run_{category}_{granularity}", datetime.now().isoformat())

    def _get_arxiv_papers(self, category: str) -> List[Dict]:
        with self.raw_repo._get_connection() as conn:
            cursor = conn.cursor()
            query = """
                SELECT
                    r.raw_id,
                    r.source_paper_id,
                    r.title,
                    r.abstract,
                    r.year,
                    r.categories,
                    r.published_at,
                    r.retrieved_at,
                    ps.paper_id
                FROM raw_papers r
                LEFT JOIN paper_sources ps
                    ON ps.raw_id = r.raw_id AND ps.source = 'arxiv'
                WHERE r.source = 'arxiv'
            """
            params: list[Any] = []
            if category != "ALL":
                query += " AND r.categories LIKE ?"
                params.append(f"%{category}%")
            query += " ORDER BY COALESCE(r.published_at, r.retrieved_at), r.raw_id"
            cursor.execute(query, params)
            return [dict(row) for row in cursor.fetchall()]

    def _parse_date(self, value: Any) -> Optional[datetime]:
        if isinstance(value, datetime):
            return value
        if isinstance(value, str) and value:
            try:
                return datetime.fromisoformat(value)
            except ValueError:
                return None
        return None

    def _bucket_date(self, paper: Dict) -> Optional[datetime]:
        return self._parse_date(paper.get("published_at")) or self._parse_date(paper.get("retrieved_at"))

    def _group_papers(self, papers: List[Dict], granularity: str) -> Dict[str, List[Dict]]:
        if granularity == "year":
            return self._group_by_year(papers)
        if granularity == "month":
            return self._group_by_month(papers)
        if granularity == "week":
            return self._group_by_week(papers)
        return self._group_by_day(papers)

    def _group_by_year(self, papers: List[Dict]) -> Dict[str, List[Dict]]:
        buckets = defaultdict(list)
        for paper in papers:
            date_field = self._bucket_date(paper)
            if date_field:
                buckets[str(date_field.year)].append(paper)
        return dict(buckets)

    def _group_by_month(self, papers: List[Dict]) -> Dict[str, List[Dict]]:
        buckets = defaultdict(list)
        missing_published_count = 0
        for paper in papers:
            if not paper.get("published_at"):
                missing_published_count += 1
            date_field = self._bucket_date(paper)
            if date_field:
                buckets[date_field.strftime("%Y-%m")].append(paper)
        self._log_published_fallback(missing_published_count, len(papers))
        return dict(buckets)

    def _group_by_week(self, papers: List[Dict]) -> Dict[str, List[Dict]]:
        buckets = defaultdict(list)
        missing_published_count = 0
        for paper in papers:
            if not paper.get("published_at"):
                missing_published_count += 1
            date_field = self._bucket_date(paper)
            if date_field:
                iso_cal = date_field.isocalendar()
                buckets[f"{iso_cal.year}-W{iso_cal.week:02d}"].append(paper)
        self._log_published_fallback(missing_published_count, len(papers))
        return dict(buckets)

    def _group_by_day(self, papers: List[Dict]) -> Dict[str, List[Dict]]:
        buckets = defaultdict(list)
        missing_published_count = 0
        for paper in papers:
            if not paper.get("published_at"):
                missing_published_count += 1
            date_field = self._bucket_date(paper)
            if date_field:
                buckets[date_field.strftime("%Y-%m-%d")].append(paper)
        self._log_published_fallback(missing_published_count, len(papers))
        return dict(buckets)

    def _log_published_fallback(self, missing_published_count: int, total: int) -> None:
        if missing_published_count:
            logger.warning(
                "%s/%s papers missing published_at, used retrieved_at as fallback",
                missing_published_count,
                total,
            )

    def _extract_bucket_keywords(self, papers: List[Dict], limit: int = 10) -> List[Dict]:
        """Aggregate canonical keyword counts from distinct linked paper_id values."""
        paper_ids = sorted({int(paper["paper_id"]) for paper in papers if paper.get("paper_id") is not None})
        if not paper_ids:
            return []

        placeholders = ",".join("?" for _ in paper_ids)
        canonicalizer = get_keyword_canonicalizer()
        paper_ids_by_key = defaultdict(set)
        variants_by_key = defaultdict(lambda: defaultdict(set))
        metadata = {}
        evidence_by_key = defaultdict(list)

        with self.analysis_repo._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                f"""
                SELECT
                    pk.keyword,
                    pk.paper_id,
                    p.canonical_title AS title,
                    r.source_paper_id,
                    r.published_at,
                    r.retrieved_at
                FROM paper_keywords pk
                JOIN papers p ON pk.paper_id = p.paper_id
                LEFT JOIN paper_sources ps
                    ON ps.paper_id = p.paper_id AND ps.source = 'arxiv'
                LEFT JOIN raw_papers r ON r.raw_id = ps.raw_id
                WHERE pk.paper_id IN ({placeholders})
                ORDER BY pk.paper_id, pk.keyword
                """,
                paper_ids,
            )
            rows = cursor.fetchall()

        for row in rows:
            normalized = canonicalizer.normalize(row["keyword"])
            if normalized is None:
                continue
            key = normalized.canonical_key
            paper_id = int(row["paper_id"])
            metadata.setdefault(key, normalized)
            paper_ids_by_key[key].add(paper_id)
            variants_by_key[key][normalized.original].add(paper_id)
            if len(evidence_by_key[key]) < 3:
                evidence_by_key[key].append(
                    {
                        "paper_id": paper_id,
                        "title": row["title"],
                        "source": "arxiv",
                        "source_paper_id": row["source_paper_id"],
                        "published_at": row["published_at"],
                        "retrieved_at": row["retrieved_at"],
                        "matched_keyword": normalized.original,
                    }
                )

        denominator = len(paper_ids)
        items = []
        for key, key_paper_ids in paper_ids_by_key.items():
            normalized = metadata[key]
            count = len(key_paper_ids)
            item = {
                "keyword": normalized.canonical_keyword,
                "count": count,
                "relative_frequency": round(count / denominator, 6) if denominator else 0,
                "matched_keywords": sorted(variants_by_key[key]),
                "evidence": evidence_by_key[key],
            }
            if normalized.topic_id:
                item["topic_id"] = normalized.topic_id
            items.append(item)

        items.sort(key=lambda item: (-item["count"], item["keyword"]))
        for rank, item in enumerate(items, start=1):
            item["rank"] = rank
        return items[:limit]

    def _bucket_warnings(
        self,
        papers: List[Dict],
        linked_paper_count: int,
        top_keywords: Optional[List[Dict]] = None,
    ) -> List[Dict]:
        warnings = []
        if not papers:
            return [{"code": "registered_no_papers", "message": "No papers were available for this bucket."}]

        missing_source = sum(1 for paper in papers if paper.get("paper_id") is None)
        if missing_source:
            warnings.append(
                {
                    "code": "missing_source_mapping",
                    "message": f"{missing_source} raw arXiv papers are not linked to structured paper_id records.",
                }
            )
        if linked_paper_count == 0:
            warnings.append({"code": "registered_no_papers", "message": "No linked paper_id records are available."})
        elif linked_paper_count < 5:
            warnings.append({"code": "low_sample_size", "message": "Bucket has fewer than 5 linked papers."})
        if linked_paper_count > 0 and not top_keywords:
            warnings.append({"code": "missing_source_mapping", "message": "No keyword facts are available for linked papers."})
        return warnings

    def _get_keywords_from_db(self, papers: List[Dict]) -> List[Dict]:
        return self._extract_bucket_keywords(papers)

    def _extract_with_yake(self, papers: List[Dict], limit: int) -> List[Dict]:
        """Legacy helper retained for direct unit tests; not used for final counts."""
        try:
            import yake

            texts = [
                f"{paper.get('title', '')}. {paper.get('abstract', '')}"
                for paper in papers
                if paper.get("title") or paper.get("abstract")
            ]
            if not texts:
                return []
            kw_extractor = yake.KeywordExtractor(lan="en", n=3, dedupLim=0.9, top=limit * 2)
            keywords = kw_extractor.extract_keywords(" ".join(texts))
            counts = Counter()
            for keyword, _score in keywords:
                if self._is_valid_keyword(keyword):
                    counts[keyword.lower()] += 1
            return [{"keyword": keyword, "count": count} for keyword, count in counts.most_common(limit)]
        except Exception as exc:
            logger.debug("Failed to extract with YAKE: %s", exc)
            return []

    def _extract_with_frequency(self, papers: List[Dict], limit: int) -> List[Dict]:
        """Legacy helper retained for direct unit tests; not used for final counts."""
        stopwords = {
            "a",
            "an",
            "the",
            "and",
            "or",
            "but",
            "in",
            "on",
            "at",
            "to",
            "for",
            "of",
            "with",
            "by",
            "from",
            "is",
            "are",
            "was",
            "were",
            "model",
            "models",
            "learning",
            "network",
            "networks",
            "neural",
            "deep",
            "data",
            "using",
            "based",
            "novel",
            "method",
            "methods",
            "approach",
            "study",
            "paper",
        }
        counts = Counter()
        for paper in papers:
            for word in re.findall(r"\b[a-zA-Z]{3,}\b", paper.get("title", "").lower()):
                if self._is_valid_keyword(word) and word not in stopwords:
                    counts[word] += 1
        return [{"keyword": keyword, "count": count} for keyword, count in counts.most_common(limit)]

    def _is_valid_keyword(self, keyword: str) -> bool:
        keyword = (keyword or "").strip().lower()
        if not keyword or len(keyword) <= 2:
            return False
        if re.match(r"^\d+$", keyword):
            return False
        return bool(re.match(r"^[a-z][a-z\s-]*$", keyword))

    def detect_emerging_topics(
        self,
        category: str = "ALL",
        threshold: float = 1.5,
        recent_window: int = 4,
    ) -> List[Dict]:
        """Detect rising arXiv keywords from cached weekly trends."""
        timeseries = self.analysis_repo.get_arxiv_timeseries(category, "week")
        if len(timeseries) < recent_window * 2:
            logger.warning("Not enough data for emerging topic detection")
            return []

        keyword_timeseries = defaultdict(list)
        for row in sorted(timeseries, key=lambda item: item["bucket"]):
            for keyword_data in row.get("top_keywords", []):
                keyword_timeseries[keyword_data["keyword"]].append(
                    (row["bucket"], int(keyword_data.get("count") or 0))
                )

        emerging_topics = []
        for keyword, points in keyword_timeseries.items():
            if len(points) < recent_window:
                continue
            recent_counts = [count for _, count in points[-recent_window:]]
            previous_counts = [count for _, count in points[-recent_window * 2 : -recent_window]]
            recent_avg = sum(recent_counts) / len(recent_counts)
            previous_avg = sum(previous_counts) / len(previous_counts) if previous_counts else 0
            growth_rate = (recent_avg / previous_avg) if previous_avg else recent_avg
            if growth_rate >= threshold:
                emerging_topics.append(
                    {
                        "category": category,
                        "keyword": keyword,
                        "growth_rate": round(growth_rate, 2),
                        "first_seen": points[0][0],
                        "recent_count": int(recent_avg),
                        "trend": "rising",
                    }
                )

        emerging_topics.sort(key=lambda item: item["growth_rate"], reverse=True)
        if emerging_topics:
            self.analysis_repo.save_emerging_topics_batch(emerging_topics)
        return emerging_topics

    def compare_categories(self, categories: List[str], granularity: str = "year") -> Dict:
        result = {
            "categories": categories,
            "timeseries": {},
            "overlap": {"keywords": [], "overlap_rate": 0.0},
            "unique": {},
        }
        all_keywords = defaultdict(set)
        for category in categories:
            timeseries = self.analysis_repo.get_arxiv_timeseries(category, granularity)
            result["timeseries"][category] = timeseries
            for row in timeseries:
                for keyword_data in row.get("top_keywords", []):
                    all_keywords[category].add(keyword_data["keyword"])

        if len(categories) >= 2:
            sets = [all_keywords[category] for category in categories]
            overlap = set.intersection(*sets) if sets else set()
            union = set.union(*sets) if sets else set()
            result["overlap"]["keywords"] = sorted(overlap)
            result["overlap"]["overlap_rate"] = round(len(overlap) / len(union), 2) if union else 0.0

        for category in categories:
            others = set().union(*(all_keywords[item] for item in categories if item != category))
            result["unique"][category] = sorted(all_keywords[category] - others)[:10]
        return result


def run_arxiv_analysis(
    granularity: str = "year",
    category: str = "ALL",
    force: bool = False,
) -> Dict:
    agent = ArxivAnalysisAgent()
    return agent.run(granularity, category, force)


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    print(ArxivAnalysisAgent().run_default_categories())
