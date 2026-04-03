# Auth0 Deploy CLI + SDK runbook (nova)

## Purpose

Define the canonical `nova` procedure for Auth0 tenant-as-code operations using
repo-local Python wrappers plus `auth0-deploy-cli`. `auth0` CLI is optional and
only for human troubleshooting.

Reusable workflow contract authority:

- `docs/architecture/spec/SPEC-0022-auth0-tenant-ops-reusable-workflow-contract.md`
- `docs/contracts/workflow-auth0-tenant-ops-v1.schema.json`
- `scripts/release/validate_auth0_contract.py`

## Preconditions

1. Confirm you are in repo root.
2. Create an untracked local overlay from one template in
   `infra/auth0/env/*.env.example`.
3. Do not export real Auth0 secrets into tracked files or shell startup files.

## Create local overlays (required)

Never source tracked `*.env.example` files directly. Copy a template to an
untracked `*.env` file and put real credentials in that local file.

Preferred local writer:

```bash
read -r -s AUTH0_CLIENT_SECRET_VALUE
printf '\n'
uv run python -m scripts.release.persist_auth0_env \
  --environment dev \
  --domain REPLACE_WITH_DEV_TENANT_DOMAIN \
  --client-id <tenant-ops-client-id> \
  --client-secret-env-var AUTH0_CLIENT_SECRET_VALUE
unset AUTH0_CLIENT_SECRET_VALUE
```

Repeat for PR/non-prod:

```bash
read -r -s AUTH0_CLIENT_SECRET_VALUE
printf '\n'
uv run python -m scripts.release.persist_auth0_env \
  --environment pr \
  --domain REPLACE_WITH_PR_TENANT_DOMAIN \
  --client-id <tenant-ops-client-id> \
  --client-secret-env-var AUTH0_CLIENT_SECRET_VALUE
unset AUTH0_CLIENT_SECRET_VALUE
```

The writer refuses to persist a local env file unless the target path is
gitignored.

To refresh an existing local env file after the repo env contract changes:

```bash
uv run python -m scripts.release.persist_auth0_env \
  --environment dev \
  --from-env-file infra/auth0/env/dev.env
```

## Active operating mode (current)

- `infra/auth0/env/dev.env` maps to the shared development tenant.
- `infra/auth0/env/pr.env` maps to the shared PR/non-prod tenant.
- `infra/auth0/env/qa.env` remains optional and scaffold-only.

## Optional Auth0 CLI login

```bash
auth0 login
```

Optional troubleshooting only:

```bash
auth0 tenants list
```

## One-time tenant seed step

Auth0 does not let an M2M client create its own Management API grant before it
already has Management API access. That first grant must be seeded once in the
dashboard or by a separate bootstrap principal.

Required once per tenant for `nova-tenant-ops-<env>`:

1. Create the non-interactive `nova-tenant-ops-<env>` app in the target
   tenant.
2. Authorize that app against the **Auth0 Management API** with these scopes:
   - `read:clients`
   - `create:clients`
   - `update:clients`
   - `delete:clients`
   - `read:resource_servers`
   - `create:resource_servers`
   - `update:resource_servers`
   - `delete:resource_servers`
   - `read:tenant_settings`
   - `update:tenant_settings`
   - `read:client_grants`
   - `create:client_grants`
   - `update:client_grants`
   - `delete:client_grants`

After that first seed, the repo scripts are the authority.

## Local env contract

Each local `infra/auth0/env/*.env` file must include:

- `AUTH0_DOMAIN`
- `AUTH0_CLIENT_ID`
- `AUTH0_CLIENT_SECRET`
- `AUTH0_ALLOW_DELETE=false`
- `AUTH0_INCLUDED_ONLY=["tenant","resourceServers","clients","clientGrants"]`
- `AUTH0_INPUT_FILE=infra/auth0/tenant/tenant.yaml`
- `AUTH0_KEYWORD_MAPPINGS_FILE=infra/auth0/mappings/<env>.json`

## Reconcile tenant resources from the repo template

Validate the tracked contract first:

```bash
uv run python -m scripts.release.validate_auth0_contract
```

Bootstrap or reconcile the tenant before running Auth0 Deploy CLI:

```bash
uv run python -m scripts.release.bootstrap_auth0_tenant \
  --env-file infra/auth0/env/dev.env \
  --report-path .artifacts/auth0-bootstrap-dev.json
```

This step now reconciles:

- tenant settings
- `Nova API <env>` resource server and all repo-defined scopes
- `Nova API <env>` `token_lifetime_for_web` on both create and update
- `nova-tenant-ops-<env>` M2M client
- `nova-web-<env>` web client
- client grants for:
  - Auth0 Management API
  - the Nova API resource server

Audit the live tenant immediately after bootstrap:

```bash
uv run python -m scripts.release.audit_auth0_tenant \
  --env-file infra/auth0/env/dev.env \
  --report-path .artifacts/auth0-audit-dev.json
```

