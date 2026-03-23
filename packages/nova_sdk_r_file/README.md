# `nova.sdk.r.file`

Generated R client for the Nova file API.

This package is generated from committed OpenAPI and is kept in-repo so
Nova release tooling can build and check the real package tree.

## Surface

- `create_nova_file_client`
- `nova_file_bearer_token`
- endpoint wrappers named `nova_file_<operation_id>`

## Example

```r
client <- create_nova_file_client(
  "https://nova.example/",
  bearer_token = "eyJhbGciOi...",
  default_headers = list(
    "Idempotency-Key" = "req-123"
  )
)

result <- nova_file_create_job(
  client,
  body = list(
    job_type = "transfer.process",
    payload = list(upload_key = "tenant-acme/sample.csv")
  )
)
result$job_id
result$status
```
