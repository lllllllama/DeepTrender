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
from .ccf_registry import load_ccf_venue_registry


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


RECENT_ANNUAL_YEARS = [2025, 2024, 2023, 2022, 2021, 2020]
RECENT_ODD_CV_YEARS = [2025, 2023, 2021]
RECENT_EVEN_CV_YEARS = [2024, 2022, 2020]


# 支持的会议（通过 Semantic Scholar）
S2_VENUES: Dict[str, SemanticScholarConfig] = {
    # ========== 计算机视觉会议 ==========
    "CVPR": SemanticScholarConfig(
        name="CVPR",
        full_name="IEEE/CVF Conference on Computer Vision and Pattern Recognition",
        venue_query="CVPR",
        years=RECENT_ANNUAL_YEARS,
    ),
    "ICCV": SemanticScholarConfig(
        name="ICCV",
        full_name="IEEE/CVF International Conference on Computer Vision",
        venue_query="ICCV",
        years=RECENT_ODD_CV_YEARS,
    ),
    "ECCV": SemanticScholarConfig(
        name="ECCV",
        full_name="European Conference on Computer Vision",
        venue_query="ECCV",
        years=RECENT_EVEN_CV_YEARS,
    ),

    # ========== 自然语言处理会议 ==========
    "ACL": SemanticScholarConfig(
        name="ACL",
        full_name="Annual Meeting of the Association for Computational Linguistics",
        venue_query="ACL",
        years=RECENT_ANNUAL_YEARS,
    ),
    "NAACL": SemanticScholarConfig(
        name="NAACL",
        full_name="North American Chapter of the ACL",
        venue_query="NAACL",
        years=[2025, 2024, 2022, 2021],
    ),

    # ========== 人工智能综合会议 ==========
    "AAAI": SemanticScholarConfig(
        name="AAAI",
        full_name="AAAI Conference on Artificial Intelligence",
        venue_query="AAAI",
        years=RECENT_ANNUAL_YEARS,
    ),
    "IJCAI": SemanticScholarConfig(
        name="IJCAI",
        full_name="International Joint Conference on Artificial Intelligence",
        venue_query="IJCAI",
        years=RECENT_ANNUAL_YEARS,
    ),
    "WACV": SemanticScholarConfig("WACV", "IEEE/CVF Winter Conference on Applications of Computer Vision", "WACV", RECENT_ANNUAL_YEARS),
    "ACM MM": SemanticScholarConfig("ACM MM", "ACM International Conference on Multimedia", "ACM Multimedia", RECENT_ANNUAL_YEARS),
    "COLING": SemanticScholarConfig("COLING", "International Conference on Computational Linguistics", "COLING", [2025, 2024, 2022, 2020]),
    "EACL": SemanticScholarConfig("EACL", "European Chapter of the Association for Computational Linguistics", "EACL", [2024, 2023, 2021]),
    "UAI": SemanticScholarConfig("UAI", "Conference on Uncertainty in Artificial Intelligence", "UAI", RECENT_ANNUAL_YEARS),
    "COLT": SemanticScholarConfig("COLT", "Conference on Learning Theory", "COLT", RECENT_ANNUAL_YEARS),
    "KDD": SemanticScholarConfig("KDD", "ACM SIGKDD Conference on Knowledge Discovery and Data Mining", "KDD", RECENT_ANNUAL_YEARS),
    "SIGIR": SemanticScholarConfig("SIGIR", "International ACM SIGIR Conference on Research and Development in Information Retrieval", "SIGIR", RECENT_ANNUAL_YEARS),
    "WWW": SemanticScholarConfig("WWW", "The Web Conference", "WWW", RECENT_ANNUAL_YEARS),
    "WSDM": SemanticScholarConfig("WSDM", "ACM International Conference on Web Search and Data Mining", "WSDM", RECENT_ANNUAL_YEARS),
    "CIKM": SemanticScholarConfig("CIKM", "ACM International Conference on Information and Knowledge Management", "CIKM", RECENT_ANNUAL_YEARS),
    "ICDM": SemanticScholarConfig("ICDM", "IEEE International Conference on Data Mining", "ICDM", RECENT_ANNUAL_YEARS),
    "SIGMOD": SemanticScholarConfig("SIGMOD", "ACM SIGMOD International Conference on Management of Data", "Proceedings of the ACM on Management of Data", RECENT_ANNUAL_YEARS),
    "VLDB": SemanticScholarConfig("VLDB", "International Conference on Very Large Data Bases", "Proceedings of the VLDB Endowment", RECENT_ANNUAL_YEARS),
    "ICDE": SemanticScholarConfig("ICDE", "IEEE International Conference on Data Engineering", "ICDE", RECENT_ANNUAL_YEARS),
    "ICSE": SemanticScholarConfig("ICSE", "International Conference on Software Engineering", "ICSE", RECENT_ANNUAL_YEARS),
    "FSE": SemanticScholarConfig("FSE", "ACM International Conference on the Foundations of Software Engineering", "FSE", RECENT_ANNUAL_YEARS),
    "CHI": SemanticScholarConfig("CHI", "ACM CHI Conference on Human Factors in Computing Systems", "CHI", RECENT_ANNUAL_YEARS),
    "UIST": SemanticScholarConfig("UIST", "ACM Symposium on User Interface Software and Technology", "UIST", RECENT_ANNUAL_YEARS),
    "ICRA": SemanticScholarConfig("ICRA", "IEEE International Conference on Robotics and Automation", "ICRA", RECENT_ANNUAL_YEARS),
    "IROS": SemanticScholarConfig("IROS", "IEEE/RSJ International Conference on Intelligent Robots and Systems", "IROS", RECENT_ANNUAL_YEARS),
}


def _extend_s2_venues_from_ccf_registry() -> None:
    """Populate Semantic Scholar coverage from the CCF venue registry."""

    for venue in load_ccf_venue_registry().values():
        if not venue.s2_venue_key:
            continue
        S2_VENUES.setdefault(
            venue.canonical_name,
            SemanticScholarConfig(
                name=venue.canonical_name,
                full_name=venue.full_name,
                venue_query=venue.s2_venue_key,
                years=RECENT_ANNUAL_YEARS,
            ),
        )


_extend_s2_venues_from_ccf_registry()


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
        # Semantic Scholar's unauthenticated limit is low; stay below
        # 100 requests per 5 minutes and explicitly back off on 429.
        self.request_delay = 1.0 if api_key else 3.2

    def _get_with_retries(self, url: str, params: Dict[str, Any]) -> Optional[requests.Response]:
        for attempt in range(4):
            try:
                response = self.session.get(url, params=params, timeout=self.timeout)
                if response.status_code == 429:
                    retry_after = response.headers.get("Retry-After")
                    try:
                        wait_seconds = float(retry_after) if retry_after else 0.0
                    except ValueError:
                        wait_seconds = 0.0
                    wait_seconds = max(wait_seconds, self.request_delay * (attempt + 1))
                    logger.warning(
                        "Semantic Scholar rate limited; sleeping %.1fs before retry %s/4",
                        wait_seconds,
                        attempt + 1,
                    )
                    time.sleep(wait_seconds)
                    continue
                response.raise_for_status()
                return response
            except requests.RequestException:
                if attempt == 3:
                    logger.exception("Semantic Scholar API request failed: %s", url)
                    return None
                time.sleep(self.request_delay * (attempt + 1))
        return None

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
                response = self._get_with_retries(S2_SEARCH_URL, params=params)
                if response is None:
                    break
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
            response = self._get_with_retries(url, params=params)
            if response is None:
                return None
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