The audit report is not informational only. The command exits nonzero when the
tenant drifts from the repo template, including a missing or mismatched Nova
API grant for `nova-tenant-ops-<env>`.

## Import tracked tenant-as-code

Run the safe Deploy CLI wrapper:

```bash
uv run python -m scripts.release.run_auth0_deploy_cli import \
  --env-file infra/auth0/env/dev.env \
  --input-file infra/auth0/tenant/tenant.yaml
```

Re-run the audit after import if you changed tracked tenant config:

```bash
uv run python -m scripts.release.audit_auth0_tenant \
  --env-file infra/auth0/env/dev.env \
  --report-path .artifacts/auth0-audit-dev-post-import.json
```

## Export current tenant state (snapshot)

```bash
uv run python -m scripts.release.run_auth0_deploy_cli export \
  --env-file infra/auth0/env/dev.env \
  --output-folder .artifacts/auth0-export/dev
```

Expected behavior:

- `Export Successful` marks a successful run.
- `insufficient_scope` warnings for unrelated tenant features are expected
  because `nova-tenant-ops-<env>` is intentionally limited to Nova-managed
  surfaces rather than full-tenant administration.
- The authoritative success check is that
  `.artifacts/auth0-export/<env>/tenant.yaml` is written.

## Overlay switching

Use the target local overlay file:

- `infra/auth0/env/dev.env` (active)
- `infra/auth0/env/pr.env` (active PR/non-prod overlay)
- `infra/auth0/env/qa.env` (local QA copy if QA is later activated)

```bash
uv run python -m scripts.release.run_auth0_deploy_cli import \
  --env-file infra/auth0/env/pr.env \
  --input-file infra/auth0/tenant/tenant.yaml
```

Do not use the QA overlay until it is explicitly provisioned.

## Safety controls

- `AUTH0_ALLOW_DELETE=false` is mandatory default across overlays.
- Never commit real `AUTH0_CLIENT_SECRET` values to git.
- Keep each `infra/auth0/mappings/*.json` file valid JSON.
- Keep local `infra/auth0/env/*.env` files untracked and gitignored.
- Prefer `--client-secret-env-var`, `--client-secret-stdin`, or
  `--prompt-client-secret` over passing secrets directly on the command line.
- `scripts/release/validate_auth0_contract.py` rejects tracked
  `infra/auth0/env/*.env` files and rejects non-placeholder secrets in
  tracked `*.env.example` files.

## Automated contract check

Run this before each import/export:

```bash
uv run python -m scripts.release.validate_auth0_contract
```

The validator enforces placeholder coverage and the pinned local env contract.
`scripts/release/run_auth0_deploy_cli.py` also re-enforces the same
non-destructive `AUTH0_ALLOW_DELETE` and `AUTH0_INCLUDED_ONLY` runtime
contract before invoking `auth0-deploy-cli`, so hand-edited local overlays
fail closed instead of weakening the import/export boundary.

## GitHub workflow productization

Nova now exposes Auth0 tenant operations as reusable workflow APIs:

- `.github/workflows/reusable-auth0-tenant-deploy.yml` (`workflow_call`)
- `.github/workflows/auth0-tenant-deploy.yml` (thin `workflow_dispatch` wrapper)

Required GitHub Environment secrets for workflow execution:

- Environment `auth0-dev`
  - `AUTH0_DOMAIN`
  - `AUTH0_CLIENT_ID`
  - `AUTH0_CLIENT_SECRET`
- Environment `auth0-pr`
  - `AUTH0_DOMAIN`
  - `AUTH0_CLIENT_ID`
  - `AUTH0_CLIENT_SECRET`
- Environment `auth0-qa`
  - `AUTH0_DOMAIN`
  - `AUTH0_CLIENT_ID`
  - `AUTH0_CLIENT_SECRET`

The reusable workflow sets `environment: auth0-${environment}` and reads the
matching secrets directly. Do not duplicate these as repo-wide secrets.

Contract schemas:

- `docs/contracts/workflow-auth0-tenant-ops-v1.schema.json`
- `docs/contracts/workflow-auth0-tenant-deploy.schema.json`

## Validation checklist

- Workflow `mode` is one of `validate|bootstrap|audit|import|export`.
- Workflow `allow_delete` equals `false`.
- Workflow `input_file` points to `infra/auth0/tenant/tenant.yaml`.
- Workflow `mapping_file` resolves to the expected environment mapping JSON.
- Workflow `bootstrap`/`audit`/`import`/`export` run only when
  `validate_auth0_contract` succeeds.
- Mapping keys cover every `@@KEY@@` token in tenant YAML.
- Domain/client credentials are set from secure local secrets, not committed plaintext.
- `bootstrap_auth0_tenant` report includes both Management API and Nova API
  client grants for the tenant-ops client.
- `audit_auth0_tenant` shows the expected Nova API, expected clients, and live
  tenant-ops client grants before and after import.
