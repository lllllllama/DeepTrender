"""Ingestion failure logging tests."""

import logging

from agents.ingestion_agent import IngestionAgent
from scraper.models import RawPaper


class FailingRepository:
    def save_raw_paper(self, paper):
        raise RuntimeError("database unavailable")


class FakeArxivClient:
    def search_by_category(self, category, max_results):
        return [
            RawPaper(
                source="arxiv",
                source_paper_id="2401.00001",
                title="Logged failure test",
            )
        ]


def test_arxiv_save_failure_is_logged(caplog):
    agent = IngestionAgent(
        repository=FailingRepository(),
        arxiv_client=FakeArxivClient(),
    )

    with caplog.at_level(logging.ERROR):
        saved_count = agent.ingest_arxiv_category("cs.LG", max_results=1)

    assert saved_count == 0
    assert "Failed to save arXiv paper 2401.00001 for category cs.LG" in caplog.text
