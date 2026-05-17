# DeepTrender Taxonomy v0.1

This directory contains the serving taxonomy used by DeepTrender v0.1.

- `domains.yaml`: coarse domains backed by arXiv categories and keywords.
- `topics.yaml`: curated canonical fine-grained topics.
- `topic_aliases.yaml`: strict synonyms and common abbreviations only.
- `topic_review_queue.yaml`: AI-generated or unresolved candidates awaiting
  human review.

Policy:

- arXiv categories are domain evidence, not fine-grained serving topics.
- Canonical topics are the fine-grained serving truth.
- Related terms are represented in `related_topics`, not aliases.
- Child topics are excluded unless a query sets `include_children=true`.
