# Auth0 tenant-as-code

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
- `AUTH0_INCLUDED_ONLY=["tenant","resourceServers","clients","clientGrants"]`

This protects against destructive deletes during import unless explicitly changed for a controlled migration event.

Local persisted tenant credentials:

- `infra/auth0/env/dev.env`
- `infra/auth0/env/pr.env`
- `infra/auth0/env/qa.env`

These files are gitignored by repo policy. Use the helper script below to write
or update them with restrictive local file permissions. Do not commit them and
do not export them into long-lived shell profiles.

## Environment overlays

Current operating mode:

- **dev (active):** use `env/dev.env` for the shared development tenant.
- **pr (active):** use `env/pr.env` for the shared PR/non-prod tenant.
- **qa (scaffold):** `qa.env.example` remains a placeholder until a QA tenant
  is approved.

Both active overlays are intentionally kept as local, untracked env files under
`infra/auth0/env/`.

## One-time bootstrap boundary

Auth0 has one unavoidable seed step: the `nova-tenant-ops-<env>` M2M client
must already be authorized for the **Auth0 Management API** before it can use
its own credentials to reconcile the tenant. After that one-time grant exists,
all steady-state Nova tenant changes are handled by the repo scripts below.

## How keyword replacement works

`tenant/tenant.yaml` uses placeholder tokens (for example `@@WEB_CALLBACK_URL@@`).
At runtime, the wrappers read `AUTH0_KEYWORD_MAPPINGS_FILE`, render the shared
template, and invoke `auth0-deploy-cli` with the resolved mapping payload. The
deploy wrapper also enforces the pinned `AUTH0_ALLOW_DELETE=false` and
`AUTH0_INCLUDED_ONLY=["tenant","resourceServers","clients","clientGrants"]`
contract so import/export stays scoped to Nova-managed tenant surfaces only
even for hand-edited local overlays.

See runbook: `docs/runbooks/release/auth0-a0deploy-runbook.md`.

## Reproducible local commands

Persist one local tenant env file without putting the client secret in shell
history:

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

Validate the tracked template and examples first:

```bash
uv run python -m scripts.release.validate_auth0_contract
```

Bootstrap or reconcile a tenant from the repo template. This now ensures:

- tenant settings
- the Nova API resource server and all defined scopes
- the Nova API `token_lifetime_for_web` value for both create and update paths
- the `nova-tenant-ops-<env>` and `nova-web-<env>` clients
- the tenant-ops client grants for both Auth0 Management API and the Nova API

```bash
uv run python -m scripts.release.bootstrap_auth0_tenant \
  --env-file infra/auth0/env/dev.env \
  --report-path .artifacts/auth0-bootstrap-dev.json
```

Audit the live tenant against the repo template:

```bash
uv run python -m scripts.release.audit_auth0_tenant \
  --env-file infra/auth0/env/dev.env \
  --report-path .artifacts/auth0-audit-dev.json
```

The audit is a drift gate. It writes the JSON report and exits nonzero when the
tenant is missing the Nova API resource server, expected clients, or the
tenant-ops Nova API grant, or when any of those surfaces differ from the repo
template.

Run the Auth0 Deploy CLI safely for import:

```bash
uv run python -m scripts.release.run_auth0_deploy_cli import \
  --env-file infra/auth0/env/dev.env \
  --input-file infra/auth0/tenant/tenant.yaml
```

Run the Auth0 Deploy CLI safely for export:

```bash
uv run python -m scripts.release.run_auth0_deploy_cli export \
  --env-file infra/auth0/env/dev.env \
  --output-folder .artifacts/auth0-export/dev
```

The wrapper runs export from a temporary working directory so `auth0-deploy-cli`
cannot overwrite tracked repo files.

GitHub Actions uses environment-scoped secrets rather than repo-wide Auth0
secrets. Configure:

- `auth0-dev`
- `auth0-pr`
- `auth0-qa`

Each environment must provide:

- `AUTH0_DOMAIN`
- `AUTH0_CLIENT_ID`
- `AUTH0_CLIENT_SECRET`

Auth0 export may emit `insufficient_scope` warnings for unrelated tenant
features such as connections, guardian, branding, or actions. That is expected
with the intentionally narrow `nova-tenant-ops-<env>` Management API grant.
Treat the export as successful when `Export Successful` is printed and the
expected `.artifacts/auth0-export/<env>/tenant.yaml` file is written.
