"""Coverage checks for venue bootstrap configuration."""

import csv
from pathlib import Path

from agents.structuring_agent import VENUE_PATTERNS
from scraper.ccf_registry import filter_ccf_venue_names, load_ccf_venue_registry
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

CCF_REGISTRY_CORE_VENUES = CORE_EXPANSION_VENUES - {"WACV"}

FULL_CCF_SAMPLE_VENUES = {
    "PPoPP",
    "SIGCOMM",
    "CCS",
    "ICSE",
    "SIGMOD",
    "STOC",
    "ACM MM",
    "AAAI",
    "CHI",
    "WWW",
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

    assert CCF_REGISTRY_CORE_VENUES.issubset(rows)
    assert FULL_CCF_SAMPLE_VENUES.issubset(rows)
    assert len(rows) >= 380


def test_registry_loader_drives_full_ccf_coverage():
    registry = load_ccf_venue_registry()

    assert len(registry) >= 380
    assert FULL_CCF_SAMPLE_VENUES.issubset(registry)
    assert not {
        name for name in registry if any(char in name for char in '/\\:*?"<>|')
    }
    assert set(filter_ccf_venue_names(tier="A", domain="AI")) >= {
        "AAAI",
        "ACL",
        "CVPR",
        "ICCV",
        "ICML",
        "ICLR",
        "NeurIPS",
    }


def test_full_ccf_registry_venues_are_available_to_s2_and_structuring():
    registry = load_ccf_venue_registry()

    assert FULL_CCF_SAMPLE_VENUES.issubset(S2_VENUES)
    assert FULL_CCF_SAMPLE_VENUES.issubset(VENUE_PATTERNS)
    assert set(registry).issubset(S2_VENUES)
