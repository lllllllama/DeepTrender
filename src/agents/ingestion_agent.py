"""
Ingestion Agent

负责从各数据源采集原始论文数据到 Raw Layer。

职责：
- 从 arXiv、OpenAlex、Semantic Scholar、OpenReview 采集数据
- 保存完整原始数据到 raw_papers 表
- 不做任何数据解释或标准化
"""

import logging
import os
import sys
from pathlib import Path
from typing import List, Optional, Dict, Any
from datetime import datetime

# 确保 src 目录在路径中
_src_dir = Path(__file__).parent.parent
if str(_src_dir) not in sys.path:
    sys.path.insert(0, str(_src_dir))

from database import get_raw_repository, RawRepository
from scraper.models import RawPaper
from scraper.arxiv_client import ArxivClient, create_arxiv_client, DEFAULT_CATEGORIES
from scraper.openalex_client import OpenAlexClient, create_openalex_client
from scraper.semantic_scholar import SemanticScholarClient, S2_VENUES
from scraper.client import OpenReviewClient, create_client as create_or_client
from scraper.venues import parse_note_to_paper
from config import VENUES


logger = logging.getLogger(__name__)


class IngestionAgent:
    """
    原始数据采集 Agent

    负责将各数据源的论文采集到 Raw Layer。
    """

    def __init__(
        self,
        repository: RawRepository = None,
        arxiv_client: ArxivClient = None,
        openalex_client: OpenAlexClient = None,
        s2_client: SemanticScholarClient = None,
        or_client: OpenReviewClient = None,
    ):
        self.repo = repository or get_raw_repository()
        self.arxiv = arxiv_client
        self.openalex = openalex_client
        self.s2 = s2_client
        self.or_client = or_client

    def _get_arxiv_client(self) -> ArxivClient:
        """懒加载 arXiv 客户端"""
        if self.arxiv is None:
            self.arxiv = create_arxiv_client()
        return self.arxiv

    def _get_openalex_client(self) -> OpenAlexClient:
        """懒加载 OpenAlex 客户端"""
        if self.openalex is None:
            self.openalex = create_openalex_client()
        return self.openalex

    def _get_s2_client(self) -> SemanticScholarClient:
        """懒加载 Semantic Scholar 客户端"""
        if self.s2 is None:
            self.s2 = SemanticScholarClient(
                api_key=os.getenv("SEMANTIC_SCHOLAR_API_KEY") or None
            )
        return self.s2

    def _get_or_client(self) -> OpenReviewClient:
        """懒加载 OpenReview 客户端"""
        if self.or_client is None:
            self.or_client = create_or_client()
        return self.or_client

    # ========== arXiv 采集 ==========

    def ingest_arxiv_recent(
        self,
        categories: List[str] = None,
        days: int = 7,
        max_results: int = 1000,
    ) -> int:
        """
        采集 arXiv 最近的论文

        Args:
            categories: arXiv 类别列表
            days: 天数
            max_results: 最大数量

        Returns:
            采集的论文数量
        """
        client = self._get_arxiv_client()
        categories = categories or DEFAULT_CATEGORIES

        print(f"\n📥 [Ingestion] 正在从 arXiv 采集最近 {days} 天的论文...")

        papers = client.search_recent(
            categories=categories,
            days=days,
            max_results=max_results,
        )

        saved_count = 0
        for paper in papers:
            try:
                self.repo.save_raw_paper(paper)
                saved_count += 1
            except Exception:
                logger.exception(
                    "Failed to save arXiv paper %s",
                    getattr(paper, "source_paper_id", "<unknown>"),
                )

        print(f"✅ arXiv: 已保存 {saved_count}/{len(papers)} 篇到 Raw Layer")
        return saved_count

    def ingest_arxiv_category(
        self,
        category: str,
        max_results: int = 1000,
    ) -> int:
        """按类别采集 arXiv 论文"""
        client = self._get_arxiv_client()

        print(f"\n📥 [Ingestion] 正在从 arXiv 采集 {category} 类别...")

        papers = client.search_by_category(category, max_results)

        saved_count = 0
        for paper in papers:
            try:
                self.repo.save_raw_paper(paper)
                saved_count += 1
            except Exception:
                logger.exception(
                    "Failed to save arXiv paper %s for category %s",
                    getattr(paper, "source_paper_id", "<unknown>"),
                    category,
                )

        print(f"✅ arXiv {category}: 已保存 {saved_count} 篇")
        return saved_count

    # ========== OpenAlex 采集 ==========

    def ingest_openalex_venue(
        self,
        venue_name: str,
        year: int,
        max_results: int = 2000,
    ) -> int:
        """
        按会议采集 OpenAlex 论文

        Args:
            venue_name: 会议名称
            year: 年份
            max_results: 最大数量

        Returns:
            采集数量
        """
        client = self._get_openalex_client()

        print(f"\n📥 [Ingestion] 正在从 OpenAlex 采集 {venue_name} {year}...")

        papers = client.search_by_venue_year(venue_name, year, max_results)

        saved_count = 0
        for paper in papers:
            try:
                self.repo.save_raw_paper(paper)
                saved_count += 1
            except Exception:
                logger.exception(
                    "Failed to save OpenAlex paper %s for %s %s",
                    getattr(paper, "source_paper_id", "<unknown>"),
                    venue_name,
                    year,
                )

        print(f"✅ OpenAlex {venue_name} {year}: 已保存 {saved_count} 篇")
        return saved_count

    # ========== Semantic Scholar 采集 ==========

    def ingest_s2_venue(
        self,
        venue_name: str,
        year: int,
        max_results: int = 1000,
    ) -> int:
        """按会议采集 Semantic Scholar 论文"""
        client = self._get_s2_client()
        config = S2_VENUES.get(venue_name)
        canonical_venue = config.name if config else venue_name
        venue_query = config.venue_query if config else venue_name

        print(f"\n📥 [Ingestion] 正在从 Semantic Scholar 采集 {canonical_venue} {year}...")

        raw_papers = client.search_papers(venue_query, year, max_results)

        saved_count = 0
        for data in raw_papers:
            try:
                paper = self._parse_s2_to_raw(data, canonical_venue, year)
                if paper:
                    self.repo.save_raw_paper(paper)
                    saved_count += 1
            except Exception:
                logger.exception(
                    "Failed to parse or save Semantic Scholar paper %s for %s %s",
                    data.get("paperId", "<unknown>") if isinstance(data, dict) else "<unknown>",
                    canonical_venue,
                    year,
                )

        print(f"✅ Semantic Scholar {canonical_venue} {year}: 已保存 {saved_count} 篇")
        return saved_count

    def _parse_s2_to_raw(self, data: Dict, venue: str, year: int) -> Optional[RawPaper]:
        """将 S2 数据转换为 RawPaper"""
        try:
            paper_id = data.get("paperId", "")
            if not paper_id:
                return None

            authors = []
            for author in data.get("authors", []):
                if isinstance(author, dict):
                    name = author.get("name", "")
                    if name:
                        authors.append(name)

            return RawPaper(
                source="s2",
                source_paper_id=paper_id,
                title=data.get("title", ""),
                abstract=data.get("abstract", ""),
                authors=authors,
                year=year,
                venue_raw=venue,
                doi=None,
                raw_json=data,
                retrieved_at=datetime.now(),
            )
        except Exception:
            logger.exception(
                "Failed to parse Semantic Scholar paper %s for %s %s",
                data.get("paperId", "<unknown>") if isinstance(data, dict) else "<unknown>",
                venue,
                year,
            )
            return None

    # ========== OpenReview 采集 ==========

    def ingest_openreview_venue(
        self,
        venue_name: str,
        year: int,
        limit: int = None,
    ) -> int:
        """采集 OpenReview 会议论文"""
        if venue_name not in VENUES:
            print(f"⚠️ 未配置的会议: {venue_name}")
            return 0

        config = VENUES[venue_name]
        client = self._get_or_client()

        venue_id = config.venue_id_pattern.format(year=year)

        print(f"\n📥 [Ingestion] 正在从 OpenReview 采集 {venue_name} {year}...")

        saved_count = 0
        for note in client.get_accepted_papers(venue_id, limit=limit):
            try:
                paper = self._parse_or_to_raw(note, venue_name, year)
                if paper:
                    self.repo.save_raw_paper(paper)
                    saved_count += 1
            except Exception:
                logger.exception(
                    "Failed to parse or save OpenReview note %s for %s %s",
                    getattr(note, "id", "<unknown>"),
                    venue_name,
                    year,
                )

        print(f"✅ OpenReview {venue_name} {year}: 已保存 {saved_count} 篇")
        return saved_count

    def _parse_or_to_raw(self, note, venue: str, year: int) -> Optional[RawPaper]:
        """将 OpenReview Note 转换为 RawPaper"""
        try:
            content = note.content

            # 获取标题
            title = content.get("title", {})
            if isinstance(title, dict):
                title = title.get("value", "")

            # 获取摘要
            abstract = content.get("abstract", {})
            if isinstance(abstract, dict):
                abstract = abstract.get("value", "")

            # 获取作者
            authors = content.get("authors", {})
            if isinstance(authors, dict):
                authors = authors.get("value", [])
            if isinstance(authors, str):
                authors = [authors]

            # 获取关键词（存入 comments）
            keywords = content.get("keywords", {})
            if isinstance(keywords, dict):
                keywords = keywords.get("value", [])
            keywords_str = ",".join(keywords) if isinstance(keywords, list) else str(keywords)

            return RawPaper(
                source="openreview",
                source_paper_id=note.id,
                title=title,
                abstract=abstract,
                authors=authors if isinstance(authors, list) else [],
                year=year,
                venue_raw=venue,
                comments=keywords_str,  # 存储关键词
                raw_json={
                    "id": note.id,
                    "forum": getattr(note, "forum", None),
                    "content_keys": list(content.keys()),
                },
                retrieved_at=datetime.now(),
            )
        except Exception:
            logger.exception(
                "Failed to parse OpenReview note %s",
                getattr(note, "id", "<unknown>"),
            )
            return None

    # ========== 批量采集 ==========

    def run(
        self,
        sources: List[str] = None,
        arxiv_days: int = 7,
        arxiv_max_results: int = 1000,
        venues: List[str] = None,
        years: List[int] = None,
    ) -> Dict[str, int]:
        """
        运行完整采集流程

        Args:
            sources: 数据源列表 ["arxiv", "openalex", "s2", "openreview"]
            arxiv_days: arXiv 采集天数
            venues: 会议列表
            years: 年份列表

        Returns:
            各数据源采集数量
        """
        sources = sources or ["arxiv", "openalex"]
        results = {}

        print("\n" + "=" * 60)
        print("📥 [Ingestion Agent] 开始采集原始数据")
        print("=" * 60)

        # arXiv
        if "arxiv" in sources:
            results["arxiv"] = self.ingest_arxiv_recent(
                days=arxiv_days,
                max_results=arxiv_max_results,
            )

        # OpenAlex
        if "openalex" in sources and venues and years:
            count = 0
            for venue in venues:
                for year in years:
                    count += self.ingest_openalex_venue(venue, year)
            results["openalex"] = count

        # Semantic Scholar
        if "s2" in sources and venues and years:
            count = 0
            for venue in venues:
                for year in years:
                    count += self.ingest_s2_venue(venue, year)
            results["s2"] = count

        # OpenReview
        if "openreview" in sources:
            count = 0
            or_venues = venues or list(VENUES.keys())
            or_years = years or [2024, 2023]
            for venue in or_venues:
                if venue in VENUES:
                    for year in or_years:
                        if year in VENUES[venue].years:
                            count += self.ingest_openreview_venue(venue, year)
            results["openreview"] = count

        total = sum(results.values())
        print(f"\n📊 [Ingestion] 总计采集 {total} 篇到 Raw Layer")

        return results


def run_ingestion(
    sources: List[str] = None,
    arxiv_days: int = 7,
    arxiv_max_results: int = 1000,
    venues: List[str] = None,
    years: List[int] = None,
) -> Dict[str, int]:
    """运行采集的便捷函数"""
    agent = IngestionAgent()
    return agent.run(
        sources=sources,
        arxiv_days=arxiv_days,
        arxiv_max_results=arxiv_max_results,
        venues=venues,
        years=years,
    )
