"""Lightweight dataclasses for taxonomy data."""

from dataclasses import dataclass, field
from typing import Any


@dataclass(frozen=True)
class Domain:
    """A coarse DeepTrender domain backed by arXiv categories."""

    domain_id: str
    name: str
    arxiv_categories: list[str] = field(default_factory=list)
    keywords: list[str] = field(default_factory=list)


@dataclass(frozen=True)
class Topic:
    """A curated fine-grained serving topic."""

    topic_id: str
    canonical_name: str
    domain: str
    secondary_domains: list[str] = field(default_factory=list)
    parent_topics: list[str] = field(default_factory=list)
    related_topics: list[str] = field(default_factory=list)
    aliases: list[str] = field(default_factory=list)
    definition: str = ""
    match_policy: dict[str, Any] = field(default_factory=dict)
    external_mappings: dict[str, Any] = field(default_factory=dict)
    owner_status: str = "curated"
