test_that("operation catalog exposes public operations", {
  catalog <- nova_file_operation_catalog()
  expect_true(is.list(catalog))
  expect_true("create_job" %in% names(catalog))
  expect_false("update_job_result" %in% names(catalog))
  expect_identical(catalog$create_job$request_content_types, "application/json")
})

test_that("request descriptors resolve paths, query params, and headers", {
  client <- create_nova_file_client("https://nova.example/", request_performer = function(request) {
    list(status = 200L, headers = list(), body = '{"job":{"job_id":"job-0001","status":"running"}}', url = request$url)
  })
  descriptor <- nova_file_request_descriptor(client, "get_job_status", path_params = list(job_id = "job-123"), query = list(limit = 5), headers = list("Idempotency-Key" = "req-123"))
  expect_equal(descriptor$url, "https://nova.example/v1/jobs/job-123")
  expect_equal(descriptor$query$limit, 5)
  expect_equal(descriptor$headers[["Idempotency-Key"]], "req-123")
  expect_true(is.null(descriptor$body))
  expect_equal(descriptor$content_type, NULL)
})

test_that("client methods execute requests and decode success and error envelopes", {
  captured_requests <- list()
  client <- create_nova_file_client("https://nova.example/", request_performer = function(request) {
    captured_requests[[length(captured_requests) + 1L]] <<- request
    list(status = 200L, headers = list(), body = '{"job":{"job_id":"job-0001","status":"pending"}}', url = request$url)
  })
  result <- client$create_job(body = list(job_type = "transfer.process", payload = list(upload_key = "tenant-acme/sample.csv")), headers = list("Authorization" = "Bearer token-123", "Idempotency-Key" = "req-123"))
  expect_true(result$ok)
  expect_equal(result$data$job$job_id, "job-0001")
  expect_equal(captured_requests[[1]]$content_type, "application/json")
  expect_equal(captured_requests[[1]]$headers[["Idempotency-Key"]], "req-123")
  expect_equal(captured_requests[[1]]$headers[["Authorization"]], "Bearer token-123")
  expect_equal(captured_requests[[1]]$body$job_type, "transfer.process")

  failing_client <- create_nova_file_client("https://nova.example/", request_performer = function(request) {
    list(status = 503L, headers = list(), body = '{"error":{"code":"queue_unavailable","message":"jobs queue unavailable","details":{"backend":"sqs"},"request_id":"req-jobs-503"}}', url = request$url)
  })
  error_result <- failing_client$create_job(body = list(job_type = "transfer.process", payload = list(upload_key = "tenant-acme/sample.csv")), headers = list("Authorization" = "Bearer token-123"))
  expect_false(error_result$ok)
  expect_equal(error_result$error$error$code, "queue_unavailable")
})
