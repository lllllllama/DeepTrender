"""Taxonomy loader tests."""

from taxonomy.loader import load_aliases, load_domains, load_topics, validate_taxonomy


def test_domains_yaml_loads_and_includes_stat_ml():
    domains = load_domains()
    assert "ML" in domains
    assert "stat.ML" in domains["ML"]["arxiv_categories"]


def test_topics_yaml_loads_required_topics():
    topics = load_topics()
    for topic_id in (
        "segmentation",
        "panoptic_segmentation",
        "large_language_model",
        "retrieval_augmented_generation",
        "vision_language_model",
        "diffusion_model",
        "reinforcement_learning",
    ):
        assert topic_id in topics


def test_all_topics_have_required_fields():
    required = {
        "canonical_name",
        "domain",
        "secondary_domains",
        "parent_topics",
        "related_topics",
        "aliases",
        "definition",
        "match_policy",
        "external_mappings",
        "owner_status",
    }
    for topic in load_topics().values():
        assert required.issubset(topic)


def test_aliases_and_related_topics_are_valid():
    topics = load_topics()
    for alias, topic_id in load_aliases().items():
        assert topic_id in topics, alias

    for topic_id, topic in topics.items():
        for related_id in topic.get("related_topics", []):
            assert related_id in topics, (topic_id, related_id)


def test_taxonomy_validation_passes():
    assert validate_taxonomy() == []
