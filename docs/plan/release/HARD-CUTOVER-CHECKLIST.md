# Hard-Cutover Checklist

Status: Finalized
Owner: Release Architecture

## 1. Runtime Contract Cutover

- [x] All runtime endpoints use `/api/transfers/*` and `/api/jobs/*`.
- [x] No deprecated alias route namespace remains in runtime code.
- [x] OpenAPI regression test enforces split-route contract.
- [x] Generated OpenAPI client smoke test passes.

## 2. Auth and Security

- [x] Local JWT mode remains canonical default.
- [x] Sync JWT verification in async flows runs on thread boundary.
- [x] Remote auth mode is optional and fail-closed.
- [x] RFC6750 `WWW-Authenticate` behavior verified.
- [x] Logging sanitization blocks token/presigned URL leakage.

## 3. Async and Reliability

- [x] Enqueue failures return `503` with `queue_unavailable`.
- [x] Failed enqueue responses are not replay-cached as success.
- [x] Worker result-update transition guardrails enforced.
- [x] Queue lag + worker throughput metrics emitted.
- [x] SQS publisher retry configuration and error mappings validated.

## 4. Cache and Readiness

- [x] Two-tier cache behavior (local + shared) validated.
- [x] Redis outage fallback behavior validated.
- [x] Cache hit/miss/fallback counters validated.
- [x] `/readyz` excludes feature-flag pass/fail coupling.

## 5. Cross-Repo Compatibility

- [x] `container-craft` docs and renderer mappings align with split routes.
- [x] `JOBS_SQS_RETRY_MODE` and
  `JOBS_SQS_RETRY_TOTAL_MAX_ATTEMPTS` contract aligned.
- [x] `dash-pca` migration to `nova_dash_bridge` and split routes complete.
- [x] `dash-pca` async uploader and settings aliases validated.

## 6. Final Live Gates (External AWS Execution Required)

- [x] Operator runbook is published:
  `docs/plan/release/NONPROD-LIVE-VALIDATION-RUNBOOK.md`
- [ ] Sidecar ALB route + health behavior validated in non-prod AWS.
- [ ] Non-prod end-to-end smoke completed.
- [ ] CloudWatch dashboards/alarms synthetic-failure validation completed.

## 7. Release Artifacts

- [x] Final release notes published:
  `docs/plan/release/RELEASE-NOTES-2026-02-12.md`
