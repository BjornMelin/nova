# `nova.sdk.r.auth`

Generated R client for the Nova auth API.

This package is generated from committed OpenAPI and is kept in-repo so
Nova release tooling can build and check the real package tree.

## Surface

- `create_nova_auth_client`
- `nova_auth_operation_catalog`
- `nova_auth_request_descriptor`
- `nova_auth_execute_operation`
- `nova_auth_decode_error_envelope`

## Example

```r
client <- create_nova_auth_client("https://nova.example/")

result <- client$verify_token(
  body = list(
    access_token = "token-123",
    required_scopes = c("files:write"),
    required_permissions = character(0)
  )
)
result$data$principal$subject
```
