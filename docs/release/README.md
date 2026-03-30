# Release artifacts (committed)

Status: Active
Last reviewed: 2026-03-24

This directory holds **machine-stable files** consumed by release automation,
GitHub workflows, and contract checks. Operator procedures live under
[`../runbooks/release/README.md`](../runbooks/release/README.md) and
[`../runbooks/provisioning/README.md`](../runbooks/provisioning/README.md).

Canonical path constants: [`scripts/release/release_paths.py`](../../scripts/release/release_paths.py).

## Authority / references

- `../architecture/adr/ADR-0023-hard-cut-v1-canonical-route-surface.md`
- `../architecture/spec/superseded/SPEC-0000-http-api-contract.md`
- `../architecture/spec/SPEC-0016-v1-route-namespace-and-literal-guardrails.md`
- `../architecture/spec/SPEC-0027-public-api-v2.md`
- `../architecture/requirements.md`
- `../plan/GREENFIELD-WAVE-2-EXECUTION.md`

## Files

| File | Role |
| --- | --- |
| [`RELEASE-VERSION-MANIFEST.md`](RELEASE-VERSION-MANIFEST.md) | Selective per-unit versions for the canonical Nova monorepo release graph; SHA256 gates promotion |
| [`runtime-config-contract.generated.md`](runtime-config-contract.generated.md) | Operator-facing env/deploy matrix; **do not edit** -- run `uv run python scripts/release/generate_runtime_config_contract.py` |

JSON fixture for the same contract: `packages/contracts/fixtures/runtime_config_contract.json` (also generator-owned).

## Historical hard-cut checklist

Archived checklist (non-authoritative): [`../history/2026-03-v1-hard-cut/release/HARD-CUTOVER-CHECKLIST.md`](../history/2026-03-v1-hard-cut/release/HARD-CUTOVER-CHECKLIST.md).
