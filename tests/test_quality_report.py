"""Quality warning threshold tests."""

from services.quality_report import build_warnings


def _codes(metrics):
    return {warning["code"] for warning in build_warnings(metrics)}


def test_unknown_quality_ratio_threshold():
    assert "unknown_quality_ratio_high" in _codes({"unknown_quality_ratio": 0.31})


def test_empty_abstract_ratio_threshold():
    assert "empty_abstract_ratio_high" in _codes({"empty_abstract_ratio": 0.21})


def test_single_source_ratio_threshold():
    assert "single_source_ratio_high" in _codes({"single_source_ratio": 0.81})


def test_small_sample_threshold():
    assert "small_sample" in _codes({"matched_papers": 4})


def test_low_topic_match_confidence_threshold():
    assert "low_topic_match_confidence" in _codes({"topic_match_confidence": 0.69})


def test_only_arxiv_conference_query_warning():
    assert "only_arxiv_evidence_for_conference_query" in _codes(
        {"only_arxiv_evidence_for_conference_query": True}
    )
