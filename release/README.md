# Release metadata

Status: Active
Last reviewed: 2026-04-10

This directory holds **machine-owned committed release metadata** consumed by
the AWS-native release control plane and repo contract checks. Human operator
procedures live under [`docs/runbooks/release/README.md`](../docs/runbooks/release/README.md)
and [`docs/runbooks/provisioning/README.md`](../docs/runbooks/provisioning/README.md).

Canonical path constants: [`scripts/release/release_paths.py`](../scripts/release/release_paths.py).

## Authority / references

- `AGENTS.md`
- `docs/overview/IMPLEMENTATION-STATUS-MATRIX.md`
- `docs/architecture/adr/ADR-0033-canonical-serverless-platform.md`
- `docs/architecture/adr/ADR-0038-docs-authority-reset.md`
- `docs/architecture/spec/SPEC-0027-public-api-v2.md`
- `docs/architecture/spec/SPEC-0029-platform-serverless.md`
- `docs/architecture/spec/SPEC-0031-docs-and-tests-authority-reset.md`

## Files

| File | Role |
| --- | --- |
| [`RELEASE-PREP.json`](RELEASE-PREP.json) | Canonical machine-readable release intent: changed units, planned versions, commit baseline, and prep metadata. `prepared_from_commit` records the reviewed source commit that fed release prep. |
| [`RELEASE-VERSION-MANIFEST.md`](RELEASE-VERSION-MANIFEST.md) | Human-reviewable mirror of `RELEASE-PREP.json`; SHA256 gates promotion and execution-manifest continuity |

The AWS-native release control plane writes the execution manifest from the
merged deploy commit SHA. `release/RELEASE-PREP.json` may therefore point at
the release PR source commit while the execution manifest pins the merged
commit; that relationship is validated by ancestry.

Generator-owned runtime deploy contract markdown lives at [`docs/contracts/runtime-config-contract.generated.md`](../docs/contracts/runtime-config-contract.generated.md).
JSON fixture for the same runtime contract lives at `packages/contracts/fixtures/runtime_config_contract.json`.

## Historical hard-cut checklist

Archived checklist (non-authoritative): [`docs/history/2026-03-v1-hard-cut/release/HARD-CUTOVER-CHECKLIST.md`](../docs/history/2026-03-v1-hard-cut/release/HARD-CUTOVER-CHECKLIST.md).
