"""S3 client factory helpers."""

from __future__ import annotations

from contextlib import AbstractAsyncContextManager
from importlib import import_module
from typing import Any, Protocol, TypeAlias, cast

import boto3
from botocore.config import Config

from nova_dash_bridge.config import FileTransferEnvConfig

S3Client: TypeAlias = Any
AsyncS3Client: TypeAlias = Any
AsyncS3ClientContext: TypeAlias = AbstractAsyncContextManager[AsyncS3Client]

__all__ = [
    "AsyncS3Client",
    "AsyncS3ClientContext",
    "S3Client",
    "S3ClientFactory",
    "SupportsCreateAsyncS3Client",
    "SupportsCreateS3Client",
]


def _client_kwargs(env: FileTransferEnvConfig) -> dict[str, Any]:
    """Build shared boto client kwargs from transfer env configuration."""
    config = Config(s3={"use_accelerate_endpoint": env.use_accelerate_endpoint})
    kwargs: dict[str, Any] = {"config": config}
    if env.region:
        kwargs["region_name"] = env.region
    return kwargs


class S3ClientFactory:
    """Build S3 clients with optional Transfer Acceleration support."""

    def create(self, env: FileTransferEnvConfig) -> S3Client:
        """Create an S3 client from transfer env configuration."""
        return boto3.client("s3", **_client_kwargs(env))

    def create_async(self, env: FileTransferEnvConfig) -> AsyncS3ClientContext:
        """Create an async S3 client context from transfer env configuration."""
        session = import_module("aioboto3").Session()
        return cast(
            AsyncS3ClientContext,
            session.client("s3", **_client_kwargs(env)),
        )


class SupportsCreateS3Client(Protocol):
    """Structural protocol for S3 client factories used by the service layer."""

    def create(self, env: FileTransferEnvConfig) -> S3Client:
        """Return an S3-compatible client."""


class SupportsCreateAsyncS3Client(Protocol):
    """Structural protocol for async S3 client factories."""

    def create_async(
        self,
        env: FileTransferEnvConfig,
    ) -> AsyncS3ClientContext:
        """Return an async S3 client context."""
