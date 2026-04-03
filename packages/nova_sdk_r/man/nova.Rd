\name{nova}

\alias{nova}
\alias{create_nova_client}
\alias{nova_bearer_token}
\alias{nova_metrics_summary}
\alias{nova_get_capabilities}
\alias{nova_get_transfer_capabilities}
\alias{nova_list_exports}
\alias{nova_create_export}
\alias{nova_get_export}
\alias{nova_cancel_export}
\alias{nova_health_live}
\alias{nova_health_ready}
\alias{nova_get_release_info}
\alias{nova_plan_resources}
\alias{nova_presign_download}
\alias{nova_abort_upload}
\alias{nova_complete_upload}
\alias{nova_initiate_upload}
\alias{nova_introspect_upload}
\alias{nova_sign_upload_parts}
\docType{package}
\title{Nova R client}
\description{Thin httr2 client for the Nova public API.}
\usage{
  create_nova_client(base_url, bearer_token = NULL, bearer_token_env = "NOVA_BEARER_TOKEN", default_headers = NULL, timeout_seconds = 30, user_agent = NULL)
  nova_bearer_token(token = NULL, env_var = "NOVA_BEARER_TOKEN")
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

\section{nova_metrics_summary}{
  \code{nova_metrics_summary(client, headers = NULL)}

  Metrics Summary

  \describe{
    \item{client}{Thin client created by \code{create_nova_client()}.}
    \item{headers}{Optional named list of per-request headers.}
    \item{Returns}{Parsed JSON response as a named list, or NULL when the response body is empty.}
  }
}

\section{nova_get_capabilities}{
  \code{nova_get_capabilities(client, headers = NULL)}

  Get Capabilities

  \describe{
    \item{client}{Thin client created by \code{create_nova_client()}.}
    \item{headers}{Optional named list of per-request headers.}
    \item{Returns}{Parsed JSON response as a named list, or NULL when the response body is empty.}
  }
}

\section{nova_get_transfer_capabilities}{
  \code{nova_get_transfer_capabilities(client, headers = NULL)}

  Get Transfer Capabilities

  \describe{
    \item{client}{Thin client created by \code{create_nova_client()}.}
    \item{headers}{Optional named list of per-request headers.}
    \item{Returns}{Parsed JSON response as a named list, or NULL when the response body is empty.}
  }
}

\section{nova_list_exports}{
  \code{nova_list_exports(client, limit = NULL, headers = NULL)}

  List Exports

  \describe{
    \item{client}{Thin client created by \code{create_nova_client()}.}
    \item{limit}{Optional query parameter \code{limit}.}
    \item{headers}{Optional named list of per-request headers.}
    \item{Returns}{Parsed JSON response as a named list, or NULL when the response body is empty.}
  }
}

\section{nova_create_export}{
  \code{nova_create_export(client, body, headers = NULL)}

  Create Export

  \describe{
    \item{client}{Thin client created by \code{create_nova_client()}.}
    \item{body}{Request payload for this operation, encoded as JSON.}
    \item{headers}{Optional named list of per-request headers.}
    \item{Returns}{Parsed JSON response as a named list, or NULL when the response body is empty.}
  }
}

\section{nova_get_export}{
  \code{nova_get_export(client, export_id, headers = NULL)}

  Get Export

  \describe{
    \item{client}{Thin client created by \code{create_nova_client()}.}
    \item{export_id}{Path parameter \code{export_id}.}
    \item{headers}{Optional named list of per-request headers.}
    \item{Returns}{Parsed JSON response as a named list, or NULL when the response body is empty.}
  }
}

\section{nova_cancel_export}{
  \code{nova_cancel_export(client, export_id, headers = NULL)}

  Cancel Export

  \describe{
    \item{client}{Thin client created by \code{create_nova_client()}.}
    \item{export_id}{Path parameter \code{export_id}.}
    \item{headers}{Optional named list of per-request headers.}
    \item{Returns}{Parsed JSON response as a named list, or NULL when the response body is empty.}
  }
}

\section{nova_health_live}{
  \code{nova_health_live(client, headers = NULL)}

  Health Live

  \describe{
    \item{client}{Thin client created by \code{create_nova_client()}.}
    \item{headers}{Optional named list of per-request headers.}
    \item{Returns}{Parsed JSON response as a named list, or NULL when the response body is empty.}
  }
}

\section{nova_health_ready}{
  \code{nova_health_ready(client, headers = NULL)}

  Health Ready

  \describe{
    \item{client}{Thin client created by \code{create_nova_client()}.}
    \item{headers}{Optional named list of per-request headers.}
    \item{Returns}{Parsed JSON response as a named list, or NULL when the response body is empty.}
  }
}

\section{nova_get_release_info}{
  \code{nova_get_release_info(client, headers = NULL)}

  Get Release Info

  \describe{
    \item{client}{Thin client created by \code{create_nova_client()}.}
    \item{headers}{Optional named list of per-request headers.}
    \item{Returns}{Parsed JSON response as a named list, or NULL when the response body is empty.}
  }
}

\section{nova_plan_resources}{
  \code{nova_plan_resources(client, body, headers = NULL)}

  Plan Resources

  \describe{
    \item{client}{Thin client created by \code{create_nova_client()}.}
    \item{body}{Request payload for this operation, encoded as JSON.}
    \item{headers}{Optional named list of per-request headers.}
    \item{Returns}{Parsed JSON response as a named list, or NULL when the response body is empty.}
  }
}

\section{nova_presign_download}{
  \code{nova_presign_download(client, body, headers = NULL)}

  Presign Download

  \describe{
    \item{client}{Thin client created by \code{create_nova_client()}.}
    \item{body}{Request payload for this operation, encoded as JSON.}
    \item{headers}{Optional named list of per-request headers.}
    \item{Returns}{Parsed JSON response as a named list, or NULL when the response body is empty.}
  }
}

\section{nova_abort_upload}{
  \code{nova_abort_upload(client, body, headers = NULL)}

  Abort Upload

  \describe{
    \item{client}{Thin client created by \code{create_nova_client()}.}
    \item{body}{Request payload for this operation, encoded as JSON.}
    \item{headers}{Optional named list of per-request headers.}
    \item{Returns}{Parsed JSON response as a named list, or NULL when the response body is empty.}
  }
}

\section{nova_complete_upload}{
  \code{nova_complete_upload(client, body, headers = NULL)}

  Complete Upload

  \describe{
    \item{client}{Thin client created by \code{create_nova_client()}.}
    \item{body}{Request payload for this operation, encoded as JSON.}
    \item{headers}{Optional named list of per-request headers.}
    \item{Returns}{Parsed JSON response as a named list, or NULL when the response body is empty.}
  }
}

\section{nova_initiate_upload}{
  \code{nova_initiate_upload(client, body, headers = NULL)}

  Initiate Upload

  \describe{
    \item{client}{Thin client created by \code{create_nova_client()}.}
    \item{body}{Request payload for this operation, encoded as JSON.}
    \item{headers}{Optional named list of per-request headers.}
    \item{Returns}{Parsed JSON response as a named list, or NULL when the response body is empty.}
  }
}

\section{nova_introspect_upload}{
  \code{nova_introspect_upload(client, body, headers = NULL)}

  Introspect Upload

  \describe{
    \item{client}{Thin client created by \code{create_nova_client()}.}
    \item{body}{Request payload for this operation, encoded as JSON.}
    \item{headers}{Optional named list of per-request headers.}
    \item{Returns}{Parsed JSON response as a named list, or NULL when the response body is empty.}
  }
}

\section{nova_sign_upload_parts}{
  \code{nova_sign_upload_parts(client, body, headers = NULL)}

  Sign Upload Parts

  \describe{
    \item{client}{Thin client created by \code{create_nova_client()}.}
    \item{body}{Request payload for this operation, encoded as JSON.}
    \item{headers}{Optional named list of per-request headers.}
    \item{Returns}{Parsed JSON response as a named list, or NULL when the response body is empty.}
  }
}

\keyword{package}
