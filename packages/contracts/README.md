# contracts

OpenAPI artifacts and schema utilities for nova runtime services.

Contract verification includes generated-client smoke coverage:

```bash
source .venv/bin/activate && \
uv run pytest -q \
  packages/nova_file_api/tests/test_generated_client_smoke.py
```
