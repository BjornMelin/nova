"""Shared AWS SDK config builders for Nova runtime owners."""

from __future__ import annotations

from botocore.config import Config

_AWS_CLIENT_CONNECT_TIMEOUT_SECONDS = 5
_AWS_CONTROL_PLANE_READ_TIMEOUT_SECONDS = 30
_AWS_CLIENT_TOTAL_MAX_ATTEMPTS = 3
_AWS_CLIENT_RETRY_MODE = "standard"


def _aws_shared_client_config() -> Config:
    """Build Nova's shared connect-timeout and retry policy."""
    return Config(
        connect_timeout=_AWS_CLIENT_CONNECT_TIMEOUT_SECONDS,
        retries={
            "mode": _AWS_CLIENT_RETRY_MODE,
            "total_max_attempts": _AWS_CLIENT_TOTAL_MAX_ATTEMPTS,
        },
    )


def aws_client_config() -> Config:
    """Build Nova's control-plane client timeout and retry policy."""
    return _aws_shared_client_config().merge(
        Config(read_timeout=_AWS_CONTROL_PLANE_READ_TIMEOUT_SECONDS)
    )


def s3_client_config(*, use_accelerate_endpoint: bool) -> Config:
    """Return the S3 client config with optional acceleration.

    Preserve botocore's default S3 read timeout so long multipart copy
    operations do not fail under Nova's shorter control-plane timeout.
    """
    return _aws_shared_client_config().merge(
        Config(s3={"use_accelerate_endpoint": use_accelerate_endpoint})
    )
