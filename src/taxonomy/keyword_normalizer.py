"""Canonicalize extracted keyword statistics for serving and static export."""

from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass, field
from functools import lru_cache
from pathlib import Path
import re
from typing import Iterable, Sequence

import yaml

from config import ROOT_DIR
from .loader import load_aliases, load_topics


STAT_ALIASES_PATH = ROOT_DIR / "config" / "taxonomy" / "keyword_stat_aliases.yaml"

GENERIC_SINGLE_WORD_NOISE = {
    "image",
    "language",
    "neural",
    "visual",
}


@dataclass(frozen=True)
class KeywordNormalization:
    """Normalized keyword metadata."""

    original: str
    canonical_keyword: str
    canonical_key: str
    reason: str
    topic_id: str | None = None


@dataclass
class AggregatedKeyword:
    """Aggregated keyword count with source variants for auditability."""

    keyword: str
    count: int
    canonical_key: str
    topic_id: str | None = None
    variants: dict[str, int] = field(default_factory=dict)

    def as_pair(self) -> tuple[str, int]:
        return self.keyword, self.count

    def as_dict(self, include_variants: bool = False) -> dict:
        payload = {
            "keyword": self.keyword,
            "count": self.count,
        }
        if self.topic_id:
            payload["topic_id"] = self.topic_id
        if include_variants:
            payload["canonical_key"] = self.canonical_key
            payload["variants"] = [
                {"keyword": keyword, "count": count}
                for keyword, count in sorted(
                    self.variants.items(),
                    key=lambda item: (-item[1], item[0]),
                )
            ]
        return payload


def loose_normalize(value: str | None) -> str:
    """Return a punctuation-tolerant normalized phrase key."""

    value = (value or "").strip().lower()
    value = value.replace("_", " ").replace("-", " ")
    value = re.sub(r"[^a-z0-9.+]+", " ", value)
    return re.sub(r"\s+", " ", value).strip()


def canonical_key(value: str) -> str:
    return loose_normalize(value).replace(" ", "_")


def is_noise_keyword(value: str | None) -> bool:
    """Filter extractor artifacts that are not useful research topics."""

    normalized = loose_normalize(value)
    if not normalized:
        return True
    if re.fullmatch(r"\d+(?:\.\d+)?", normalized):
        return True
    if len(normalized) < 3:
        return True
    if normalized in GENERIC_SINGLE_WORD_NOISE:
        return True
    return False


def _read_stat_aliases() -> dict:
    if not STAT_ALIASES_PATH.exists():
        return {}
    with STAT_ALIASES_PATH.open("r", encoding="utf-8") as handle:
        return yaml.safe_load(handle) or {}


