"""
Semantic Scholar API 客户端

用于获取 CVPR、ACL、AAAI 等不在 OpenReview 上的会议论文。
Semantic Scholar 是一个免费的学术论文搜索引擎，提供 API 访问。
"""

import logging
import time
import requests
from typing import List, Optional, Iterator, Dict, Any
from dataclasses import dataclass

from .models import Paper


logger = logging.getLogger(__name__)


# Semantic Scholar API 配置
S2_API_URL = "https://api.semanticscholar.org/graph/v1"
S2_SEARCH_URL = f"{S2_API_URL}/paper/search/bulk"
S2_PAPER_URL = f"{S2_API_URL}/paper"

# 请求字段
S2_FIELDS = [
    "paperId", "title", "abstract", "authors", "venue",
    "year", "url", "externalIds", "publicationTypes"
]


@dataclass
class SemanticScholarConfig:
    """Semantic Scholar 会议配置"""
    name: str  # 会议简称
    full_name: str  # 会议全称
    venue_query: str  # 用于搜索的 venue 关键词
    years: List[int]


# 支持的会议（通过 Semantic Scholar）
S2_VENUES: Dict[str, SemanticScholarConfig] = {
    # ========== 计算机视觉会议 ==========
    "CVPR": SemanticScholarConfig(
        name="CVPR",
        full_name="IEEE/CVF Conference on Computer Vision and Pattern Recognition",
        venue_query="CVPR",
        years=[2024, 2023, 2022, 2021]
    ),
    "ICCV": SemanticScholarConfig(
        name="ICCV",
        full_name="IEEE/CVF International Conference on Computer Vision",
        venue_query="ICCV",
        years=[2023, 2021]  # 每两年一次
    ),
    "ECCV": SemanticScholarConfig(
        name="ECCV",
        full_name="European Conference on Computer Vision",
        venue_query="ECCV",
        years=[2024, 2022]  # 每两年一次
    ),

    # ========== 自然语言处理会议 ==========
    "ACL": SemanticScholarConfig(
        name="ACL",
        full_name="Annual Meeting of the Association for Computational Linguistics",
        venue_query="ACL",
        years=[2024, 2023, 2022]
    ),
    "NAACL": SemanticScholarConfig(
        name="NAACL",
        full_name="North American Chapter of the ACL",
        venue_query="NAACL",
        years=[2024, 2022]
    ),

    # ========== 人工智能综合会议 ==========
    "AAAI": SemanticScholarConfig(
        name="AAAI",
        full_name="AAAI Conference on Artificial Intelligence",
        venue_query="AAAI",
        years=[2024, 2023, 2022]
    ),
    "IJCAI": SemanticScholarConfig(
        name="IJCAI",
        full_name="International Joint Conference on Artificial Intelligence",
        venue_query="IJCAI",
        years=[2024, 2023, 2022]
    ),
}


class SemanticScholarClient:
    """Semantic Scholar API 客户端"""

    def __init__(self, api_key: Optional[str] = None, timeout: float = 30.0):
        """
        初始化客户端

        Args:
            api_key: API Key（可选，用于提高速率限制）
        """
        self.api_key = api_key
        self.timeout = timeout
        self.session = requests.Session()
        if api_key:
            self.session.headers["x-api-key"] = api_key

        # 速率限制：无 key 时 100 req/5min
        self.request_delay = 0.5

    def search_papers(
        self,
        venue: str,
        year: int,
        limit: Optional[int] = None,
    ) -> List[Dict[str, Any]]:
        """
        搜索指定会议和年份的论文

        Args:
            venue: 会议名称（如 "CVPR"）
            year: 年份
            limit: 返回数量限制

        Returns:
            论文数据列表
        """
        papers = []
        token = None

        while True:
            params = {
                "query": "",
                "venue": venue,
                "year": str(year),
                "fields": ",".join(S2_FIELDS),
                "limit": min(limit or 1000, 1000),
            }

            if token:
                params["token"] = token

            try:
                response = self.session.get(S2_SEARCH_URL, params=params, timeout=self.timeout)
                response.raise_for_status()
                data = response.json()

                batch = data.get("data", [])
                papers.extend(batch)

                # 检查是否有更多页
                token = data.get("token")
                if not token or (limit and len(papers) >= limit):
                    break

                time.sleep(self.request_delay)

            except requests.RequestException:
                logger.exception(
                    "Semantic Scholar API request failed for venue=%s year=%s",
                    venue,
                    year,
                )
                break

        if limit:
            papers = papers[:limit]

        return papers

    def get_paper_by_id(self, paper_id: str) -> Optional[Dict[str, Any]]:
        """获取单篇论文详情"""
        try:
            url = f"{S2_PAPER_URL}/{paper_id}"
            params = {"fields": ",".join(S2_FIELDS)}
            response = self.session.get(url, params=params, timeout=self.timeout)
            response.raise_for_status()
            return response.json()
        except requests.RequestException:
            logger.exception("Failed to fetch Semantic Scholar paper %s", paper_id)
            return None


