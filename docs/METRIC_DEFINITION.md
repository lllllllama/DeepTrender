# DeepTrender Metric Definition

DeepTrender trend metrics are paper-centric and traceable.

## Counting Rule

`count` is always the number of distinct structured `paper_id` values in the queried scope.

Keyword aliases and surface forms are canonicalized before counting. If one paper contains multiple aliases for the same canonical keyword, that paper contributes `1` to that canonical keyword.

## Supported Trend Metrics

Every keyword trend point should expose:

- `count`: distinct `paper_id` count for the keyword in the bucket.
- `relative_frequency`: `count / distinct paper_id count in the bucket`.
- `rank`: rank among canonical keywords in the same scope and bucket, ordered by `count` descending.

## arXiv Buckets

arXiv year, month, week, and day buckets use `published_at`. If `published_at` is missing, the bucket falls back to `retrieved_at` and must surface a warning in quality output.

Required arXiv scopes are `ALL`, `cs.LG`, `cs.CV`, `cs.CL`, `cs.AI`, and `cs.RO`. Category-specific keyword trends must be isolated from each other.

## Prohibited Final Counts

Final trend `count` values must not use:

- YAKE scores.
- raw word frequency.
- frequency in concatenated title or abstract text.

Extractor output can create `paper_keywords`, but the final trend count is still distinct canonical keyword matches per `paper_id`.

## Evidence

Top keyword trend buckets must expose evidence samples with `paper_id`, title, source, publication timestamp when available, and the matched raw keyword.

## Warnings

Empty or weak data must not be presented as normal. Supported warning codes include:

- `low_sample_size`
- `stale_data`
- `registered_no_papers`
- `missing_source_mapping`
- `weak_growth_signal`
