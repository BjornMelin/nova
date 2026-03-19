test_that("operation catalog exposes multi-media operations", {
  catalog <- nova_auth_operation_catalog()
  expect_true(is.list(catalog))
  expect_true("introspect_token" %in% names(catalog))
  expect_identical(catalog$verify_token$request_content_types, "application/json")
  expect_identical(catalog$introspect_token$request_content_types, c("application/json", "application/x-www-form-urlencoded"))
})

test_that("request descriptors require explicit content types for multi-media bodies", {
  client <- create_nova_auth_client("https://nova.example/", request_performer = function(request) {
    list(status = 200L, headers = list(), body = '{"principal":{"subject":"auth0|user-123","scope_id":"tenant-acme","tenant_id":"tenant-acme","scopes":["files:write","jobs:enqueue"],"permissions":["jobs:enqueue","jobs:read"]},"claims":{"iss":"https://example.us.auth0.com/","aud":"nova-file-api","sub":"auth0|user-123","exp":1999999999,"iat":1999999000,"scope":"files:write jobs:enqueue"}}', url = request$url)
  })
  expect_error(
    nova_auth_request_descriptor(client, "introspect_token", body = list(access_token = "token-123", required_scopes = c("files:write"), required_permissions = character(0))),
    "requires an explicit content_type"
  )
  json_descriptor <- nova_auth_request_descriptor(client, "introspect_token", body = list(access_token = "token-123", required_scopes = c("files:write"), required_permissions = character(0)), content_type = "application/json")
  expect_equal(json_descriptor$content_type, "application/json")
  form_descriptor <- nova_auth_request_descriptor(client, "introspect_token", body = list(token = "token-123", required_scopes = c("files:write"), required_permissions = character(0)), content_type = "application/x-www-form-urlencoded")
  expect_equal(form_descriptor$content_type, "application/x-www-form-urlencoded")
  expect_equal(form_descriptor$body$token, "token-123")
})

test_that("client methods execute requests and decode success and error envelopes", {
  captured_requests <- list()
  client <- create_nova_auth_client("https://nova.example/", request_performer = function(request) {
    captured_requests[[length(captured_requests) + 1L]] <<- request
    list(status = 200L, headers = list(), body = '{"principal":{"subject":"auth0|user-123","scope_id":"tenant-acme","tenant_id":"tenant-acme","scopes":["files:write","jobs:enqueue"],"permissions":["jobs:enqueue","jobs:read"]},"claims":{"iss":"https://example.us.auth0.com/","aud":"nova-file-api","sub":"auth0|user-123","exp":1999999999,"iat":1999999000,"scope":"files:write jobs:enqueue"}}', url = request$url)
  })
  result <- client$verify_token(body = list(access_token = "token-123", required_scopes = c("files:write"), required_permissions = character(0)))
  expect_true(result$ok)
  expect_equal(result$data$principal$subject, "auth0|user-123")
  expect_equal(captured_requests[[1]]$body$access_token, "token-123")

  failing_client <- create_nova_auth_client("https://nova.example/", request_performer = function(request) {
    list(status = 401L, headers = list(), body = '{"error":{"code":"invalid_token","message":"token validation failed","details":{},"request_id":"req-auth-401"}}', url = request$url)
  })
  error_result <- failing_client$verify_token(body = list(access_token = "token-123", required_scopes = character(0), required_permissions = character(0)))
  expect_false(error_result$ok)
  expect_equal(error_result$error$error$code, "invalid_token")
})
