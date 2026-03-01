# Auth0 tenant-as-code (a0deploy)

This directory is the canonical Auth0 tenant configuration for `nova`.

## Layout

- `tenant/tenant.yaml`: shared Auth0 resource definition using keyword placeholders.
- `env/dev.env.example`: template for local-dev overlay (single shared dev tenant).
- `env/qa.env.example`: template for QA scaffold overlay (cutover later).
- `env/pr.env.example`: template for PR scaffold overlay (cutover later).
- `mappings/*.json`: canonical keyword replacement payloads per environment.

## Safety defaults

All overlays pin:

- `AUTH0_ALLOW_DELETE=false`

This protects against destructive deletes during import unless explicitly changed for a controlled migration event.

## Environment overlays

Current operating mode:

- **dev (active):** copy `env/dev.env.example` to untracked `env/dev.env`,
  provide real credentials locally, and use `env/dev.env`.
- **qa/pr (scaffold):** `*.env.example` templates remain placeholders until
  cutover is approved; if needed, copy to local untracked `qa.env` / `pr.env`.

This is intentional to keep a single active tenant path during local modernization while preserving final-state shape for QA/PR rollout.

## How keyword replacement works

`tenant/tenant.yaml` uses placeholder tokens (for example `@@WEB_CALLBACK_URL@@`).
At runtime, export `AUTH0_KEYWORD_REPLACE_MAPPINGS` from `AUTH0_KEYWORD_MAPPINGS_FILE`, then run `a0deploy` against the shared tenant file.

See runbook: `docs/plan/release/AUTH0-A0DEPLOY-RUNBOOK.md`.

## Contract validation

Run from repo root:

```bash
python -m scripts.release.validate_auth0_contract
```

This enforces overlay safety settings and verifies keyword mapping coverage for every token in `tenant/tenant.yaml`.
