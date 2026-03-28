# Green-field evidence (non-normative)

Status: Supporting material
Last updated: 2026-03-19

Files in this directory are **copies** of audit and scoring artifacts from
`.agents/nova_greenfield_codex_pack/`. They support reasoning traceability and
program prioritization; they are **not** part of the active Nova architecture
authority set.

**Normative decisions** live under:

- `docs/architecture/adr/ADR-0033*.md` through `ADR-0041*.md`
- `docs/architecture/spec/SPEC-0027*.md` through `SPEC-0029*.md`
- `docs/architecture/requirements.md` (GFR requirements)
- `docs/plan/greenfield-simplification-program.md`

Do not cite CSV scores as runtime law; cite the Accepted ADRs they informed.

## Contents

| File | Role |
| --- | --- |
| `EXECUTIVE_AUDIT.md` | Independent second-pass audit narrative |
| `DECISION_FRAMEWORKS_AND_SCORES.md` | Scoring frameworks A/B/C used in pack ADRs |
| `RISK_REGISTER_AND_MITIGATIONS.md` | Risk inventory |
| `REJECTED_AND_DEFERRED_OPTIONS.md` | Options explicitly not chosen |
| `ENTROPY_REDUCTION_LEDGER.md` | Deletion / simplification ledger |
| `CHANGE_IMPACT_MAP.md` | File/package impact by branch |
| `manifest.json` | Branch order and semver metadata |
| `TARGET_ARCHITECTURE.md` | Composite platform narrative (pack copy) |
| `IMPLEMENTATION_PROGRAM.md` | Program copy (canonical router is `../greenfield-simplification-program.md`) |
| `decision_scores.csv` | Machine-readable score rows |
| `entropy_ledger.csv` | Machine-readable entropy rows |
