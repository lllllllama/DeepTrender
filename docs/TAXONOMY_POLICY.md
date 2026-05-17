# DeepTrender Taxonomy Policy v0.1

DeepTrender uses two taxonomy levels:

- arXiv categories are coarse domain evidence.
- DeepTrender canonical topics are the serving truth for fine-grained topics.

## Domains

The v0.1 domain set is intentionally small:

- `CV`
- `NLP`
- `ML`
- `AI`
- `Robotics`

The `ML` domain includes both `cs.LG` and `stat.ML`. Multimodal is not a
top-level v0.1 domain; multimodal concepts are represented as topics or
secondary domains.

## Topics

Canonical topics live in `config/taxonomy/topics.yaml`. Each topic must define:

- `canonical_name`
- `domain`
- `secondary_domains`
- `parent_topics`
- `related_topics`
- `aliases`
- `definition`
- `match_policy`
- `external_mappings`
- `owner_status`

Child topics are not included by default. A query may include child topics only
when `normalized_query.include_children` is `true`.

## Aliases

Aliases are strict synonyms or common abbreviations only. Related but distinct
concepts must be represented in `related_topics`, not in aliases.

Examples:

- `llm` can alias `large_language_model`.
- `rag` can alias `retrieval_augmented_generation`.
- `semantic_segmentation` is related to `panoptic_segmentation`, but it is not
  an alias of it.

## Review Queue

AI-generated topic candidates must go into
`config/taxonomy/topic_review_queue.yaml`, not directly into curated topics.
External taxonomies are evidence, not the final source of truth.
