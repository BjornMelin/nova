# contracts

OpenAPI artifacts, canonical fixtures, and schema utilities for Nova runtime
services.

Start with `docs/contracts/README.md` for the active contract authority set and
`docs/overview/ACTIVE-DOCS-INDEX.md` for the current docs router. This package
README is a package-local orientation note, not the operator authority surface.

## OpenAPI artifacts

- Full runtime export:
  `packages/contracts/openapi/nova-file-api.openapi.json`
- Reduced public SDK artifact:
  `packages/contracts/openapi/nova-file-api.public.openapi.json`

The reduced public artifact is the committed SDK-generation source of truth for
TypeScript, Python, and R. The full runtime export remains the runtime/API
contract authority.

## Canonical contract fixtures

- Path: `packages/contracts/fixtures/v1`
- Coverage: auth verify, transfer initiate, canonical `/v1/exports` and `/v1/capabilities` routes, canonical error envelope
- Consumer guidance: `packages/contracts/fixtures/v1/README.md`

Contract verification includes generated-client smoke coverage:

```bash
uv run pytest -q packages/nova_file_api/tests/test_generated_client_smoke.py
```
