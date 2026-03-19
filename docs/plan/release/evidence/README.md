# Release evidence artifacts

Status: Active
Last reviewed: 2026-03-19

## Purpose

`docs/plan/release/evidence/` holds **durable evidence** referenced from
[`../evidence-log.md`](../evidence-log.md): narrative mirrors (for example
archived plan extracts), JSON exports from validation scripts, and screenshots
paths cited in the log.

## When to add a file here

- **Append-first:** Routine validation runs are recorded in
  [`evidence-log.md`](../evidence-log.md) (UTC time, operator, gate, links).
- **Sibling file:** Add a new file under `evidence/` when the log needs a
  stable, reviewable attachment (JSON report, markdown mirror of an external
  artifact, or a dated evidence bundle). Name with ISO date prefix
  (`YYYY-MM-DD-…`) or a dated subdirectory for multi-file sets.

## When not to

- Do not store secrets, tokens, or presigned URLs.
- Do not duplicate content that already lives only in CI artifacts unless the
  repo needs a durable audit pointer (then redact and link).

## JSON under dated folders

Folders such as `2026-03-05-live-runtime-route-authority/` are intentional
snapshots. Keep them immutable after publication; add new dated folders for new
runs rather than overwriting.

## Index

Parent catalog: [`../README.md`](../README.md).
