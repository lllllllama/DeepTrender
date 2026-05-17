"""
配置管理模块

包含会议配置、路径配置和提取器配置。
"""

from pathlib import Path
from dataclasses import dataclass, field
from typing import List, Dict
import os
from dotenv import load_dotenv

# 加载环境变量
load_dotenv()

# 项目根目录
ROOT_DIR = Path(__file__).parent.parent
DATA_DIR = ROOT_DIR / "data"
OUTPUT_DIR = ROOT_DIR / "output"
FIGURES_DIR = OUTPUT_DIR / "figures"
REPORTS_DIR = OUTPUT_DIR / "reports"

# 确保目录存在
DATA_DIR.mkdir(exist_ok=True)
OUTPUT_DIR.mkdir(exist_ok=True)
FIGURES_DIR.mkdir(exist_ok=True)
REPORTS_DIR.mkdir(exist_ok=True)

# 数据库路径
DATABASE_PATH = DATA_DIR / "keywords.db"


def _load_arxiv_categories_from_domains_yaml(default: List[str]) -> List[str]:
    """Load arXiv categories from taxonomy domains, falling back safely."""

    taxonomy_path = ROOT_DIR / "config" / "taxonomy" / "domains.yaml"
    if not taxonomy_path.exists():
        return default
    try:
        import yaml

        data = yaml.safe_load(taxonomy_path.read_text(encoding="utf-8")) or {}
        categories = []
        for domain in data.get("domains", {}).values():
            categories.extend(domain.get("arxiv_categories", []))
        return sorted(set(categories)) or default
    except Exception:
        return default


@dataclass
class VenueConfig:
    """会议配置"""
    name: str  # 会议简称，如 ICLR
    full_name: str  # 会议全称
    venue_id_pattern: str  # OpenReview venue ID 模式，如 "ICLR.cc/{year}/Conference"
    years: List[int] = field(default_factory=list)  # 要爬取的年份


# 支持的会议配置
# 说明：仅包含 OpenReview 上确认可用的会议
# 年份从新到旧排列，优先爬取最新数据
VENUES: Dict[str, VenueConfig] = {
    # ========== 机器学习核心会议 (ML Core) ==========
    "ICLR": VenueConfig(
        name="ICLR",
        full_name="International Conference on Learning Representations",
        venue_id_pattern="ICLR.cc/{year}/Conference",
        years=[2025, 2024, 2023, 2022, 2021]
    ),
    "NeurIPS": VenueConfig(
        name="NeurIPS",
        full_name="Conference on Neural Information Processing Systems",
        venue_id_pattern="NeurIPS.cc/{year}/Conference",
        years=[2024, 2023, 2022, 2021]
    ),
    "ICML": VenueConfig(
        name="ICML",
        full_name="International Conference on Machine Learning",
        venue_id_pattern="ICML.cc/{year}/Conference",
        years=[2024, 2023, 2022, 2021]
    ),
    
    # ========== 自然语言处理会议 (NLP) ==========
    "EMNLP": VenueConfig(
        name="EMNLP",
        full_name="Conference on Empirical Methods in Natural Language Processing",
        venue_id_pattern="EMNLP.cc/{year}/Conference",
        years=[2024, 2023]
    ),
    "COLM": VenueConfig(
        name="COLM",
        full_name="Conference on Language Modeling",
        venue_id_pattern="COLM.cc/{year}/Conference",
        years=[2024]  # 2024 首届
    ),
    
    # ========== 机器人与强化学习会议 ==========
    "CoRL": VenueConfig(
        name="CoRL",
        full_name="Conference on Robot Learning",
        venue_id_pattern="robot-learning.org/{year}/Conference",
        years=[2024, 2023, 2022]
    ),
    
    # ========== 图学习会议 ==========
    "LOG": VenueConfig(
        name="LOG",
        full_name="Learning on Graphs Conference",
        venue_id_pattern="logconference.org/{year}/Conference",
        years=[2024, 2023, 2022]
    ),
    
    # ========== 统计学习会议 ==========
    "AISTATS": VenueConfig(
        name="AISTATS",
        full_name="International Conference on Artificial Intelligence and Statistics",
        venue_id_pattern="AISTATS.cc/{year}/Conference",
        years=[2024, 2023, 2022]
    ),
}


@dataclass
class ExtractorConfig:
    """关键词提取配置"""
    # YAKE 配置
    yake_language: str = "en"
    yake_max_ngram_size: int = 3
    yake_deduplication_threshold: float = 0.9
    yake_num_keywords: int = 20
    
    # KeyBERT 配置
    keybert_model: str = "all-MiniLM-L6-v2"  # 轻量级模型
    keybert_top_n: int = 20
    keybert_keyphrase_ngram_range: tuple = (1, 3)
    
    # 默认提取器
    default_extractor: str = "yake"  # 可选: "yake", "keybert", "both"


# 默认配置实例
EXTRACTOR_CONFIG = ExtractorConfig()


@dataclass
class VisualizationConfig:
    """可视化配置"""
    # 图表尺寸
    figure_width: int = 12
    figure_height: int = 8
    dpi: int = 150
    
    # 词云配置
    wordcloud_width: int = 1600
    wordcloud_height: int = 800
    wordcloud_background_color: str = "white"
    wordcloud_colormap: str = "viridis"
    wordcloud_max_words: int = 100
    
    # 柱状图配置
    bar_chart_top_k: int = 20
    bar_chart_color: str = "#4C72B0"
    
    # 主题
    font_family: str = "DejaVu Sans"


VISUALIZATION_CONFIG = VisualizationConfig()


# OpenReview API 配置
OPENREVIEW_API_URL = "https://api2.openreview.net"
OPENREVIEW_USERNAME = os.getenv("OPENREVIEW_USERNAME", "")
OPENREVIEW_PASSWORD = os.getenv("OPENREVIEW_PASSWORD", "")

# arXiv 配置
ARXIV_CATEGORIES = _load_arxiv_categories_from_domains_yaml(
    default=["cs.CV", "cs.CL", "cs.LG", "cs.AI", "cs.RO", "stat.ML"]
)

# OpenAlex 配置
OPENALEX_EMAIL = os.getenv("OPENALEX_EMAIL", "")

# 领域分类关键词
DOMAIN_CATEGORIES = {
    "CV": ["cs.CV", "computer vision", "image", "video", "visual"],
    "NLP": ["cs.CL", "natural language", "nlp", "text", "language model"],
    "ML": ["cs.LG", "stat.ML", "machine learning", "deep learning"],
    "RL": ["cs.AI", "reinforcement learning", "robot", "control"],
    "AI": ["artificial intelligence", "neural network"],
}
