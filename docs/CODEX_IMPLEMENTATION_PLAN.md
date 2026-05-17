# Codex Implementation Plan v0.1

This plan tracks the v0.1 implementation requested in `reference/change.md`.

## Step 1: Policy and Taxonomy Config

- Add data policy, taxonomy policy, MCP response contract, and frontend
  information architecture docs.
- Add domain, topic, alias, and review-queue YAML files.
- Keep aliases strict and put related concepts in `related_topics`.

## Step 2: Taxonomy Loader and Resolver

- Add `src/taxonomy` package.
- Load YAML files with stable validation.
- Resolve domains from arXiv categories and text.
- Resolve topics by canonical name, strict alias, and phrase evidence.
- Keep child topics excluded unless `include_children=true`.

## Step 3: Serving Layer

- Add `src/services` package.
- Centralize quality warnings.
- Add MCP-ready service functions using the `data/meta/warnings/evidence`
  contract.
- Add frontend-ready view builders that use `relative_frequency` as the primary
  metric and raw `count` as the secondary metric.

## Step 4: MCP Integration and Tests

- Expose new read-only MCP tools while preserving existing tools.
- Add tests for taxonomy loading, topic resolution, MCP response contract, and
  warning thresholds.
- Run existing and new tests before final commit.
