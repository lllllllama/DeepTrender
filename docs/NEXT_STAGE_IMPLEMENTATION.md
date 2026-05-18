# DeepTrender Next Stage Implementation

This stage upgrades DeepTrender from runtime topic matching to a structured
topic fact layer while preserving the v0.1 positioning and policies.

## Paper Topics Fact Layer

`paper_topics` stores derived, rebuildable topic facts for structured papers.
Each row links a paper to one canonical DeepTrender topic and records:

- `topic_id`
- `canonical_topic`
- `domain`
- `match_method`
- `confidence`
- `evidence_keyword`
- `evidence_source`
- `taxonomy_version`

The table is added with `CREATE TABLE IF NOT EXISTS` and does not modify or
delete existing tables.

## Why Persisted Topic Facts Are Needed

Runtime matching is useful for early MVP behavior, but it has drawbacks:

- It recomputes matches on every query.
- It makes historical query results harder to reproduce.
- It cannot easily support coverage, provenance, and scoped quality reports.

Persisted topic facts make topic statistics reproducible for a specific
taxonomy version while remaining rebuildable from structured papers, paper
keywords, and the taxonomy resolver.

## Rebuild Behavior

`src/services/topic_facts.py` provides:

- `build_paper_topic_matches`
- `rebuild_paper_topics`
- `get_topic_fact_summary`

Rebuilding clears only rows for the selected taxonomy version and then derives
fresh facts from structured papers and keywords. Related topics are not merged.
Child topics are not added unless `include_children=true` is explicit.

## Runtime Matching Fallback

`get_venue_year_topic` now prefers `paper_topics` for the current taxonomy
version. If no persisted topic facts are available, it uses the previous runtime
matching path and emits:

```json
{
  "code": "runtime_topic_matching_fallback",
  "message": "paper_topics facts are unavailable; using runtime topic matching fallback.",
  "severity": "medium"
}
```

## Scoped Quality Report

`get_data_quality_report(scope=...)` supports:

- global scope
- venue
- venue/year
- topic
- topic/venue/year
- domain
- source

If a metric cannot be computed from the current schema for a given scope, it is
returned as `null` with a `metric_not_available_for_scope` warning.

## Provenance Tools

Read-only provenance tools expose traceable facts:

- `get_paper_provenance`
- `get_topic_source_coverage`
- `get_venue_year_source_coverage`

When a field is unavailable in the current schema, such as a general
`source_url`, the service returns `null` plus a warning instead of fabricating a
value.

## Legacy MCP vs v0.1 Contracted MCP

Existing tools remain unchanged:

- `get_overview`
- `get_status`
- `list_venues`

New v0.1 wrappers follow the `data/meta/warnings/evidence` response contract:

- `get_overview_v01`
- `get_status_v01`
- `list_venues_v01`

## Acceptance Criteria

- Existing tests pass.
- New tests pass.
- No destructive migration is introduced.
- Existing MCP tools remain available.
- New v0.1 MCP tools follow the response contract.
- `paper_topics` exists and is rebuildable.
- `get_venue_year_topic` prefers persisted facts.
- Runtime fallback emits `runtime_topic_matching_fallback`.
- Provenance responses include paper, sources, topics, warnings, and evidence.
- Scoped quality reports use the existing warning thresholds.
- Frontend metric policy remains `relative_frequency` primary and `count`
  secondary.
- arXiv remains preprint evidence by default and is not accepted conference
  evidence by default.
