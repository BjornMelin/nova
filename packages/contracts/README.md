# contracts

OpenAPI artifacts, canonical fixtures, and schema utilities for Nova runtime services.

## Canonical contract fixtures

- Path: `packages/contracts/fixtures/v1`
- Coverage: auth verify, transfer initiate, canonical `/v1/*` jobs/capabilities, canonical error envelope
- Consumer guidance: `packages/contracts/fixtures/v1/README.md`

Contract verification includes generated-client smoke coverage:

```bash
source .venv/bin/activate && \
uv run pytest -q \
  packages/nova_file_api/tests/test_generated_client_smoke.py
```
