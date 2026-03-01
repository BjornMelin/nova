# Auth0 CLI + a0deploy runbook (nova)

## Purpose

Define the canonical `nova` procedure for Auth0 tenant-as-code operations using `auth0` CLI for authentication and `a0deploy` for import/export.

## Preconditions

1. Install CLIs:
   - `auth0`
   - `a0deploy`
2. Confirm you are in repo root.
3. Create an untracked local overlay from one template in
   `infra/auth0/env/*.env.example`.

## Create local overlays (required)

Never source tracked `*.env.example` files directly. Copy a template to an
untracked `*.env` file and put real credentials in that local file.

```bash
cp infra/auth0/env/dev.env.example infra/auth0/env/dev.env
```

For scaffold environments:

```bash
cp infra/auth0/env/qa.env.example infra/auth0/env/qa.env
cp infra/auth0/env/pr.env.example infra/auth0/env/pr.env
```

## Local-dev operating mode (current)

- Use **only** `infra/auth0/env/dev.env` for local work.
- This maps all local development to a single shared dev tenant now.
- `qa.env.example` and `pr.env.example` are scaffold placeholders reserved for
  later cutover.

Cutover mapping plan (when approved):

- `dev.env.example` -> stable developer integration tenant template
- `qa.env.example` -> pre-production validation tenant template
- `pr.env.example` -> ephemeral PR tenant template

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
source infra/auth0/env/dev.env
set +a

export AUTH0_KEYWORD_REPLACE_MAPPINGS="$(cat "$AUTH0_KEYWORD_MAPPINGS_FILE")"
a0deploy import --input_file "$AUTH0_INPUT_FILE"
```

## Export current tenant state (snapshot)

```bash
set -a
source infra/auth0/env/dev.env
set +a

export AUTH0_KEYWORD_REPLACE_MAPPINGS="$(cat "$AUTH0_KEYWORD_MAPPINGS_FILE")"
a0deploy export --format yaml --output_folder infra/auth0/output/dev
```

## Overlay switching

Use the target local overlay file:

- `infra/auth0/env/dev.env` (active)
- `infra/auth0/env/qa.env` (local QA copy from `qa.env.example`)
- `infra/auth0/env/pr.env` (local PR copy from `pr.env.example`)

```bash
set -a
source infra/auth0/env/qa.env
set +a

export AUTH0_KEYWORD_REPLACE_MAPPINGS="$(cat "$AUTH0_KEYWORD_MAPPINGS_FILE")"
a0deploy import --input_file "$AUTH0_INPUT_FILE"
```

Do not use QA/PR overlays until placeholders are replaced and cutover is
approved.

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
