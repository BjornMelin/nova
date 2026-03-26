# Browser Live Validation Checklist (WS5)

Status: Active
Owner: Release Architecture + Platform Operations
Last updated: 2026-03-19

## When to use this vs NONPROD runbook

- **This checklist:** Scripted browser validation (`agent-browser`) for
  dash + Nova URLs, route contract JSON, and non-mutating smoke steps.
- **[nonprod-live-validation-runbook.md](nonprod-live-validation-runbook.md):**
  Broader AWS control-plane and pipeline gates. Run both when certifying a
  release to prod.

## Authority / Related Documents

Authority:
[README.md#canonical-documentation-authority-chain](README.md#canonical-documentation-authority-chain)

## Purpose

Define deterministic browser/live validation gates for deployed `dash-pca` +
Nova runtime integration using `agent-browser`. This complements local
Playwright pytest e2e by certifying environment-integrated behavior.

## Inputs

- `ENVIRONMENT` (`dev` or `prod`)
- `DASH_BASE_URL` (HTTPS)
- `NOVA_BASE_URL` (HTTPS)
- `E2E_UPLOAD_FILE` (stable fixture)
- optional auth inputs:
  - `AUTH_ENABLED` (`true`/`false`)
  - `AUTH_LOGIN_URL`
  - `AUTH_USERNAME`
  - `AUTH_PASSWORD`

## Execution (non-mutating)

```bash
REPO_ROOT="$(git rev-parse --show-toplevel)"
cd "$REPO_ROOT"
set -euo pipefail
RUN_ID="$(date -u +%Y%m%dT%H%M%SZ)"
OUT=".artifacts/browser-live-validation/${RUN_ID}"
mkdir -p "$OUT"
```

### C01: Canonical route contract preflight

```bash
python3 scripts/release/validate_route_contract.py \
  --base-url "$NOVA_BASE_URL" \
  --report-path "$OUT/nova-route-contract.json"
```

Pass:

- Report status is `passed`.
- Canonical routes are non-`404` and `<500`.
- Legacy routes return `404`.

### C02: Browser landing and trace capture

```bash
agent-browser trace start "$OUT/trace.zip"
agent-browser open "${DASH_BASE_URL}/pca-discrete"
agent-browser wait --load networkidle
agent-browser screenshot "$OUT/landing.png"
agent-browser snapshot -i > "$OUT/landing.snapshot.txt"
```

Pass:

- Page loads and upload shell is visible.

### C03: Auth/session contract

```bash
if [ "${AUTH_ENABLED:-false}" = "true" ]; then
  printf '%s' "$AUTH_PASSWORD" | agent-browser auth save dash-sso --url "$AUTH_LOGIN_URL" --username "$AUTH_USERNAME" --password-stdin
  agent-browser auth login dash-sso
  agent-browser open "${DASH_BASE_URL}/pca-discrete"
  agent-browser wait --load networkidle
fi
```

When `AUTH_ENABLED=true`, `agent-browser auth save` and `agent-browser auth login`
mutate the local browser session/cookie context used for validation, but they do
not create tenant-visible runtime data.

Pass:

- Auth-enabled env: user reaches app page post-login.
- Session storage/cookie context remains valid through auth flow.

### C04: Network/console evidence

```bash
agent-browser network requests > "$OUT/network.json"
agent-browser console > "$OUT/console.log" || true
agent-browser errors > "$OUT/errors.log" || true
agent-browser trace stop
```

Pass:

- Requests include canonical `/v1/transfers` and `/v1/exports`.
- No active legacy namespace route usage.
- No critical unhandled exceptions affecting user flow.

## Execution (controlled mutating tests: upload & processing)

⚠️ **Side effects:** The following steps create/modify tenant-visible artifacts and may trigger async processing. Run only against isolated environment data and unique test scope.

- Required environment scoping:
  - `ENVIRONMENT=dev` (or approved staging sandbox).
  - Optional isolation prefix: `BROWSER_LIVE_SCOPE` (defaults to `$RUN_ID`).
  - If your tenant supports it, pass the scope through `E2E_UPLOAD_FILE` metadata or URL query args so created jobs/data are discoverable and removable.

```bash
export BROWSER_LIVE_SCOPE="${BROWSER_LIVE_SCOPE:-$RUN_ID}"
```

### C05: Upload and process flow

```bash
agent-browser upload "#upload-data input[type=file]" "$E2E_UPLOAD_FILE"
agent-browser wait "#upload-insights"
agent-browser click "#process-button"
agent-browser wait "#variance-plot .js-plotly-plot"
agent-browser click "#tab-tab-scores"
agent-browser wait "#scores-plot .js-plotly-plot"
agent-browser click "#tab-tab-loadings"
agent-browser wait "#loadings-plot .js-plotly-plot"
agent-browser screenshot "$OUT/post-process.png"
```

Pass:

- Upload insights show file metadata.
- Processing completes and PCA plots render.

### C06: Download controls

```bash
agent-browser is enabled "#download-all-pngs-btn"
agent-browser is enabled "#download-excel-btn"
agent-browser is enabled "#download-bundle-btn"
agent-browser download "#download-excel-btn" "$OUT/result.xlsx"
test -s "$OUT/result.xlsx"
```

Pass:

- All download actions enabled.
- Excel artifact downloaded and non-empty.

### C07: Required post-run cleanup

```bash
# Record run scope for ticketing/cleanup.
echo "RUN_ID=${RUN_ID}" >> "$OUT/run-metadata.txt"
echo "BROWSER_LIVE_SCOPE=${BROWSER_LIVE_SCOPE}" >> "$OUT/run-metadata.txt"

# Best-effort cleanup: if tenant-specific cleanup endpoint is configured,
# remove run-scoped job artifacts before leaving the env.
if [ -n "${BROWSER_LIVE_CLEANUP_URL:-}" ]; then
  curl -fsS -X POST "${BROWSER_LIVE_CLEANUP_URL}" \
    -H "Content-Type: application/json" \
    -d "{\"scope\":\"${BROWSER_LIVE_SCOPE}\"}" || true
fi
```

Pass:

- Cleanup command is executed when `BROWSER_LIVE_CLEANUP_URL` is configured.
- Run scope is recorded for traceability and support.
- Evidence artifacts remain in `$OUT` for release ledger attachment.

### C08: Optional manual cleanup verification

If your environment cannot isolate by scope, run a manual tenant cleanup before the next release validation window and document deletion confirmation in the artifact summary.

## CI Gating Policy

### Dev promotion (`ValidateDev` companion gate)

- Block on any `P0`:
  - canonical route contract failure
  - auth/session failure in auth-enabled environment
  - upload/process flow failure
  - non-canonical route usage
- `P1` only with time-boxed waiver and remediation issue link.

### Prod promotion (`ValidateProd` companion gate)

- Block on any `P0` or unwaived `P1`.
- Require full artifact set and immutable evidence links on the promotion PR or
  per [`release-policy.md`](release-policy.md) §6.

## Artifact Contract

Produce one JSON summary that conforms to:

- `docs/contracts/browser-live-validation-report.schema.json`

Minimum required artifacts:

- `nova-route-contract.json`
- `trace.zip`
- `landing.png`
- `post-process.png`
- `network.json`
- `console.log`
- `errors.log`

## Relationship to dash-pca Playwright pytest e2e

- Playwright pytest e2e (`tests/e2e/**` in `dash-pca`) remains the deterministic
  code regression suite for local/test-server execution.
- WS5 browser/live validation adds deployed-environment certification:
  DNS/TLS path, auth/session integration, and release-evidence artifacts.
