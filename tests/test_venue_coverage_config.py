"""Coverage checks for venue bootstrap configuration."""

import csv
from pathlib import Path

from agents.structuring_agent import VENUE_PATTERNS
from scraper.semantic_scholar import S2_VENUES


CORE_EXPANSION_VENUES = {
    "KDD",
    "SIGIR",
    "WWW",
    "SIGMOD",
    "VLDB",
    "ICDE",
    "UAI",
    "WACV",
    "ACM MM",
    "ICSE",
    "CHI",
    "ICRA",
}


def test_expanded_s2_venue_set_has_historical_years():
    assert CORE_EXPANSION_VENUES.issubset(S2_VENUES)

    for venue in CORE_EXPANSION_VENUES:
        assert min(S2_VENUES[venue].years) <= 2021
        assert max(S2_VENUES[venue].years) >= 2024


def test_expanded_venues_can_be_structured():
    assert CORE_EXPANSION_VENUES.issubset(VENUE_PATTERNS)


def test_registry_contains_expanded_coverage():
    registry_path = Path(__file__).parents[1] / "data" / "registry" / "ccf_venues.csv"
    with registry_path.open("r", encoding="utf-8", newline="") as handle:
        rows = {row["canonical_name"] for row in csv.DictReader(handle)}

    assert CORE_EXPANSION_VENUES.issubset(rows)
    assert len(rows) >= 35
