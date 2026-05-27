"""arXiv metric-contract regression tests."""

from datetime import datetime
import json

from analysis.arxiv_agent import ArxivAnalysisAgent
from scraper.models import RawPaper, create_legacy_paper
from tools.export_static_site import StaticSiteExporter


def _save_linked_arxiv(repo, *, arxiv_id, title, category, published_at, keywords, year=2024):
    raw_id = repo.raw.save_raw_paper(
        RawPaper(
            source="arxiv",
            source_paper_id=arxiv_id,
            title=title,
            categories=category,
            year=year,
            published_at=published_at,
        )
    )
    paper = create_legacy_paper(
        id=arxiv_id,
        title=title,
        abstract="A short abstract.",
        authors=["A. Tester"],
        venue="arXiv",
        year=year,
        url=f"https://arxiv.org/abs/{arxiv_id}",
        keywords=keywords,
    )
    assert repo.save_paper(paper) is True
    repo.structured.link_paper_source(paper.paper_id, raw_id, "arxiv")
    return paper.paper_id


def test_arxiv_keyword_count_is_distinct_paper_id_and_alias_deduped(repo):
    _save_linked_arxiv(
        repo,
        arxiv_id="2401.00001",
        title="LLM aliases in one paper",
        category="cs.LG",
        published_at=datetime(2024, 1, 10),
        keywords=["large language model", "language models"],
    )
    _save_linked_arxiv(
        repo,
        arxiv_id="2401.00002",
        title="LLM aliases in another paper",
        category="cs.LG",
        published_at=datetime(2024, 1, 11),
        keywords=["large language"],
    )

    agent = ArxivAnalysisAgent(analysis_repo=repo.analysis, raw_repo=repo.raw)
    result = agent.run("year", "cs.LG", force=True)
    assert result["paper_count"] == 2

    series = repo.analysis.get_arxiv_timeseries("cs.LG", "year")
    keywords = {item["keyword"]: item for item in series[0]["top_keywords"]}
    assert keywords["large language model"]["count"] == 2
    assert keywords["large language model"]["relative_frequency"] == 1.0
    assert keywords["large language model"]["rank"] == 1
    assert keywords["large language model"]["evidence"]


def test_arxiv_category_keyword_cache_is_isolated(repo):
    _save_linked_arxiv(
        repo,
        arxiv_id="2402.00001",
        title="Vision paper",
        category="cs.CV",
        published_at=datetime(2024, 2, 1),
        keywords=["computer vision"],
    )
    _save_linked_arxiv(
        repo,
        arxiv_id="2402.00002",
        title="Language paper",
        category="cs.CL",
        published_at=datetime(2024, 2, 1),
        keywords=["natural language processing"],
    )

    agent = ArxivAnalysisAgent(analysis_repo=repo.analysis, raw_repo=repo.raw)
    repo.analysis.save_arxiv_timeseries("cs.CV", "year", "1999", 99, [])
    agent.run("year", "cs.CV", force=True)
    agent.run("year", "cs.CL", force=True)

    cv = repo.analysis.get_keyword_trends_cached("arxiv", "computer vision", "year", venue="cs.CV")
    cl = repo.analysis.get_keyword_trends_cached("arxiv", "computer vision", "year", venue="cs.CL")
    assert cv and cv[0]["count"] == 1
    assert cl == []
    assert [row["bucket"] for row in repo.analysis.get_arxiv_timeseries("cs.CV", "year")] == ["2024"]


def test_arxiv_all_granularities_use_published_at(repo):
    _save_linked_arxiv(
        repo,
        arxiv_id="2403.00001",
        title="Published bucket paper",
        category="cs.AI",
        published_at=datetime(2023, 12, 31),
        keywords=["reasoning"],
        year=2024,
    )

    agent = ArxivAnalysisAgent(analysis_repo=repo.analysis, raw_repo=repo.raw)
    agent.run_all_granularities("cs.AI", force=True)

    assert repo.analysis.get_arxiv_timeseries("cs.AI", "year")[0]["bucket"] == "2023"
    assert repo.analysis.get_arxiv_timeseries("cs.AI", "month")[0]["bucket"] == "2023-12"
    assert repo.analysis.get_arxiv_timeseries("cs.AI", "week")[0]["bucket"] == "2023-W52"
    assert repo.analysis.get_arxiv_timeseries("cs.AI", "day")[0]["bucket"] == "2023-12-31"


def test_arxiv_empty_evidence_requires_warning(repo):
    repo.raw.save_raw_paper(
        RawPaper(
            source="arxiv",
            source_paper_id="2404.00001",
            title="Unmapped raw paper",
            categories="cs.RO",
            published_at=datetime(2024, 4, 1),
        )
    )
    agent = ArxivAnalysisAgent(analysis_repo=repo.analysis, raw_repo=repo.raw)
    agent.run("month", "cs.RO", force=True)

    series = repo.analysis.get_arxiv_timeseries("cs.RO", "month")
    assert series[0]["paper_count"] == 0
    assert series[0]["top_keywords"] == []
    assert {warning["code"] for warning in series[0]["warnings"]} >= {
        "missing_source_mapping",
        "registered_no_papers",
    }


def test_static_arxiv_json_and_manifest_contract(repo, tmp_path):
    _save_linked_arxiv(
        repo,
        arxiv_id="2405.00001",
        title="Exported arxiv paper",
        category="cs.LG",
        published_at=datetime(2024, 5, 1),
        keywords=["transformer"],
    )
    ArxivAnalysisAgent(analysis_repo=repo.analysis, raw_repo=repo.raw).run_default_categories(force=True)

    exporter = StaticSiteExporter(output_dir=str(tmp_path), top_keywords=300, repository=repo)
    exporter.export_all()

    expected_files = [
        tmp_path / "data" / "arxiv" / "arxiv_timeseries_year_cs.LG.json",
        tmp_path / "data" / "arxiv" / "arxiv_keywords_index_cs.LG.json",
        tmp_path / "data" / "arxiv" / "arxiv_keyword_trends_year_cs.LG.json",
        tmp_path / "data" / "arxiv" / "arxiv_quality_cs.LG.json",
        tmp_path / "data" / "manifest.json",
    ]
    for path in expected_files:
        with path.open("r", encoding="utf-8") as handle:
            json.load(handle)

    manifest = json.loads((tmp_path / "data" / "manifest.json").read_text(encoding="utf-8"))
    for field in [
        "generated_at",
        "stale_status",
        "arxiv_categories_exported",
        "venues_exported",
        "venues_with_data",
        "venues_without_data",
        "keyword_coverage_ratio",
        "topic_fact_coverage_ratio",
    ]:
        assert field in manifest
