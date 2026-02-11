# SUBPLAN-003: Docs automation + OpenAPI publishing

## Goal

Create a docs site and automatically publish it on merge/release.

## Steps

1. Add MkDocs Material site.
2. Add an “API Reference” page that embeds Scalar UI.
3. GitHub Actions:
   - build docs
   - publish to S3 (preferred) or GitHub Pages (initial)
4. Add client generation placeholders (TS + R) in CI as artifacts.

## Exit criteria

- Docs site updates automatically and includes interactive API reference.
