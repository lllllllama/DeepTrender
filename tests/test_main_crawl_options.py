"""Pipeline crawl option tests."""

from main import (
    FULL_CRAWL_ARXIV_DAYS,
    FULL_CRAWL_ARXIV_MAX_RESULTS,
    FULL_CRAWL_PROCESSING_LIMIT,
    resolve_crawl_options,
)


def test_full_crawl_expands_bootstrap_defaults():
    options = resolve_crawl_options(full_crawl=True)

    assert options["sources"] == ["arxiv", "openalex", "s2", "openreview"]
    assert options["arxiv_days"] == FULL_CRAWL_ARXIV_DAYS
    assert options["arxiv_max_results"] == FULL_CRAWL_ARXIV_MAX_RESULTS
    assert options["limit"] == FULL_CRAWL_PROCESSING_LIMIT
    assert {"ICLR", "NeurIPS", "CVPR", "ACL"}.issubset(set(options["venues"]))
    assert {2021, 2022, 2023, 2024, 2025}.issubset(set(options["years"]))


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
