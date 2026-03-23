\name{nova.sdk.r.file}

\alias{nova.sdk.r.file}
\alias{create_nova_file_client}
\alias{nova_file_bearer_token}
\alias{nova_file_metrics_summary}
\alias{nova_file_get_capabilities}
\alias{nova_file_health_live}
\alias{nova_file_health_ready}
\alias{nova_file_list_jobs}
\alias{nova_file_create_job}
\alias{nova_file_get_job_status}
\alias{nova_file_cancel_job}
\alias{nova_file_list_job_events}
\alias{nova_file_retry_job}
\alias{nova_file_get_release_info}
\alias{nova_file_plan_resources}
\alias{nova_file_presign_download}
\alias{nova_file_abort_upload}
\alias{nova_file_complete_upload}
\alias{nova_file_initiate_upload}
\alias{nova_file_introspect_upload}
\alias{nova_file_sign_upload_parts}
\docType{package}
\title{Nova SDK R file client}
\description{Generated R client for the Nova file API.}
\usage{
  create_nova_file_client(base_url, bearer_token = NULL, bearer_token_env = "NOVA_FILE_BEARER_TOKEN", default_headers = NULL, timeout_seconds = 30, user_agent = NULL)
  nova_file_bearer_token(token = NULL, env_var = "NOVA_FILE_BEARER_TOKEN")
}

\arguments{
  \item{base_url}{Base URL for the Nova API, without a trailing slash requirement.}
  \item{bearer_token}{Explicit bearer token used for Authorization headers when request headers do not already provide one.}
  \item{bearer_token_env}{Environment variable name used as an optional bearer-token fallback.}
  \item{default_headers}{Named list of default request headers applied to every request.}
  \item{timeout_seconds}{Positive request timeout in seconds.}
  \item{user_agent}{Optional explicit user agent string.}
  \item{token}{Explicit bearer token string.}
  \item{env_var}{Environment variable name used to resolve a bearer token.}
}

\value{
  The constructor returns a thin client configuration object.
  The bearer-token helper returns an explicit or environment-derived token, or NULL when none is available.
}

\keyword{package}
