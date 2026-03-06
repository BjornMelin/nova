# contracts

OpenAPI artifacts, canonical fixtures, and schema utilities for Nova runtime services.

## Canonical OpenAPI artifacts

Committed service contracts live under `packages/contracts/openapi/`:

- `packages/contracts/openapi/nova-file-api.openapi.json`
- `packages/contracts/openapi/nova-auth-api.openapi.json`

These files are the canonical generation source for internal TypeScript/R
catalogs and the committed public Python SDK package trees.

## Canonical contract fixtures

- Path: `packages/contracts/fixtures/v1`
- Coverage: auth verify, transfer initiate, canonical `/v1/*` jobs/capabilities, canonical error envelope
- Consumer guidance: `packages/contracts/fixtures/v1/README.md`

## Export and drift-check workflow

Refresh or verify the committed contract surface from repository root:

```bash
source .venv/bin/activate && uv run python scripts/contracts/export_openapi.py --check
source .venv/bin/activate && uv run python scripts/release/generate_clients.py --check
source .venv/bin/activate && uv run python scripts/release/generate_python_clients.py --check
```

`generate_clients.py` governs the internal TypeScript and R catalogs.
`generate_python_clients.py` governs the committed Python SDK trees under
`packages/nova_sdk_py_file` and `packages/nova_sdk_py_auth`.

Contract verification also includes generated-client smoke coverage for both
canonical OpenAPI artifacts:

```bash
source .venv/bin/activate && \
uv run pytest -q \
  packages/nova_file_api/tests/test_generated_client_smoke.py
```
