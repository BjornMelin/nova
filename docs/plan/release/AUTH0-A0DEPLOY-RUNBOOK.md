# Auth0 CLI + a0deploy runbook (nova)

## Purpose

Define the canonical `nova` procedure for Auth0 tenant-as-code operations using `auth0` CLI for authentication and `a0deploy` for import/export.

## Preconditions

1. Install CLIs:
   - `auth0`
   - `a0deploy`
2. Confirm you are in repo root.
3. Use one environment overlay in `infra/auth0/env/*.env.example`.

## Local-dev operating mode (current)

- Use **only** `infra/auth0/env/dev.env.example` for local work.
- This maps all local development to a single shared dev tenant now.
- `qa.env` and `pr.env` are scaffold placeholders reserved for later cutover.

Cutover mapping plan (when approved):

- `dev.env` -> stable developer integration tenant
- `qa.env` -> pre-production validation tenant
- `pr.env` -> ephemeral PR tenant profile

## Authenticate with Auth0 CLI

```bash
auth0 login
```

Optionally confirm tenant context:

```bash
auth0 tenants list
```

## Deploy from tenant-as-code (import)

Example: local development overlay.

```bash
set -a
source infra/auth0/env/dev.env.example
set +a

export AUTH0_KEYWORD_REPLACE_MAPPINGS="$(cat "$AUTH0_KEYWORD_MAPPINGS_FILE")"
a0deploy import --input_file "$AUTH0_INPUT_FILE"
```

## Export current tenant state (snapshot)

```bash
set -a
source infra/auth0/env/dev.env.example
set +a

export AUTH0_KEYWORD_REPLACE_MAPPINGS="$(cat "$AUTH0_KEYWORD_MAPPINGS_FILE")"
a0deploy export --format yaml --output_folder infra/auth0/output/dev
```

## Overlay switching

Use the target overlay file exactly as-is:

- `infra/auth0/env/dev.env.example` (active)
- `infra/auth0/env/qa.env.example` (scaffold)
- `infra/auth0/env/pr.env.example` (scaffold)

```bash
set -a
source infra/auth0/env/qa.env.example
set +a

export AUTH0_KEYWORD_REPLACE_MAPPINGS="$(cat "$AUTH0_KEYWORD_MAPPINGS_FILE")"
a0deploy import --input_file "$AUTH0_INPUT_FILE"
```

Do not use QA/PR overlays until placeholders are replaced and cutover is approved.

## Safety controls

- `AUTH0_ALLOW_DELETE=false` is mandatory default across overlays.
- Never commit real `AUTH0_CLIENT_SECRET` values to git.
- Keep each `infra/auth0/mappings/*.json` file valid JSON.

## Automated contract check

Run this before each import/export:

```bash
python -m scripts.release.validate_auth0_contract
```

## Validation checklist

- `AUTH0_ALLOW_DELETE` equals `false`.
- `AUTH0_INPUT_FILE` points to `infra/auth0/tenant/tenant.yaml`.
- `AUTH0_KEYWORD_MAPPINGS_FILE` points to the expected environment mapping JSON.
- Mapping keys cover every `@@KEY@@` token in tenant YAML.
- Domain/client credentials are set from secure local secrets, not committed plaintext.
