# `nova`

Thin httr2 client for the Nova public API.

This package is generated from the committed reduced public OpenAPI artifact at
`packages/contracts/openapi/nova-file-api.public.openapi.json` and is kept
in-repo so Nova release tooling can build and check the real package tree.
The generated client is intentionally thin and follows the current
public Nova API contract: bearer JWT auth, JSON bodies, concrete
path/query parameters, and plain R list responses.

## Surface

- `create_nova_client`
- `nova_bearer_token`
- endpoint wrappers named `nova_<operation_id>`

## Example

```r
client <- create_nova_client(
  "https://nova.example/",
  bearer_token = "eyJhbGciOi…",
)

result <- nova_create_export(
  client,
  body = list(
    source_key = "uploads/scope-1/source.csv",
    filename = "source.csv"
  ),
  headers = list("Idempotency-Key" = "req-123")
)
result$export_id
result$status

exports <- nova_list_exports(client, limit = 25)
export <- nova_get_export(client, export_id = result$export_id)
```

## Generation contract

- Source OpenAPI artifact:
  `packages/contracts/openapi/nova-file-api.public.openapi.json`
- Thin CLI entrypoint:
  `scripts/release/generate_clients.py`
- R lane implementation:
  `scripts/release/r_sdk.py`
