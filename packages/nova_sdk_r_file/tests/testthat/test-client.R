test_that("constructor resolves explicit and environment bearer tokens", {
  Sys.setenv(NOVA_FILE_BEARER_TOKEN = "env-token-123")
  env_client <- create_nova_file_client("https://nova.example/")
  expect_equal(env_client$bearer_token, "env-token-123")
  explicit_client <- create_nova_file_client("https://nova.example/", bearer_token = "explicit-token-123")
  expect_equal(explicit_client$bearer_token, "explicit-token-123")
  Sys.unsetenv("NOVA_FILE_BEARER_TOKEN")
})

test_that("generated package exports thin endpoint wrappers", {
  exports <- getNamespaceExports("nova.sdk.r.file")
  expect_true("nova_file_create_job" %in% exports)
  expect_true("nova_file_get_job_status" %in% exports)
  expect_false("nova_file_request_descriptor" %in% exports)
  expect_false("nova_file_execute_operation" %in% exports)
})

test_that("structured errors preserve Nova error envelope fields", {
  client <- create_nova_file_client("https://nova.example/", bearer_token = "token-123")
  error <- tryCatch(
    stop(
      structure(
        list(
          message = "jobs queue unavailable",
          call = NULL,
          code = "queue_unavailable",
          status = 503L,
          request_id = "req-jobs-503",
          details = list(backend = "sqs"),
          operation_id = "create_job",
          method = "POST",
          path = "/v1/jobs"
        ),
        class = c("nova_file_api_error", "error", "condition")
      )
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
