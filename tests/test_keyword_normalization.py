"""Keyword statistic normalization tests."""

from scraper.models import create_legacy_paper


def _paper(title, venue, year, keywords):
    return create_legacy_paper(
        id=title.lower().replace(" ", "_"),
        title=title,
        abstract="A short abstract for keyword normalization tests.",
        authors=["A. Tester"],
        venue=venue,
        year=year,
        url="https://example.com",
        keywords=keywords,
    )


def test_top_keywords_merge_llm_surface_forms_once_per_paper(repo):
    repo.save_papers(
        [
            _paper(
                "LLM surface forms",
                "ICLR",
                2024,
                ["large language model", "large language", "language models", "102"],
            ),
            _paper("Language models again", "ICLR", 2024, ["language models"]),
            _paper("Diffusion aliases", "ICLR", 2024, ["diffusion", "diffusion model"]),
        ]
    )

    top_keywords = repo.get_top_keywords(venue="ICLR", year=2024, limit=10)
    counts = dict(top_keywords)

    assert counts["large language model"] == 2
    assert counts["diffusion model"] == 1
    assert "large language" not in counts
    assert "language models" not in counts
    assert "102" not in counts


def test_keyword_trend_counts_canonical_surface_forms(repo):
    repo.save_papers(
        [
            _paper("LLM in 2023", "ICLR", 2023, ["language models"]),
            _paper("LLM in 2024", "ICLR", 2024, ["large language"]),
        ]
    )

    assert repo.get_keyword_trend("large language model", venue="ICLR") == {
        2023: 1,
        2024: 1,
    }
