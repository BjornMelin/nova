"""S3 client factory helpers."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any, Protocol, cast

import boto3
from botocore.client import BaseClient
from botocore.config import Config

from nova_dash_bridge.config import FileTransferEnvConfig

if TYPE_CHECKING:
    from mypy_boto3_s3 import S3Client  # type: ignore[import-not-found]
else:
    S3Client = BaseClient


class S3ClientFactory:
    """Build S3 clients with optional Transfer Acceleration support."""

    def create(self, env: FileTransferEnvConfig) -> S3Client:
        """Create an S3 client from transfer env configuration."""
        config = Config(
            s3={"use_accelerate_endpoint": env.use_accelerate_endpoint}
        )
        kwargs: dict[str, Any] = {"config": config}
        if env.region:
            kwargs["region_name"] = env.region
        return cast("S3Client", boto3.client("s3", **kwargs))


class SupportsCreateS3Client(Protocol):
    """Structural protocol for S3 client factories used by the service layer."""

    def create(self, env: FileTransferEnvConfig) -> S3Client:
        """Return an S3-compatible client."""
