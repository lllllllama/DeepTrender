"""Taxonomy resolver tests."""

from taxonomy.resolver import resolve_domain, resolve_topic


def test_required_alias_resolution_cases():
    cases = {
        "RAG": "retrieval_augmented_generation",
        "retrieval-augmented generation": "retrieval_augmented_generation",
        "LLM": "large_language_model",
        "VLM": "vision_language_model",
        "panoptic parsing": "panoptic_segmentation",
        "panoptic segmentation": "panoptic_segmentation",
    }
    for query, topic_id in cases.items():
        assert resolve_topic(query)["topic_id"] == topic_id


def test_rag_is_alias_exact():
    result = resolve_topic("RAG")
    assert result["match_method"] == "alias_exact"
    assert result["confidence"] == 0.95
    assert result["aliases_used"] == ["rag"]


def test_segmentation_children_are_opt_in():
    default = resolve_topic("segmentation")
    with_children = resolve_topic("segmentation", include_children=True)

    assert default["topic_id"] == "segmentation"
    assert default["include_children"] is False
    assert "panoptic_segmentation" not in default["child_topic_ids"]

    assert with_children["include_children"] is True
    assert "panoptic_segmentation" in with_children["child_topic_ids"]


def test_resolve_domain_uses_stat_ml_for_ml():
    result = resolve_domain(["stat.ML"])
    assert result["domain"] == "ML"
    assert result["confidence"] == 1.0
