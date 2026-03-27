test_that("constructor resolves explicit and environment bearer tokens", {
  withr::local_envvar(NOVA_BEARER_TOKEN = "env-token-123")
  env_client <- create_nova_client("https://nova.example/")
  expect_equal(env_client$bearer_token, "env-token-123")
  explicit_client <- create_nova_client("https://nova.example/", bearer_token = "explicit-token-123")
  expect_equal(explicit_client$bearer_token, "explicit-token-123")
})

test_that("constructor treats zero-length bearer tokens as absent", {
  withr::local_envvar(NOVA_BEARER_TOKEN = NA_character_)
  client <- create_nova_client("https://nova.example/", bearer_token = character(0))
  expect_null(client$bearer_token)
})

test_that("constructor rejects unusable base URLs after trimming", {
  expect_error(create_nova_client("/"), "base_url must remain usable after trimming trailing slashes", fixed = TRUE)
})

test_that("constructor normalizes invalid user agents to the default", {
  client <- create_nova_client("https://nova.example/", user_agent = character(0))
  expect_equal(client$user_agent, nova_default_user_agent())
  client_na <- create_nova_client("https://nova.example/", user_agent = NA_character_)
  expect_equal(client_na$user_agent, nova_default_user_agent())
})

test_that("generated package exports thin endpoint wrappers", {
  exports <- getNamespaceExports("nova")
  expect_true("nova_create_export" %in% exports)
  expect_true("nova_get_export" %in% exports)
  expect_true("nova_list_exports" %in% exports)
  expect_true("nova_cancel_export" %in% exports)
  expect_false("nova_request_descriptor" %in% exports)
  expect_false("nova_execute_operation" %in% exports)
})

test_that("request construction uses concrete params and bearer auth", {
  observed_request <- NULL
  mocked_response <- httr2::response(
    status_code = 200,
    url = "https://nova.example/v1/exports/export-123",
    headers = list(`content-type` = "application/json"),
    body = charToRaw('{"export_id":"export-123","source_key":"uploads/scope-1/source.csv","filename":"source.csv","status":"queued","output":null,"error":null,"created_at":"2026-03-25T00:00:00Z","updated_at":"2026-03-25T00:00:00Z"}')
  )
  withr::local_envvar(NOVA_BEARER_TOKEN = NA_character_)
  result <- httr2::with_mocked_responses(
    function(req) {
      observed_request <<- req
      mocked_response
    },
    {
      client <- create_nova_client("https://nova.example/", bearer_token = "token-123", timeout_seconds = 12)
      nova_get_export(client, export_id = "export-123", headers = list(`X-Request-Id` = "req-123"))
    }
  )
  expect_equal(result$export_id, "export-123")
  expect_equal(result$status, "queued")
  expect_equal(observed_request$url, "https://nova.example/v1/exports/export-123")
  expect_equal(observed_request$method, "GET")
  expect_true("Authorization" %in% names(observed_request$headers))
  expect_equal(observed_request$headers$`X-Request-Id`, "req-123")
  expect_equal(observed_request$options$timeout, 12)
})

test_that("lowercase authorization headers suppress bearer injection", {
  observed_request <- NULL
  mocked_response <- httr2::response(
    status_code = 200,
    url = "https://nova.example/v1/exports/export-123",
    headers = list(`content-type` = "application/json"),
    body = charToRaw('{"export_id":"export-123","source_key":"uploads/scope-1/source.csv","filename":"source.csv","status":"queued","output":null,"error":null,"created_at":"2026-03-25T00:00:00Z","updated_at":"2026-03-25T00:00:00Z"}')
  )
  result <- httr2::with_mocked_responses(
    function(req) {
      observed_request <<- req
      mocked_response
    },
    {
      client <- create_nova_client("https://nova.example/", bearer_token = "token-123")
      nova_get_export(client, export_id = "export-123", headers = list(authorization = "Bearer custom"))
    }
  )
  auth_positions <- which(tolower(names(observed_request$headers)) == "authorization")
  expect_length(auth_positions, 1L)
  expect_identical(names(observed_request$headers)[auth_positions[[1L]]], "authorization")
  expect_equal(result$export_id, "export-123")
})

