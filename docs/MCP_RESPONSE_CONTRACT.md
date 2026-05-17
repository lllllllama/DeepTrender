# DeepTrender MCP Response Contract v0.1

All new MCP-style service responses must use this shape:

```json
{
  "data": {},
  "meta": {},
  "warnings": [],
  "evidence": []
}
```

## Required Metadata

Every response must include:

- `meta.taxonomy_version`
- `meta.data_policy_version`
- `meta.generated_at`
- `meta.source_layer`
- `meta.limit`
- `meta.offset`
- `meta.has_more`

## Query Responses

Query tools must include `data.normalized_query`.

Topic queries must include:

- `input_topic`
- `canonical_topic`
- `topic_id`
- `domain`
- `include_children`
- `aliases_used`

Conference-specific tools must also include:

- `conference_source_policy`
- `quality_scope`

## Warning Codes

Supported v0.1 warning codes:

- `unknown_quality_ratio_high`
- `empty_abstract_ratio_high`
- `single_source_ratio_high`
- `small_sample`
- `low_topic_match_confidence`
- `only_arxiv_evidence_for_conference_query`

## Pagination

Responses with lists should return the requested slice and report:

- `meta.limit`
- `meta.offset`
- `meta.has_more`
- `data.pagination`

## Trend Metrics

Frontend-facing and MCP trend responses must make `relative_frequency` the
primary trend metric and also expose raw `count` values.
