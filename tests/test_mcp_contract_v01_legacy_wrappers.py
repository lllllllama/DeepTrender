"""Contract tests for v0.1 wrappers around legacy MCP tools."""

import mcp_server as ms
from services import mcp_views


def _assert_contract(response):
    assert set(response) == {"data", "meta", "warnings", "evidence"}
    for key in (
        "taxonomy_version",
        "data_policy_version",
        "generated_at",
        "source_layer",
        "limit",
        "offset",
        "has_more",
    ):
        assert key in response["meta"]


def test_get_overview_v01_follows_contract(repo_with_data, monkeypatch):
    monkeypatch.setattr(ms, "_repo", repo_with_data)

    _assert_contract(mcp_views.get_overview_v01(repo=repo_with_data))
    _assert_contract(ms.get_overview_v01())


def test_get_status_v01_follows_contract(repo_with_data, monkeypatch):
    monkeypatch.setattr(ms, "_repo", repo_with_data)

    _assert_contract(mcp_views.get_status_v01(repo=repo_with_data))
    _assert_contract(ms.get_status_v01())


def test_list_venues_v01_follows_contract(repo_with_data, monkeypatch):
    monkeypatch.setattr(ms, "_repo", repo_with_data)

    _assert_contract(mcp_views.list_venues_v01(repo=repo_with_data))
    _assert_contract(ms.list_venues_v01())


def test_old_legacy_tools_still_work(repo_with_data, monkeypatch):
    monkeypatch.setattr(ms, "_repo", repo_with_data)

    overview = ms.get_overview()
    status = ms.get_status()
    venues = ms.list_venues()

    assert "total_papers" in overview
    assert "database" in status
    assert isinstance(venues, list)
