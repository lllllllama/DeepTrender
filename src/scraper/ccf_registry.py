"""CCF venue registry loader.

The CSV registry is the source of truth for broad CCF conference coverage.
It is intentionally read at runtime so ingestion, export, and tests do not
need hand-written copies of the same venue list.
"""

from __future__ import annotations

import csv
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path
from typing import Iterable


ROOT_DIR = Path(__file__).resolve().parents[2]
DEFAULT_REGISTRY_PATH = ROOT_DIR / "data" / "registry" / "ccf_venues.csv"


@dataclass(frozen=True)
class CCFVenue:
    canonical_name: str
    full_name: str
    domain: str
    tier: str
    source_preference: str
    openreview_id_pattern: str
    s2_venue_key: str
    openalex_venue_name: str
    aliases: tuple[str, ...]


def _split_aliases(value: str) -> tuple[str, ...]:
    return tuple(alias.strip() for alias in value.split(",") if alias.strip())


@lru_cache(maxsize=4)
def load_ccf_venue_registry(
    registry_path: str | Path = DEFAULT_REGISTRY_PATH,
) -> dict[str, CCFVenue]:
    """Load CCF venue metadata keyed by canonical venue name."""

    path = Path(registry_path)
    if not path.exists():
        return {}

    venues: dict[str, CCFVenue] = {}
    with path.open("r", encoding="utf-8", newline="") as handle:
        for row in csv.DictReader(handle):
            name = (row.get("canonical_name") or "").strip()
            if not name:
                continue
            venues[name] = CCFVenue(
                canonical_name=name,
                full_name=(row.get("full_name") or name).strip(),
                domain=(row.get("domain") or "General").strip(),
                tier=(row.get("tier") or "C").strip().upper(),
                source_preference=(row.get("source_preference") or "s2").strip(),
                openreview_id_pattern=(row.get("openreview_id_pattern") or "").strip(),
                s2_venue_key=(row.get("s2_venue_key") or name).strip(),
                openalex_venue_name=(row.get("openalex_venue_name") or name).strip(),
                aliases=_split_aliases(row.get("aliases") or ""),
            )
    return venues


def filter_ccf_venues(
    *,
    tier: str | None = None,
    domain: str | None = None,
    names: Iterable[str] | None = None,
) -> list[CCFVenue]:
    """Return registry venues matching optional tier/domain/name filters."""

    requested_names = {name.strip() for name in names or [] if name and name.strip()}
    requested_tier = (tier or "").strip().upper()
    requested_domain = (domain or "").strip().lower()

    results = []
    for venue in load_ccf_venue_registry().values():
        if requested_names and venue.canonical_name not in requested_names:
            continue
        if requested_tier and requested_tier != "ALL" and venue.tier != requested_tier:
            continue
        if (
            requested_domain
            and requested_domain != "all"
            and venue.domain.lower() != requested_domain
        ):
            continue
        results.append(venue)
    return sorted(
        results,
        key=lambda venue: (venue.tier, venue.domain, venue.canonical_name),
    )


def filter_ccf_venue_names(
    *,
    tier: str | None = None,
    domain: str | None = None,
    names: Iterable[str] | None = None,
) -> list[str]:
    """Return canonical names for matching CCF venues."""

    return [
        venue.canonical_name
        for venue in filter_ccf_venues(tier=tier, domain=domain, names=names)
    ]
