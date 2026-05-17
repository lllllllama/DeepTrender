# DeepTrender Data Policy v0.1

DeepTrender is a structured trend database for AI/ML papers. Its primary job is
to serve traceable facts: normalized topics, source evidence, venue/year/topic
counts, relative frequencies, warnings, provenance, and structured evidence.
Subjective trend interpretation belongs to downstream human interfaces or AI
agents.

## Evidence Layers

1. Source Evidence Layer
- Raw records from arXiv, OpenReview, OpenAlex, and Semantic Scholar.
- Raw payloads should remain unmodified and traceable.

2. Canonical Merge Layer
- Deduplicated papers, normalized venues, source links, and compatibility
  mappings.

3. Taxonomy and Fact Layer
- Canonical domains, topics, aliases, paper-topic matches, and statistics.

4. Serving Layer
- MCP-ready and frontend-ready response objects.

## Source Policy

- arXiv is preprint evidence by default.
- arXiv may be used for overall preprint trend tables.
- arXiv papers must not be treated as CVPR, ICLR, NeurIPS, ICML, or other
  accepted conference papers by default.
- OpenReview and official proceedings may provide accepted conference evidence.
- OpenAlex and Semantic Scholar are auxiliary evidence unless confidence is
  high.
- Unknown quality papers must be shown separately or included with warnings.
- Conference trend outputs must distinguish accepted, preprint, unknown, and
  mixed evidence.

## Paper Status Model

DeepTrender v0.1 recognizes these status values:

- `accepted`
- `submitted`
- `preprint`
- `published`
- `unknown`
- `filtered`

The current database schema stores `accepted`, `unknown`, and `filtered` in
`papers.quality_flag`, with `papers.venue_type` providing compatibility hints
such as `conference`, `journal`, `preprint`, and `unknown`. v0.1 does not force
a destructive migration. Serving code maps the current fields into the expanded
status vocabulary where possible.

## Warning Policy

The serving layer must surface these warning conditions:

- `unknown_quality_ratio > 0.3`
- `empty_abstract_ratio > 0.2`
- `single_source_ratio > 0.8`
- `matched_papers < 5`
- `topic_match_confidence < 0.7`
- `only_arxiv_evidence_for_conference_query`

Warnings are structured objects with stable codes, values, thresholds, severity,
and human-readable messages.
