"""Typed configuration and policies for file transfer."""

from __future__ import annotations

from collections.abc import Callable, Mapping
from dataclasses import dataclass, field
from typing import Any

from nova_file_api.public import Principal
from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

PrincipalResolver = Callable[[str | None], Principal]


class FileTransferEnvConfig(BaseSettings):
    """Container-craft compatible `FILE_TRANSFER_*` configuration."""

    model_config = SettingsConfigDict(
        env_prefix="",
        case_sensitive=False,
        extra="ignore",
    )

    enabled: bool = Field(
        default=False,
        validation_alias="FILE_TRANSFER_ENABLED",
    )
    bucket: str = Field(
        default="",
        validation_alias="FILE_TRANSFER_BUCKET",
    )
    upload_prefix: str = Field(
        default="uploads/",
        validation_alias="FILE_TRANSFER_UPLOAD_PREFIX",
    )
    export_prefix: str = Field(
        default="exports/",
        validation_alias="FILE_TRANSFER_EXPORT_PREFIX",
    )
    tmp_prefix: str = Field(
        default="tmp/",
        validation_alias="FILE_TRANSFER_TMP_PREFIX",
    )
    presign_upload_ttl_seconds: int = Field(
        default=1800,
        ge=60,
        le=3600,
        validation_alias="FILE_TRANSFER_PRESIGN_UPLOAD_TTL_SECONDS",
    )
    presign_download_ttl_seconds: int = Field(
        default=900,
        ge=60,
        le=3600,
        validation_alias="FILE_TRANSFER_PRESIGN_DOWNLOAD_TTL_SECONDS",
    )
    multipart_threshold_bytes: int = Field(
        default=104_857_600,
        ge=5 * 1024 * 1024,
        validation_alias="FILE_TRANSFER_MULTIPART_THRESHOLD_BYTES",
    )
    part_size_bytes: int = Field(
        default=134_217_728,
        ge=5 * 1024 * 1024,
        le=5 * 1024 * 1024 * 1024,
        validation_alias="FILE_TRANSFER_PART_SIZE_BYTES",
    )
    max_concurrency: int = Field(
        default=4,
        ge=1,
        le=32,
        validation_alias="FILE_TRANSFER_MAX_CONCURRENCY",
    )
    thread_tokens: int = Field(
        default=80,
        ge=1,
        le=1000,
        validation_alias="FILE_TRANSFER_THREAD_TOKENS",
    )
    use_accelerate_endpoint: bool = Field(
        default=False,
        validation_alias="FILE_TRANSFER_USE_ACCELERATE_ENDPOINT",
    )
    region: str | None = Field(
        default=None,
        validation_alias="FILE_TRANSFER_REGION",
    )

    @field_validator("upload_prefix", "export_prefix", "tmp_prefix")
    @classmethod
    def _normalize_prefix(cls, value: str) -> str:
        raw = value.strip()
        if not raw:
            raise ValueError("prefix values must be non-empty")
        return raw if raw.endswith("/") else f"{raw}/"

    @classmethod
    def from_env(
        cls,
        environ: Mapping[str, str] | None = None,
    ) -> FileTransferEnvConfig:
        """Load config from environment variables."""
        if environ is None:
            return cls()
        return cls.model_validate(dict(environ))


@dataclass(slots=True, kw_only=True)
class UploadPolicy:
    """Upload constraints enforced before issuing presigned operations."""

    max_upload_bytes: int
    allowed_extensions: set[str] = field(default_factory=set)
    multipart_threshold_bytes: int | None = None
    part_size_bytes: int | None = None
    max_concurrency: int | None = None
    per_extension_max_bytes: dict[str, int] = field(default_factory=dict)

    def __post_init__(self) -> None:
        """Validate policy values and normalize extensions."""
        if self.max_upload_bytes <= 0:
            raise ValueError("max_upload_bytes must be > 0")
        normalized = {
            self._normalize_extension(v) for v in self.allowed_extensions
        }
        if not normalized:
            raise ValueError("allowed_extensions must not be empty")
        self.allowed_extensions = normalized
        self.per_extension_max_bytes = {
            self._normalize_extension(ext): cap
            for ext, cap in self.per_extension_max_bytes.items()
        }
        for ext, cap in self.per_extension_max_bytes.items():
            if ext not in self.allowed_extensions:
                raise ValueError(
                    f"per_extension_max_bytes uses unknown extension: {ext}"
                )
            if cap <= 0:
                raise ValueError("per-extension max bytes must be > 0")
            if cap > self.max_upload_bytes:
                raise ValueError(
                    "per-extension max bytes cannot exceed max_upload_bytes"
                )

        if self.multipart_threshold_bytes is not None:
            if self.multipart_threshold_bytes < 5 * 1024 * 1024:
                raise ValueError("multipart_threshold_bytes must be >= 5 MiB")
            if self.multipart_threshold_bytes > self.max_upload_bytes:
                raise ValueError(
                    "multipart_threshold_bytes cannot exceed max_upload_bytes"
                )

        if self.part_size_bytes is not None:
            minimum = 5 * 1024 * 1024
            maximum = 5 * 1024 * 1024 * 1024
            if not minimum <= self.part_size_bytes <= maximum:
                raise ValueError(
                    "part_size_bytes must be between 5 MiB and 5 GiB"
                )

        if self.max_concurrency is not None and not (
            1 <= self.max_concurrency <= 32
        ):
            raise ValueError("max_concurrency must be between 1 and 32")

    @staticmethod
    def _normalize_extension(extension: str) -> str:
        raw = extension.strip().lower()
        if not raw:
            raise ValueError("extension values must be non-empty")
        return raw if raw.startswith(".") else f".{raw}"


@dataclass(slots=True, kw_only=True)
class AuthPolicy:
    """Authentication hooks for framework integrations."""

    principal_resolver: PrincipalResolver | None = None

    def resolve_principal(
        self,
        authorization_header: str | None,
    ) -> Principal:
        """Resolve a trusted principal from the incoming bearer header."""
        if self.principal_resolver is None:
            raise ValueError("auth principal_resolver is required")
        principal = self.principal_resolver(authorization_header)
        subject = principal.subject.strip()
        scope_id = principal.scope_id.strip()
        if not subject or not scope_id:
            raise ValueError(
                "resolved principal must include non-empty subject and scope_id"
            )
        return principal


def policy_from_env(
    env: FileTransferEnvConfig,
    *,
    max_upload_bytes: int,
    allowed_extensions: set[str],
    per_extension_max_bytes: dict[str, int] | None = None,
) -> UploadPolicy:
    """Build an upload policy using env defaults for multipart tuning."""
    return UploadPolicy(
        max_upload_bytes=max_upload_bytes,
        allowed_extensions=allowed_extensions,
        multipart_threshold_bytes=env.multipart_threshold_bytes,
        part_size_bytes=env.part_size_bytes,
        max_concurrency=env.max_concurrency,
        per_extension_max_bytes=per_extension_max_bytes or {},
    )


def request_context(
    *,
    request_id: str | None = None,
) -> dict[str, Any]:
    """Return log-safe request context fields."""
    return {"request_id": request_id} if request_id else {}
