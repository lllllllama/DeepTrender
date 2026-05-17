"""Centralized v0.1 quality and warning helpers."""

from __future__ import annotations

from typing import Any

THRESHOLDS = {
    "unknown_quality_ratio": 0.30,
    "empty_abstract_ratio": 0.20,
    "single_source_ratio": 0.80,
    "matched_papers": 5,
    "topic_match_confidence": 0.70,
}


def _number(value: Any) -> float | None:
    if value is None:
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _warning(
    code: str,
    metric: str,
    value: float,
    threshold: float,
    *,
    high: bool = True,
    severity: str = "medium",
) -> dict[str, Any]:
    relation = "above" if high else "below"
    return {
        "code": code,
        "message": f"{metric} is {value:.2f}, {relation} threshold {threshold:.2f}.",
        "severity": severity,
        "value": value,
        "threshold": threshold,
    }


def build_warnings(metrics: dict) -> list[dict]:
    """Build stable v0.1 warning objects from metric values."""

    warnings: list[dict] = []

    unknown_quality_ratio = _number(metrics.get("unknown_quality_ratio"))
    if unknown_quality_ratio is not None and unknown_quality_ratio > THRESHOLDS["unknown_quality_ratio"]:
        warnings.append(
            _warning(
                "unknown_quality_ratio_high",
                "unknown_quality_ratio",
                unknown_quality_ratio,
                THRESHOLDS["unknown_quality_ratio"],
            )
        )

    empty_abstract_ratio = _number(metrics.get("empty_abstract_ratio"))
    if empty_abstract_ratio is not None and empty_abstract_ratio > THRESHOLDS["empty_abstract_ratio"]:
        warnings.append(
            _warning(
                "empty_abstract_ratio_high",
                "empty_abstract_ratio",
                empty_abstract_ratio,
                THRESHOLDS["empty_abstract_ratio"],
            )
        )

    single_source_ratio = _number(metrics.get("single_source_ratio"))
    if single_source_ratio is not None and single_source_ratio > THRESHOLDS["single_source_ratio"]:
        warnings.append(
            _warning(
                "single_source_ratio_high",
                "single_source_ratio",
                single_source_ratio,
                THRESHOLDS["single_source_ratio"],
            )
        )

    matched_papers = _number(metrics.get("matched_papers"))
    if matched_papers is not None and matched_papers < THRESHOLDS["matched_papers"]:
        warnings.append(
            _warning(
                "small_sample",
                "matched_papers",
                matched_papers,
                THRESHOLDS["matched_papers"],
                high=False,
            )
        )

    topic_match_confidence = _number(metrics.get("topic_match_confidence"))
    if (
        topic_match_confidence is not None
        and topic_match_confidence < THRESHOLDS["topic_match_confidence"]
    ):
        warnings.append(
            _warning(
                "low_topic_match_confidence",
                "topic_match_confidence",
                topic_match_confidence,
                THRESHOLDS["topic_match_confidence"],
                high=False,
            )
        )

    if metrics.get("only_arxiv_evidence_for_conference_query"):
        warnings.append(
            {
                "code": "only_arxiv_evidence_for_conference_query",
                "message": "Conference query is supported only by arXiv preprint evidence.",
                "severity": "high",
                "value": True,
                "threshold": None,
            }
        )

    return warnings
