# `nova.sdk.r.file`

Generated R client for the Nova file API.

This package is generated from committed OpenAPI and is kept in-repo so
Nova release tooling can build and check the real package tree.
The generated client is intentionally thin and follows the current
public Nova file API contract: bearer JWT auth, JSON bodies,
concrete path/query parameters, and plain R list responses.

## Surface

- `create_nova_file_client`
- `nova_file_bearer_token`
- endpoint wrappers named `nova_file_<operation_id>`

## Example

```r
client <- create_nova_file_client(
  "https://nova.example/",
  bearer_token = "eyJhbGciOi...",
)

result <- nova_file_create_export(
  client,
  body = list(
    source_key = "uploads/scope-1/source.csv",
    filename = "source.csv"
  ),
  headers = list("Idempotency-Key" = "req-123")
)
result$export_id
result$status

exports <- nova_file_list_exports(client, limit = 25)
export <- nova_file_get_export(client, export_id = result$export_id)
```
