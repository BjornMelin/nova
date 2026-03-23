test_that("constructor resolves explicit and environment bearer tokens", {
  withr::local_envvar(NOVA_FILE_BEARER_TOKEN = "env-token-123")
  env_client <- create_nova_file_client("https://nova.example/")
  expect_equal(env_client$bearer_token, "env-token-123")
  explicit_client <- create_nova_file_client("https://nova.example/", bearer_token = "explicit-token-123")
  expect_equal(explicit_client$bearer_token, "explicit-token-123")
})

test_that("constructor treats zero-length bearer tokens as absent", {
  withr::local_envvar(NOVA_FILE_BEARER_TOKEN = NA_character_)
  client <- create_nova_file_client("https://nova.example/", bearer_token = character(0))
  expect_null(client$bearer_token)
})

test_that("generated package exports thin endpoint wrappers", {
  exports <- getNamespaceExports("nova.sdk.r.file")
  expect_true("nova_file_create_job" %in% exports)
  expect_true("nova_file_get_job_status" %in% exports)
  expect_true("nova_file_list_jobs" %in% exports)
  expect_false("nova_file_request_descriptor" %in% exports)
  expect_false("nova_file_execute_operation" %in% exports)
})

test_that("request construction uses concrete params and bearer auth", {
  observed_request <- NULL
  mocked_response <- httr2::response(
    status_code = 200,
    url = "https://nova.example/v1/jobs/job-123",
    headers = list(`content-type` = "application/json"),
    body = charToRaw('{"job_id":"job-123","status":"queued"}')
  )
  withr::local_envvar(NOVA_FILE_BEARER_TOKEN = NA_character_)
  result <- httr2::with_mocked_responses(
    function(req) {
      observed_request <<- req
      mocked_response
    },
    {
      client <- create_nova_file_client("https://nova.example/", bearer_token = "token-123", timeout_seconds = 12)
      nova_file_get_job_status(client, job_id = "job-123", headers = list(`X-Request-Id` = "req-123"))
    }
  )
  expect_equal(result$job_id, "job-123")
  expect_equal(result$status, "queued")
  expect_equal(observed_request$url, "https://nova.example/v1/jobs/job-123")
  expect_equal(observed_request$method, "GET")
  expect_true("Authorization" %in% names(observed_request$headers))
  expect_equal(observed_request$headers$`X-Request-Id`, "req-123")
  expect_equal(observed_request$options$timeout, 12)
})

test_that("lowercase authorization headers suppress bearer injection", {
  observed_request <- NULL
  mocked_response <- httr2::response(
    status_code = 200,
    url = "https://nova.example/v1/jobs/job-123",
    headers = list(`content-type` = "application/json"),
    body = charToRaw('{"job_id":"job-123","status":"queued"}')
  )
  result <- httr2::with_mocked_responses(
    function(req) {
      observed_request <<- req
      mocked_response
    },
    {
      client <- create_nova_file_client("https://nova.example/", bearer_token = "token-123")
      nova_file_get_job_status(client, job_id = "job-123", headers = list(authorization = "Bearer custom"))
    }
  )
  auth_positions <- which(tolower(names(observed_request$headers)) == "authorization")
  expect_length(auth_positions, 1L)
  expect_identical(names(observed_request$headers)[auth_positions[[1L]]], "authorization")
  expect_equal(result$job_id, "job-123")
})

test_that("request construction encodes query params and JSON bodies", {
  observed_requests <- list()
  mocked_response <- httr2::response(
    status_code = 200,
    url = "https://nova.example/v1/jobs",
    headers = list(`content-type` = "application/json"),
    body = charToRaw('{"items":[]}')
  )
  httr2::with_mocked_responses(
    function(req) {
      observed_requests[[length(observed_requests) + 1L]] <<- req
      mocked_response
    },
    {
      client <- create_nova_file_client("https://nova.example/", bearer_token = "token-123")
      nova_file_list_jobs(client, limit = 25)
      nova_file_create_job(
        client,
        body = list(
          job_type = "transfer.process",
          payload = list(upload_key = "tenant-acme/sample.csv")
        ),
        headers = list("Idempotency-Key" = "req-123")
      )
    }
  )
  expect_length(observed_requests, 2L)
  expect_equal(observed_requests[[1]]$method, "GET")
  expect_equal(observed_requests[[1]]$url, "https://nova.example/v1/jobs?limit=25")
  expect_equal(observed_requests[[2]]$method, "POST")
  expect_equal(observed_requests[[2]]$url, "https://nova.example/v1/jobs")
  expect_equal(observed_requests[[2]]$headers$`Idempotency-Key`, "req-123")
  expect_equal(observed_requests[[2]]$body$content_type, "application/json")
  expect_equal(observed_requests[[2]]$body$data$job_type, "transfer.process")
  expect_equal(observed_requests[[2]]$body$data$payload$upload_key, "tenant-acme/sample.csv")
})

test_that("structured errors preserve Nova error envelope fields", {
  mocked_response <- httr2::response(
    status_code = 503,
    url = "https://nova.example/v1/jobs",
    headers = list(`content-type` = "application/json"),
    body = charToRaw('{"error":{"code":"queue_unavailable","message":"jobs queue unavailable","request_id":"req-jobs-503","details":{"backend":"sqs"}}}')
  )
  error <- tryCatch(
    httr2::with_mocked_responses(
      function(req) mocked_response,
      {
        client <- create_nova_file_client("https://nova.example/", bearer_token = "token-123")
        nova_file_create_job(client, body = list(job_type = "transfer.process"))
      }
    ),
    nova_file_api_error = function(error) error
  )
  expect_s3_class(error, "nova_file_api_error")
  expect_equal(error$code, "queue_unavailable")
  expect_equal(error$status, 503L)
  expect_equal(error$request_id, "req-jobs-503")
  expect_equal(error$details$backend, "sqs")
  expect_equal(conditionMessage(error), "[queue_unavailable] jobs queue unavailable")
})
