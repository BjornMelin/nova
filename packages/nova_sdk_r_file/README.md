# `nova.sdk.r.file`

Generated R client for the Nova file API.

This package is generated from committed OpenAPI and is kept in-repo so
Nova release tooling can build and check the real package tree.

## Surface

- `create_nova_file_client`
- `nova_file_operation_catalog`
- `nova_file_request_descriptor`
- `nova_file_execute_operation`
- `nova_file_decode_error_envelope`

## Example

```r
client <- create_nova_file_client(
  "https://nova.example/",
  default_headers = list(
    "Authorization" = "Bearer eyJhbGciOi...",
    "Idempotency-Key" = "req-123"
  )
)

result <- client$create_job(
  body = list(
    job_type = "transfer.process",
    payload = list(upload_key = "tenant-acme/sample.csv")
  )
)
result$data$job_id
result$data$status
```