test_that("request construction encodes query params and JSON bodies", {
  observed_requests <- list()
  mocked_response <- httr2::response(
    status_code = 200,
    url = "https://nova.example/v1/exports",
    headers = list(`content-type` = "application/json"),
    body = charToRaw('{"exports":[]}')
  )
  httr2::with_mocked_responses(
    function(req) {
      observed_requests[[length(observed_requests) + 1L]] <<- req
      mocked_response
    },
    {
      client <- create_nova_client("https://nova.example/", bearer_token = "token-123")
      nova_list_exports(client, limit = 25)
      nova_create_export(
        client,
        body = list(
          source_key = "uploads/scope-1/source.csv",
          filename = "source.csv"
        ),
        headers = list("Idempotency-Key" = "req-123")
      )
    }
  )
  expect_length(observed_requests, 2L)
  expect_equal(observed_requests[[1]]$method, "GET")
  expect_equal(observed_requests[[1]]$url, "https://nova.example/v1/exports?limit=25")
  expect_equal(observed_requests[[2]]$method, "POST")
  expect_equal(observed_requests[[2]]$url, "https://nova.example/v1/exports")
  expect_equal(observed_requests[[2]]$headers$`Idempotency-Key`, "req-123")
  expect_equal(observed_requests[[2]]$body$content_type, "application/json")
  expect_equal(observed_requests[[2]]$body$data$source_key, "uploads/scope-1/source.csv")
  expect_equal(observed_requests[[2]]$body$data$filename, "source.csv")
})

test_that("structured errors preserve Nova error envelope fields", {
  mocked_response <- httr2::response(
    status_code = 503,
    url = "https://nova.example/v1/exports",
    headers = list(`content-type` = "application/json"),
    body = charToRaw('{"error":{"code":"queue_unavailable","message":"export creation failed because queue publish failed","request_id":"req-exports-503","details":{"backend":"sqs"}}}')
  )
  error <- tryCatch(
    httr2::with_mocked_responses(
      function(req) mocked_response,
      {
        client <- create_nova_client("https://nova.example/", bearer_token = "token-123")
        nova_create_export(client, body = list(source_key = "uploads/scope-1/source.csv", filename = "source.csv"))
      }
    ),
    nova_api_error = function(error) error
  )
  expect_s3_class(error, "nova_api_error")
  expect_true(inherits(error, "httr2_http"))
  expect_equal(error$code, "queue_unavailable")
  expect_equal(error$status, 503L)
  expect_equal(error$request_id, "req-exports-503")
  expect_equal(error$details$backend, "sqs")
  expect_equal(httr2::resp_status(error$resp), 503L)
  expect_equal(conditionMessage(error), "[queue_unavailable] export creation failed because queue publish failed")
})

test_that("structured errors fall back when code or message is missing", {
  mocked_response <- httr2::response(
    status_code = 503,
    url = "https://nova.example/v1/exports",
    headers = list(`content-type` = "application/json"),
    body = charToRaw('{"error":{"details":{"backend":"sqs"}}}')
  )
  error <- tryCatch(
    httr2::with_mocked_responses(
      function(req) mocked_response,
      {
        client <- create_nova_client("https://nova.example/", bearer_token = "token-123")
        nova_create_export(client, body = list(source_key = "uploads/scope-1/source.csv", filename = "source.csv"))
      }
    ),
    nova_api_error = function(error) error
  )
  expect_s3_class(error, "nova_api_error")
  expect_equal(error$code, "http_503")
  expect_match(conditionMessage(error), "http_503", fixed = TRUE)
})

test_that("structured errors fall back to raw body text for non-JSON responses", {
  mocked_response <- httr2::response(
    status_code = 503,
    url = "https://nova.example/v1/exports",
    headers = list(`content-type` = "text/plain"),
    body = charToRaw("service unavailable")
  )
  error <- tryCatch(
    httr2::with_mocked_responses(
      function(req) mocked_response,
      {
        client <- create_nova_client("https://nova.example/", bearer_token = "token-123")
        nova_create_export(client, body = list(source_key = "uploads/scope-1/source.csv", filename = "source.csv"))
      }
    ),
    nova_api_error = function(error) error
  )
  expect_s3_class(error, "nova_api_error")
  expect_true(inherits(error, "httr2_http"))
  expect_equal(error$code, "http_503")
  expect_match(conditionMessage(error), "service unavailable", fixed = TRUE)
  expect_equal(httr2::resp_status(error$resp), 503L)
})
