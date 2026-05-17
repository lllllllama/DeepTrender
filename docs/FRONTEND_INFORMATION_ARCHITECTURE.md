# Frontend Information Architecture v0.1

DeepTrender frontend views should present facts first and interpretation second.
Views should make source scope and quality warnings visible without overstating
conference acceptance.

## Primary Views

1. Domain overview
- Domain metadata.
- Topic list.
- Data quality warnings.

2. Topic page
- Canonical topic.
- Aliases.
- Related topics.
- Definitions and source mappings.

3. Venue topic chart
- Yearly `relative_frequency` as the primary metric.
- Yearly `count` as the secondary metric.
- Source scope and warnings.

4. Venue/year/topic detail
- Normalized query.
- Matched paper count.
- Total venue paper count.
- Relative frequency.
- Evidence and warning details.

## Chart Contract

```json
{
  "chart_type": "line",
  "primary_metric": "relative_frequency",
  "x": ["2020", "2021", "2022"],
  "series": [
    {
      "name": "panoptic segmentation",
      "relative_frequency": [0.012, 0.009, 0.006],
      "count": [18, 14, 10]
    }
  ],
  "warnings": []
}
```

## Source Display

Conference views must show whether evidence is accepted, preprint, unknown, or
mixed. arXiv-only support for a conference query must be flagged.