class KeywordCanonicalizer:
    """Map raw extracted keywords to display-safe aggregate labels."""

    def __init__(self) -> None:
        self.topics = load_topics()
        self.topic_names = {
            topic_id: topic.get("canonical_name", topic_id.replace("_", " "))
            for topic_id, topic in self.topics.items()
        }
        self.alias_index: dict[str, tuple[str, str]] = {}
        self.stat_alias_index: dict[str, tuple[str, str]] = {}
        self.variants_by_topic: dict[str, set[str]] = defaultdict(set)
        self._build_indexes()

    def _add_topic_variant(self, topic_id: str, phrase: str) -> None:
        normalized = loose_normalize(phrase)
        if normalized:
            self.variants_by_topic[topic_id].add(normalized)

    def _build_indexes(self) -> None:
        for topic_id, topic in self.topics.items():
            canonical_name = topic.get("canonical_name", topic_id.replace("_", " "))
            self.alias_index[loose_normalize(canonical_name)] = (topic_id, "canonical_topic")
            self.alias_index[loose_normalize(topic_id)] = (topic_id, "canonical_topic")
            self._add_topic_variant(topic_id, canonical_name)
            self._add_topic_variant(topic_id, topic_id)
            for alias in topic.get("aliases", []):
                self.alias_index[loose_normalize(alias)] = (topic_id, "taxonomy_alias")
                self._add_topic_variant(topic_id, alias)

        for alias, topic_id in load_aliases().items():
            if topic_id in self.topics:
                self.alias_index[loose_normalize(alias)] = (topic_id, "taxonomy_alias")
                self._add_topic_variant(topic_id, alias)

        for _, group in (_read_stat_aliases().get("canonical_variants") or {}).items():
            topic_id = group.get("target_topic") or group.get("target")
            if topic_id not in self.topics:
                continue
            reason = group.get("reason", "stat_alias")
            for alias in group.get("aliases", []):
                normalized = loose_normalize(alias)
                if not normalized:
                    continue
                self.stat_alias_index[normalized] = (topic_id, reason)
                self._add_topic_variant(topic_id, alias)

    def normalize(self, keyword: str | None) -> KeywordNormalization | None:
        original = (keyword or "").strip()
        if is_noise_keyword(original):
            return None

        normalized = loose_normalize(original)
        topic_match = self.alias_index.get(normalized)
        if topic_match:
            topic_id, reason = topic_match
            display = self.topic_names[topic_id]
            return KeywordNormalization(
                original=original,
                canonical_keyword=display,
                canonical_key=canonical_key(display),
                reason=reason,
                topic_id=topic_id,
            )

        stat_match = self.stat_alias_index.get(normalized)
        if stat_match:
            topic_id, reason = stat_match
            display = self.topic_names[topic_id]
            return KeywordNormalization(
                original=original,
                canonical_keyword=display,
                canonical_key=canonical_key(display),
                reason=reason,
                topic_id=topic_id,
            )

        return KeywordNormalization(
            original=original,
            canonical_keyword=normalized,
            canonical_key=canonical_key(normalized),
            reason="literal",
        )

    def equivalent_surface_forms(self, keyword: str) -> list[str]:
        """Return raw keyword forms that should be counted with this keyword."""

        normalized = self.normalize(keyword)
        if not normalized:
            return []
        variants = {normalized.canonical_keyword, normalized.canonical_key.replace("_", " ")}
        if normalized.topic_id:
            variants.update(self.variants_by_topic.get(normalized.topic_id, set()))
        else:
            variants.add(loose_normalize(keyword))
        return sorted({variant for variant in variants if variant})

    def aggregate_count_pairs(
        self,
        rows: Iterable[tuple[str, int]],
        limit: int | None = None,
    ) -> list[AggregatedKeyword]:
        aggregates: dict[str, AggregatedKeyword] = {}

        for keyword, raw_count in rows:
            normalized = self.normalize(keyword)
            if not normalized:
                continue

            count = int(raw_count or 0)
            current = aggregates.get(normalized.canonical_key)
            if current is None:
                current = AggregatedKeyword(
                    keyword=normalized.canonical_keyword,
                    count=0,
                    canonical_key=normalized.canonical_key,
                    topic_id=normalized.topic_id,
                    variants={},
                )
                aggregates[normalized.canonical_key] = current

            current.count += count
            current.variants[normalized.original] = current.variants.get(normalized.original, 0) + count

        sorted_items = sorted(
            aggregates.values(),
            key=lambda item: (-item.count, item.keyword),
        )
        return sorted_items[:limit] if limit is not None else sorted_items

    def aggregate_paper_keyword_rows(
        self,
        rows: Iterable[tuple[str, int]],
        limit: int | None = None,
    ) -> list[AggregatedKeyword]:
        """Aggregate keyword rows by unique paper per canonical keyword."""

        paper_ids_by_key: dict[str, set[int]] = defaultdict(set)
        variants_by_key: dict[str, dict[str, set[int]]] = defaultdict(lambda: defaultdict(set))
        metadata: dict[str, KeywordNormalization] = {}

        for keyword, paper_id in rows:
            normalized = self.normalize(keyword)
            if not normalized or paper_id is None:
                continue
            paper_id_int = int(paper_id)
            metadata.setdefault(normalized.canonical_key, normalized)
            paper_ids_by_key[normalized.canonical_key].add(paper_id_int)
            variants_by_key[normalized.canonical_key][normalized.original].add(paper_id_int)

        items = []
        for key, paper_ids in paper_ids_by_key.items():
            normalized = metadata[key]
            items.append(
                AggregatedKeyword(
                    keyword=normalized.canonical_keyword,
                    count=len(paper_ids),
                    canonical_key=key,
                    topic_id=normalized.topic_id,
                    variants={
                        variant: len(variant_paper_ids)
                        for variant, variant_paper_ids in variants_by_key[key].items()
                    },
                )
            )

        sorted_items = sorted(items, key=lambda item: (-item.count, item.keyword))
        return sorted_items[:limit] if limit is not None else sorted_items

    def aggregate_keyword_items(
        self,
        items: Sequence[dict],
        *,
        keyword_field: str = "keyword",
        count_field: str = "count",
        limit: int | None = None,
    ) -> list[dict]:
        rows = [
            (str(item.get(keyword_field, "")), int(item.get(count_field, 0) or 0))
            for item in items
        ]
        return [
            item.as_dict()
            for item in self.aggregate_count_pairs(rows, limit=limit)
        ]


@lru_cache(maxsize=1)
def get_keyword_canonicalizer() -> KeywordCanonicalizer:
    return KeywordCanonicalizer()
