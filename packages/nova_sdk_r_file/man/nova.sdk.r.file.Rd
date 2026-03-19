\name{nova.sdk.r.file}

\alias{nova.sdk.r.file}
\alias{create_nova_file_client}
\alias{nova_file_operation_catalog}
\alias{nova_file_request_descriptor}
\alias{nova_file_execute_operation}
\alias{nova_file_decode_error_envelope}
\docType{package}
\title{Nova SDK R file client}
\description{Generated R client for the Nova file API.}
\usage{
  create_nova_file_client(base_url, request_performer = nova_file_default_request_performer, default_headers = NULL, timeout_seconds = 30)
  nova_file_operation_catalog()
  nova_file_request_descriptor(client, operation_id, body = NULL, path_params = NULL, query = NULL, headers = NULL, content_type = NULL)
  nova_file_execute_operation(client, operation_id, body = NULL, path_params = NULL, query = NULL, headers = NULL, content_type = NULL)
  nova_file_decode_error_envelope(body, status = NULL)
}

\arguments{
  \item{base_url}{Base URL for the Nova API, without a trailing slash requirement.}
  \item{request_performer}{Function used to execute a prepared request descriptor.}
  \item{default_headers}{Named list of default request headers applied to every request.}
  \item{timeout_seconds}{Positive request timeout in seconds.}
  \item{client}{Client instance created by the package constructor.}
  \item{operation_id}{Stable Nova operation identifier from the operation catalog.}
  \item{body}{Optional request body payload for operations that accept one.}
  \item{path_params}{Named list of path parameter values used to resolve templated routes.}
  \item{query}{Named list of query-string parameters.}
  \item{headers}{Named list of per-request headers merged over default headers.}
  \item{content_type}{Explicit request media type for multi-media operations.}
  \item{status}{Optional HTTP status code used when decoding an error envelope.}
}

\value{
  The constructor returns a client object with bound operation methods.
  The request descriptor returns a structured request list.
  The executor returns a structured response list with parsed data or error envelopes.
}

\keyword{package}
