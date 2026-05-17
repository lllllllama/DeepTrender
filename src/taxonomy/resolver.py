"""Resolve domains and canonical topics from v0.1 taxonomy files."""

from __future__ import annotations

import re
from typing import Any

from .loader import load_aliases as _load_aliases
from .loader import load_domains as _load_domains
from .loader import load_topics as _load_topics


def load_domains() -> dict[str, dict[str, Any]]:
    """Compatibility wrapper required by the v0.1 resolver contract."""

    return _load_domains()


def load_topics() -> dict[str, dict[str, Any]]:
    """Compatibility wrapper required by the v0.1 resolver contract."""

    return _load_topics()


def load_aliases() -> dict[str, str]:
    """Compatibility wrapper required by the v0.1 resolver contract."""

    return _load_aliases()


def _strict_normalize(value: str | None) -> str:
    value = (value or "").strip().lower()
    return re.sub(r"\s+", " ", value)


def _loose_normalize(value: str | None) -> str:
    value = (value or "").strip().lower()
    value = value.replace("_", " ").replace("-", " ")
    value = re.sub(r"[^a-z0-9.+]+", " ", value)
    return re.sub(r"\s+", " ", value).strip()


def _warning_low_confidence(value: float) -> dict[str, Any]:
    return {
        "code": "low_topic_match_confidence",
        "message": f"topic_match_confidence is {value:.2f}, below threshold 0.70.",
        "severity": "medium",
        "value": value,
        "threshold": 0.70,
    }


def _child_topic_ids(topic_id: str) -> list[str]:
    topics = load_topics()
    children = [
        candidate_id
        for candidate_id, topic in topics.items()
        if topic_id in topic.get("parent_topics", [])
    ]
    result: list[str] = []
    for child_id in sorted(children):
        result.append(child_id)
        result.extend(_child_topic_ids(child_id))
    return result


def _aliases_by_topic() -> dict[str, list[str]]:
    aliases_by_topic: dict[str, list[str]] = {}
    for alias, topic_id in load_aliases().items():
        aliases_by_topic.setdefault(topic_id, []).append(alias)
    for topic_id, topic in load_topics().items():
        for alias in topic.get("aliases", []):
            aliases_by_topic.setdefault(topic_id, []).append(alias)
    return aliases_by_topic


def _alias_index() -> dict[str, tuple[str, str]]:
    index: dict[str, tuple[str, str]] = {}
    for topic_id, aliases in _aliases_by_topic().items():
        for alias in aliases:
            index[_loose_normalize(alias)] = (topic_id, alias)
    return index


def _resolution(
    *,
    input_value: str,
    topic_id: str | None,
    match_method: str,
    confidence: float,
    include_children: bool,
    aliases_used: list[str] | None = None,
) -> dict[str, Any]:
    topics = load_topics()
    topic = topics.get(topic_id or "", {})
    warnings = []
    if confidence < 0.7:
        warnings.append(_warning_low_confidence(confidence))

    child_topic_ids = _child_topic_ids(topic_id) if topic_id and include_children else []
    return {
        "input": input_value,
        "topic_id": topic_id,
        "canonical_topic": topic.get("canonical_name"),
        "domain": topic.get("domain"),
        "secondary_domains": topic.get("secondary_domains", []),
        "match_method": match_method,
        "confidence": confidence,
        "include_children": include_children,
        "child_topic_ids": child_topic_ids,
        "aliases_used": aliases_used or [],
        "warnings": warnings,
    }


def resolve_domain(
    arxiv_categories: list[str],
    text: str | None = None,
) -> dict[str, Any]:
    """Resolve a coarse domain from arXiv categories and optional text."""

    domains = load_domains()
    category_set = {_strict_normalize(category) for category in arxiv_categories or []}
    for domain_id, domain in domains.items():
        configured = {_strict_normalize(category) for category in domain.get("arxiv_categories", [])}
        matched = sorted(category_set & configured)
        if matched:
            return {
                "domain": domain_id,
                "name": domain.get("name"),
                "match_method": "arxiv_category",
                "confidence": 1.0,
                "categories_used": matched,
                "warnings": [],
            }

    text_norm = _loose_normalize(text)
    if text_norm:
        scores = {}
        for domain_id, domain in domains.items():
            score = sum(
                1
                for keyword in domain.get("keywords", [])
                if _loose_normalize(keyword) in text_norm
            )
            if score:
                scores[domain_id] = score
        if scores:
            domain_id = max(scores, key=scores.get)
            return {
                "domain": domain_id,
                "name": domains[domain_id].get("name"),
                "match_method": "keyword_text",
                "confidence": 0.8,
                "categories_used": [],
                "warnings": [],
            }

    return {
        "domain": None,
        "name": None,
        "match_method": "unresolved",
        "confidence": 0.0,
        "categories_used": [],
        "warnings": [],
    }


