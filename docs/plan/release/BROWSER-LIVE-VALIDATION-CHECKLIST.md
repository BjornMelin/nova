# Browser Live Validation Checklist (WS5)

Status: Active
Owner: Release Architecture + Platform Operations
Last updated: 2026-03-04

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
  agent-browser auth save dash-sso --url "$AUTH_LOGIN_URL" --username "$AUTH_USERNAME" --password "$AUTH_PASSWORD"
  agent-browser auth login dash-sso
  agent-browser open "${DASH_BASE_URL}/pca-discrete"
  agent-browser wait --load networkidle
fi
```

Pass:

- Auth-enabled env: user reaches app page post-login.
- Session storage/cookie context remains valid through upload/process steps.

### C04: Upload and process flow

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

### C05: Download controls

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

### C06: Network/console evidence

```bash
agent-browser network requests > "$OUT/network.json"
agent-browser console > "$OUT/console.log" || true
agent-browser errors > "$OUT/errors.log" || true
agent-browser trace stop
```

Pass:

- Requests include canonical `/v1/transfers` and `/v1/jobs`.
- No active legacy namespace route usage.
- No critical unhandled exceptions affecting user flow.

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
- Require full artifact set and immutable evidence links in release ledger.

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
