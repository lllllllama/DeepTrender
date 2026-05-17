"""v0.1 MCP response contract tests."""

import mcp_server as ms
from services import frontend_views
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
    assert isinstance(response["warnings"], list)
    assert isinstance(response["evidence"], list)


def test_new_service_responses_follow_contract(repo_with_data):
    responses = [
        mcp_views.list_domains(),
        mcp_views.list_topics(domain="ML"),
        mcp_views.resolve_topic("RAG"),
        mcp_views.get_venue_year_topic("ICLR", 2023, "transformer", repo=repo_with_data),
        mcp_views.get_data_quality_report(repo=repo_with_data),
    ]

    for response in responses:
        _assert_contract(response)


def test_topic_response_has_normalized_query():
    response = mcp_views.resolve_topic("LLM")
    _assert_contract(response)
    normalized_query = response["data"]["normalized_query"]
    assert normalized_query["input_topic"] == "LLM"
    assert normalized_query["topic_id"] == "large_language_model"
    assert normalized_query["include_children"] is False


def test_venue_year_topic_response_fields(repo_with_data):
    response = mcp_views.get_venue_year_topic("ICLR", 2023, "transformer", repo=repo_with_data)
    _assert_contract(response)
    data = response["data"]
    assert data["normalized_query"]["venue"] == "ICLR"
    assert data["matched_papers"] == 1
    assert data["total_venue_papers"] == 1
    assert data["relative_frequency"] == 1.0
    assert "conference_source_policy" in data
    assert "quality_scope" in data


def test_mcp_server_exposes_new_read_only_tools(repo_with_data, monkeypatch):
    monkeypatch.setattr(ms, "_repo", repo_with_data)

    _assert_contract(ms.list_domains())
    _assert_contract(ms.list_topics(domain="CV"))
    _assert_contract(ms.resolve_topic("VLM"))
    _assert_contract(ms.get_venue_year_topic("ICLR", 2023, "transformer"))
    _assert_contract(ms.get_data_quality_report())


def test_frontend_view_uses_relative_frequency(repo_with_data):
    view = frontend_views.build_venue_year_topic_view(
        "ICLR",
        2023,
        "transformer",
        repo=repo_with_data,
    )
    assert view["primary_metric"] == "relative_frequency"
    assert view["secondary_metric"] == "count"
    assert view["data"]["relative_frequency"] == 1.0
