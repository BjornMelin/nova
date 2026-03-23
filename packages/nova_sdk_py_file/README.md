# nova-sdk-py-file

Generated Python core SDK for the Nova file API OpenAPI contract.

## Build

```bash
source .venv/bin/activate && uv build packages/nova_sdk_py_file
```

## Usage

Use `Client` for unauthenticated endpoints and `AuthenticatedClient` for the
bearer-authenticated public API surface.

```python
from nova_sdk_py_file import AuthenticatedClient
from nova_sdk_py_file.api.transfers import initiate_upload
from nova_sdk_py_file.models import InitiateUploadRequest

client = AuthenticatedClient(
    base_url="https://nova.example.com",
    token="<bearer-jwt>",
)

payload = InitiateUploadRequest(
    filename="report.csv",
    size_bytes=128,
)

with client as api_client:
    response = initiate_upload.sync(client=api_client, body=payload)
```

## Generation contract

- Source OpenAPI artifact:
  `packages/contracts/openapi/nova-file-api.openapi.json`
- Generator entrypoint:
  `scripts/release/generate_python_clients.py`
- Generator pin:
  `openapi-python-client==0.28.3`
- Generator assets:
  `scripts/release/openapi_python_client/config.yaml` and
  `scripts/release/openapi_python_client/templates/`

The generated module tree under `src/nova_sdk_py_file/` is deterministic and
rechecked in CI with `uv run python scripts/release/generate_python_clients.py --check`.

Detailed responses preserve raw integer HTTP status codes, including
valid proxy or gateway codes outside the IANA enum range. The canonical
generated helper model name for job results is `JobRecordResultDetails`.