def resolve_topic(query: str, include_children: bool = False) -> dict[str, Any]:
    """Resolve a topic query into a canonical DeepTrender topic."""

    topics = load_topics()
    query_strict = _strict_normalize(query)
    query_loose = _loose_normalize(query)

    for topic_id, topic in topics.items():
        canonical = _strict_normalize(topic.get("canonical_name"))
        if query_strict == canonical or query_loose == _loose_normalize(topic_id):
            return _resolution(
                input_value=query,
                topic_id=topic_id,
                match_method="canonical_exact",
                confidence=1.0,
                include_children=include_children,
            )

    alias_match = _alias_index().get(query_loose)
    if alias_match:
        topic_id, alias = alias_match
        return _resolution(
            input_value=query,
            topic_id=topic_id,
            match_method="alias_exact",
            confidence=0.95,
            include_children=include_children,
            aliases_used=[alias],
        )

    return _resolution(
        input_value=query,
        topic_id=None,
        match_method="unresolved",
        confidence=0.0,
        include_children=include_children,
    )


def _phrase_in_text(phrase: str, text: str | None) -> bool:
    phrase_norm = _loose_normalize(phrase)
    text_norm = _loose_normalize(text)
    if not phrase_norm or not text_norm:
        return False
    return f" {phrase_norm} " in f" {text_norm} "


def _topic_aliases(topic_id: str, topic: dict[str, Any]) -> list[str]:
    aliases = list(topic.get("aliases", []))
    aliases.extend(load_aliases_for_topic(topic_id))
    return sorted(set(aliases), key=str.lower)


def load_aliases_for_topic(topic_id: str) -> list[str]:
    return [alias for alias, target_id in load_aliases().items() if target_id == topic_id]


def _topic_categories(topic: dict[str, Any]) -> set[str]:
    categories: set[str] = set()
    for mapping in (topic.get("external_mappings") or {}).get("arxiv", []):
        if "id" in mapping:
            categories.add(_strict_normalize(mapping["id"]))
    return categories


def match_paper_topics(
    title: str,
    abstract: str | None,
    extracted_keywords: list[str] | None = None,
    arxiv_categories: list[str] | None = None,
) -> list[dict[str, Any]]:
    """Return candidate topic matches for a paper."""

    topics = load_topics()
    extracted_keywords = extracted_keywords or []
    keyword_norms = {_loose_normalize(keyword) for keyword in extracted_keywords}
    category_norms = {_strict_normalize(category) for category in (arxiv_categories or [])}
    matches: list[dict[str, Any]] = []

    for topic_id, topic in topics.items():
        canonical = topic.get("canonical_name", "")
        aliases = _topic_aliases(topic_id, topic)
        phrases = [canonical, *aliases]
        best_method: str | None = None
        best_confidence = 0.0
        aliases_used: list[str] = []

        for phrase in phrases:
            is_alias = _loose_normalize(phrase) != _loose_normalize(canonical)
            if _phrase_in_text(phrase, title) and best_confidence < 0.85:
                best_method = "title_exact_phrase"
                best_confidence = 0.85
                aliases_used = [phrase] if is_alias else []
            if _phrase_in_text(phrase, abstract) and best_confidence < 0.75:
                best_method = "abstract_phrase"
                best_confidence = 0.75
                aliases_used = [phrase] if is_alias else []

        for phrase in phrases:
            phrase_norm = _loose_normalize(phrase)
            if phrase_norm in keyword_norms and best_confidence < 0.65:
                best_method = "extracted_keyword_match"
                best_confidence = 0.65
                aliases_used = [phrase] if phrase_norm != _loose_normalize(canonical) else []

        if category_norms & _topic_categories(topic) and best_confidence < 0.50:
            best_method = "external_broader_mapping"
            best_confidence = 0.50
            aliases_used = []

        if best_method:
            warnings = []
            if best_confidence < 0.7:
                warnings.append(_warning_low_confidence(best_confidence))
            matches.append(
                {
                    "topic_id": topic_id,
                    "canonical_topic": canonical,
                    "domain": topic.get("domain"),
                    "secondary_domains": topic.get("secondary_domains", []),
                    "match_method": best_method,
                    "confidence": best_confidence,
                    "aliases_used": aliases_used,
                    "warnings": warnings,
                }
            )

    return sorted(matches, key=lambda item: item["confidence"], reverse=True)