def parse_s2_paper(data: Dict[str, Any], venue: str, year: int) -> Optional[Paper]:
    """
    将 Semantic Scholar 数据转换为 Paper 对象

    Args:
        data: Semantic Scholar 论文数据
        venue: 会议名称
        year: 年份

    Returns:
        Paper 对象
    """
    try:
        paper_id = data.get("paperId", "")
        title = data.get("title", "")
        abstract = data.get("abstract", "")

        # 提取作者名
        authors = []
        for author in data.get("authors", []):
            if isinstance(author, dict):
                name = author.get("name", "")
                if name:
                    authors.append(name)

        # URL
        url = data.get("url", f"https://www.semanticscholar.org/paper/{paper_id}")

        return Paper(
            id=f"s2:{paper_id}",  # 添加前缀区分来源
            title=title,
            abstract=abstract or "",
            authors=authors,
            venue=venue,
            year=year,
            url=url,
            keywords=[],  # Semantic Scholar 不直接提供关键词
        )
    except Exception:
        logger.exception("Failed to parse Semantic Scholar paper %s", data.get("paperId", "<unknown>"))
        return None


def scrape_s2_venue(
    config: SemanticScholarConfig,
    year: int,
    client: Optional[SemanticScholarClient] = None,
    limit: Optional[int] = None,
) -> List[Paper]:
    """
    爬取指定会议的论文（通过 Semantic Scholar）

    Args:
        config: 会议配置
        year: 年份
        client: S2 客户端
        limit: 论文数量限制

    Returns:
        论文列表
    """
    if client is None:
        client = SemanticScholarClient()

    print(f"\n🔍 正在从 Semantic Scholar 获取 {config.name} {year}...")

    raw_papers = client.search_papers(config.venue_query, year, limit)

    papers = []
    for data in raw_papers:
        paper = parse_s2_paper(data, config.name, year)
        if paper and paper.title:  # 过滤无效论文
            papers.append(paper)

    print(f"✅ {config.name} {year}: 获取 {len(papers)} 篇论文")
    return papers


def scrape_all_s2_venues(
    venues: Optional[Dict[str, SemanticScholarConfig]] = None,
    years: Optional[List[int]] = None,
    limit_per_venue: Optional[int] = None,
    max_age_days: int = 7,
    repository = None,
) -> List[Paper]:
    """
    爬取所有 Semantic Scholar 会议

    Args:
        venues: 会议配置
        years: 年份列表
        limit_per_venue: 每个会议的论文限制
        max_age_days: 最大爬取间隔天数，在此时间内爬取过的会议将被跳过（默认 7 天）
        repository: 数据库仓库（用于检查和记录爬取日志）

    Returns:
        所有论文列表
    """
    if venues is None:
        venues = S2_VENUES

    client = SemanticScholarClient()
    all_papers = []
    skipped_count = 0

    for venue_name, config in venues.items():
        venue_years = years if years is not None else config.years

        for year in venue_years:
            # 检查是否需要爬取
            if repository is not None and not repository.should_scrape(config.name, year, max_age_days):
                print(f"⏭️ 跳过 {config.name} {year}（{max_age_days} 天内已爬取）")
                skipped_count += 1
                continue

            try:
                papers = scrape_s2_venue(config, year, client, limit_per_venue)
                all_papers.extend(papers)

                # 记录爬取日志
                if repository is not None and papers:
                    repository.log_scrape(config.name, year, len(papers))

            except Exception:
                logger.exception("Failed to scrape Semantic Scholar venue %s %s", venue_name, year)
                continue

    print(f"\n📊 Semantic Scholar 总计获取 {len(all_papers)} 篇论文（跳过 {skipped_count} 个会议年份）")
    return all_papers

