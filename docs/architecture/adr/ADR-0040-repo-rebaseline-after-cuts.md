---
ADR: 0040
Title: Green-field repo rebaseline after architecture cuts
Status: Accepted
Version: 1.0
Date: 2026-03-19
Related:
  - "[ADR-0023: Hard-cut v1 canonical route surface](./ADR-0023-hard-cut-v1-canonical-route-surface.md)"
  - "[SPEC-0000: HTTP API contract](../spec/SPEC-0000-http-api-contract.md)"
  - "[SPEC-0016: V1 route namespace and literal guardrails](../spec/SPEC-0016-v1-route-namespace-and-literal-guardrails.md)"
  - "[requirements.md](../requirements.md)"
  - "[Green-field simplification program](../../plan/greenfield-simplification-program.md)"
References:
  - "[manifest.json (pack)](../../plan/greenfield-evidence/manifest.json)"
  - "[Prompt 11 (pack)](../../../.agents/nova_greenfield_codex_pack/prompts/11_chore_repo-rebaseline-ci-release.md)"
---

## Summary

After the green-field architecture branches land, Nova requires a **mandatory
repo-wide rebaseline**: workspaces, dependency floors, CI, release flow, docs,
and verification commands must match the **smaller** final system.

## Context

- Deleting services without removing release logic, package references,
  workflows, and docs produces a misleading repository
  ([GFR-R10](../requirements.md#gfr-r10--repo-should-shrink-after-every-accepted-branch)).
- This is the **final** program step; manifest branch score **9.17/10** (order 11)
  is program prioritization weighting, not a substitute for Framework A/B/C
  option tables.
- Execution order: program branch 11 after branch 10 merges.

## Alternatives

- **A:** Merge feature branches only; defer cleanup (“ship half-migrated”).
- **B:** Ad-hoc fixes when something breaks; no coordinated rebaseline.
- **C:** Scheduled **repo-wide rebaseline** after cuts.

## Decision

**Option C** is accepted.

Implementation commitments:

- Remove dead workspace packages, manifests, workflows, infra snippets, and doc
  references.
- Refresh `uv.lock` / dependency floors and npm workspace members for the final
  graph.
- Tighten CI matrix and scripts so gates match the reduced surface.
- Update `README.md`, `docs/**`, and release helpers for copy-paste accuracy.
- Branch `chore/repo-rebaseline-ci-release`.

## Related requirements

- [GFR-R9](../requirements.md#gfr-r9--deterministic-build-and-verification)
- [GFR-R10](../requirements.md#gfr-r10--repo-should-shrink-after-every-accepted-branch)

## Consequences

1. **Positive:** New contributors see one system; CI confusion drops.
2. **Trade-offs:** Large diff; disciplined review and full gate runs required.
3. **Ongoing:** Rebaseline is **blocking** for declaring the green-field program
   complete.

## Changelog

- 2026-03-19: Canonical ADR ported from green-field pack ADR-0008.
