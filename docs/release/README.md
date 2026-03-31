# Release artifacts (committed)

Status: Active
Last reviewed: 2026-03-24

This directory holds **machine-stable files** consumed by release automation,
GitHub workflows, and contract checks. Operator procedures live under
[`../runbooks/release/README.md`](../runbooks/release/README.md) and
[`../runbooks/provisioning/README.md`](../runbooks/provisioning/README.md).

Canonical path constants: [`scripts/release/release_paths.py`](../../scripts/release/release_paths.py).

## Authority / references

- `../AGENTS.md`
- `../overview/IMPLEMENTATION-STATUS-MATRIX.md`
- `../plan/GREENFIELD-WAVE-2-EXECUTION.md`
- `../architecture/adr/ADR-0033-canonical-serverless-platform.md`
- `../architecture/adr/ADR-0038-docs-authority-reset.md`
- `../architecture/spec/SPEC-0027-public-api-v2.md`
- `../architecture/spec/SPEC-0029-platform-serverless.md`
- `../architecture/spec/SPEC-0031-docs-and-tests-authority-reset.md`

## Files

| File | Role |
| --- | --- |
| [`RELEASE-VERSION-MANIFEST.md`](RELEASE-VERSION-MANIFEST.md) | Selective per-unit versions for the canonical Nova monorepo release graph; SHA256 gates promotion |
| [`runtime-config-contract.generated.md`](runtime-config-contract.generated.md) | Generator-owned deploy/runtime contract for living Lambda surfaces only; **do not edit** -- run `uv run python scripts/release/generate_runtime_config_contract.py` |

JSON fixture for the same contract: `packages/contracts/fixtures/runtime_config_contract.json` (also generator-owned).

## Historical hard-cut checklist

Archived checklist (non-authoritative): [`../history/2026-03-v1-hard-cut/release/HARD-CUTOVER-CHECKLIST.md`](../history/2026-03-v1-hard-cut/release/HARD-CUTOVER-CHECKLIST.md).
