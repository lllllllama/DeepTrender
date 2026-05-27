"""Pipeline crawl option tests."""

from main import (
    FULL_CRAWL_ARXIV_DAYS,
    FULL_CRAWL_ARXIV_MAX_RESULTS,
    FULL_CRAWL_PROCESSING_LIMIT,
    resolve_crawl_options,
    run_topic_fact_rebuild,
)


def test_full_crawl_expands_bootstrap_defaults():
    options = resolve_crawl_options(full_crawl=True)

    assert options["sources"] == ["arxiv", "openalex", "s2", "openreview"]
    assert options["arxiv_days"] == FULL_CRAWL_ARXIV_DAYS
    assert options["arxiv_max_results"] == FULL_CRAWL_ARXIV_MAX_RESULTS
    assert options["limit"] == FULL_CRAWL_PROCESSING_LIMIT
    assert {"ICLR", "NeurIPS", "CVPR", "ACL", "KDD", "SIGMOD", "ICSE"}.issubset(
        set(options["venues"])
    )
    assert {"PPoPP", "SIGCOMM", "CCS", "STOC", "ACM MM", "CHI", "WWW"}.issubset(
        set(options["venues"])
    )
    assert len(options["venues"]) >= 360
    assert {2020, 2021, 2022, 2023, 2024, 2025}.issubset(set(options["years"]))


def test_full_crawl_preserves_explicit_scope_but_raises_caps():
    options = resolve_crawl_options(
        sources=["arxiv"],
        arxiv_days=30,
        arxiv_max_results=2000,
        venues=["ICLR"],
        years=[2024],
        limit=1000,
        full_crawl=True,
    )

    assert options["sources"] == ["arxiv"]
    assert options["venues"] == ["ICLR"]
    assert options["years"] == [2024]
    assert options["arxiv_days"] == FULL_CRAWL_ARXIV_DAYS
    assert options["arxiv_max_results"] == FULL_CRAWL_ARXIV_MAX_RESULTS
    assert options["limit"] == FULL_CRAWL_PROCESSING_LIMIT


def test_incremental_options_keep_small_defaults():
    options = resolve_crawl_options(
        sources=["arxiv"],
        arxiv_days=7,
        arxiv_max_results=1000,
        limit=5000,
        full_crawl=False,
    )

    assert options["sources"] == ["arxiv"]
    assert options["arxiv_days"] == 7
    assert options["arxiv_max_results"] == 1000
    assert options["limit"] == 5000


def test_full_crawl_can_filter_and_batch_ccf_registry_scope():
    options = resolve_crawl_options(
        full_crawl=True,
        ccf_tier="A",
        ccf_domain="AI",
        venue_offset=1,
        venue_count=3,
    )

    assert len(options["venues"]) == 3
    assert set(options["venues"]).issubset(
        {"ICLR", "NeurIPS", "ICML", "EMNLP", "COLM", "CoRL", "LOG", "AISTATS"}
        | {"AAAI", "ACL", "CVPR", "ICCV", "IJCAI"}
    )


def test_topic_fact_rebuild_runs_by_default():
    calls = []

    def fake_rebuild(**kwargs):
        calls.append(kwargs)
        return {
            "processed_papers": 3,
            "matched_papers": 2,
            "topic_match_count": 4,
            "warnings": [],
        }

    summary = run_topic_fact_rebuild(rebuild_func=fake_rebuild)

    assert calls == [{"include_children": False}]
    assert summary["topic_match_count"] == 4


def test_topic_fact_rebuild_can_include_children():
    calls = []

    def fake_rebuild(**kwargs):
        calls.append(kwargs)
        return {
            "processed_papers": 1,
            "matched_papers": 1,
            "topic_match_count": 2,
            "warnings": [],
        }

    run_topic_fact_rebuild(include_child_topics=True, rebuild_func=fake_rebuild)

    assert calls == [{"include_children": True}]


def test_topic_fact_rebuild_can_be_skipped():
    calls = []

    def fake_rebuild(**kwargs):
        calls.append(kwargs)
        return {
            "processed_papers": 1,
            "matched_papers": 1,
            "topic_match_count": 1,
            "warnings": [],
        }

    summary = run_topic_fact_rebuild(skip_topic_facts=True, rebuild_func=fake_rebuild)

    assert summary is None
    assert calls == []
