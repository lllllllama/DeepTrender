"""Load and validate DeepTrender v0.1 taxonomy YAML files."""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path
from typing import Any

import yaml

from config import ROOT_DIR

TAXONOMY_VERSION = "taxonomy_v0.1"
DATA_POLICY_VERSION = "data_policy_v0.1"
TAXONOMY_DIR = ROOT_DIR / "config" / "taxonomy"


class TaxonomyError(ValueError):
    """Raised when taxonomy files are missing or inconsistent."""


def _read_yaml(filename: str) -> dict[str, Any]:
    path = TAXONOMY_DIR / filename
    if not path.exists():
        raise TaxonomyError(f"Missing taxonomy file: {path}")
    with path.open("r", encoding="utf-8") as handle:
        return yaml.safe_load(handle) or {}


@lru_cache(maxsize=1)
def load_domains_document() -> dict[str, Any]:
    """Return the full domains YAML document."""

    return _read_yaml("domains.yaml")


@lru_cache(maxsize=1)
def load_topics_document() -> dict[str, Any]:
    """Return the full topics YAML document."""

    return _read_yaml("topics.yaml")


@lru_cache(maxsize=1)
def load_aliases_document() -> dict[str, Any]:
    """Return the full topic aliases YAML document."""

    return _read_yaml("topic_aliases.yaml")


@lru_cache(maxsize=1)
def load_review_queue_document() -> dict[str, Any]:
    """Return the full topic review queue YAML document."""

    return _read_yaml("topic_review_queue.yaml")


def load_domains() -> dict[str, dict[str, Any]]:
    """Return domain records keyed by domain id."""

    return load_domains_document().get("domains", {})


def load_topics() -> dict[str, dict[str, Any]]:
    """Return topic records keyed by topic id."""

    return load_topics_document().get("topics", {})


def load_aliases() -> dict[str, str]:
    """Return strict topic aliases keyed by alias text."""

    return load_aliases_document().get("aliases", {})


def load_review_queue() -> list[dict[str, Any]]:
    """Return pending candidate topic records."""

    return load_review_queue_document().get("candidates", [])


def validate_taxonomy() -> list[str]:
    """Return validation errors for the configured v0.1 taxonomy."""

    errors: list[str] = []
    domains = load_domains()
    topics = load_topics()
    aliases = load_aliases()
    required_topic_fields = {
        "canonical_name",
        "domain",
        "secondary_domains",
        "parent_topics",
        "related_topics",
        "aliases",
        "definition",
        "match_policy",
        "external_mappings",
        "owner_status",
    }

    for domain_id, domain in domains.items():
        if not domain.get("name"):
            errors.append(f"Domain {domain_id} is missing name")
        if not isinstance(domain.get("arxiv_categories", []), list):
            errors.append(f"Domain {domain_id} arxiv_categories must be a list")

    for topic_id, topic in topics.items():
        missing = required_topic_fields - set(topic)
        if missing:
            errors.append(f"Topic {topic_id} is missing fields: {sorted(missing)}")
        if topic.get("domain") not in domains:
            errors.append(f"Topic {topic_id} has unknown domain {topic.get('domain')}")
        for domain_id in topic.get("secondary_domains", []):
            if domain_id not in domains:
                errors.append(f"Topic {topic_id} has unknown secondary domain {domain_id}")
        for parent_id in topic.get("parent_topics", []):
            if parent_id not in topics:
                errors.append(f"Topic {topic_id} has unknown parent topic {parent_id}")
        for related_id in topic.get("related_topics", []):
            if related_id not in topics:
                errors.append(f"Topic {topic_id} has unknown related topic {related_id}")
        match_policy = topic.get("match_policy") or {}
        if match_policy.get("include_children") is not False:
            errors.append(f"Topic {topic_id} must set match_policy.include_children to false")

    for alias, topic_id in aliases.items():
        if topic_id not in topics:
            errors.append(f"Alias {alias!r} points to unknown topic {topic_id!r}")

    return errors
