"""Application configuration models."""

from __future__ import annotations

import importlib.metadata
import json
import os

from pydantic import Field, field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

from nova_file_api.models import (
    ActivityStoreBackend,
    JobsQueueBackend,
    JobsRepositoryBackend,
)

_MSG_WORKER_RUNTIME_REQUIRES_JOBS_ENABLED = (
    "JOBS_ENABLED must be true when JOBS_RUNTIME_MODE=worker"
)
_MSG_WORKER_RUNTIME_REQUIRES_SQS_BACKEND = (
    "JOBS_QUEUE_BACKEND must be sqs when JOBS_RUNTIME_MODE=worker"
)
_MSG_WORKER_RUNTIME_REQUIRES_SQS_QUEUE_URL = (
    "JOBS_SQS_QUEUE_URL must be configured when JOBS_RUNTIME_MODE=worker"
)
_MSG_WORKER_RUNTIME_REQUIRES_DYNAMODB_JOBS_BACKEND = (
    "JOBS_REPOSITORY_BACKEND must be dynamodb when JOBS_RUNTIME_MODE=worker"
)
_MSG_WORKER_RUNTIME_REQUIRES_JOBS_TABLE = (
    "JOBS_DYNAMODB_TABLE must be configured when JOBS_RUNTIME_MODE=worker"
)
_MSG_WORKER_RUNTIME_REQUIRES_DYNAMODB_ACTIVITY_BACKEND = (
    "ACTIVITY_STORE_BACKEND must be dynamodb when JOBS_RUNTIME_MODE=worker"
)
_MSG_WORKER_RUNTIME_REQUIRES_ACTIVITY_TABLE = (
    "ACTIVITY_ROLLUPS_TABLE must be configured when JOBS_RUNTIME_MODE=worker"
)
_MSG_STEP_FUNCTIONS_REQUIRES_STATE_MACHINE_ARN = (
    "JOBS_STEP_FUNCTIONS_STATE_MACHINE_ARN must be configured when "
    "JOBS_QUEUE_BACKEND=stepfunctions and JOBS_ENABLED=true"
)
_MSG_PRODUCTION_CORS_REQUIRES_ALLOWED_ORIGINS = (
    "ALLOWED_ORIGINS must be configured for production deployments"
)
_DEFAULT_DEV_CORS_ALLOWED_ORIGINS = (
    "http://localhost:3000",
    "http://127.0.0.1:3000",
    "http://localhost:8050",
    "http://127.0.0.1:8050",
)


def _is_blank(value: str | None) -> bool:
    """Return whether an optional environment value is unset or blank."""
    return value is None or not value.strip()


def _default_app_version() -> str:
    """Return installed package version with resilient fallback."""
    try:
        return importlib.metadata.version("nova-file-api")
    except importlib.metadata.PackageNotFoundError:
        return "0.0.0"


def _env_value_or_none(name: str) -> str | None:
    """Return one non-blank environment variable value when configured."""
    value = os.environ.get(name)
    if value is None:
        return None
    stripped = value.strip()
    if not stripped:
        return None
    return stripped


def _parse_string_tuple(value: object) -> tuple[str, ...]:
    """Normalize JSON or comma-delimited inputs into a tuple of strings."""
    if value is None:
        return ()
    if isinstance(value, str):
        stripped = value.strip()
        if not stripped:
            return ()
        if stripped.startswith("["):
            try:
                parsed = json.loads(stripped)
            except json.JSONDecodeError as exc:
                raise ValueError(
                    "ALLOWED_ORIGINS must be valid JSON when provided "
                    "as a list string."
                ) from exc
            if not isinstance(parsed, list):
                raise TypeError("JSON input must decode to a list of strings.")
            return _parse_string_tuple(parsed)
        return tuple(
            item
            for item in (part.strip() for part in stripped.split(","))
            if item
        )
    if isinstance(value, (list, tuple, set, frozenset)):
        if any(not isinstance(part, str) for part in value):
            raise TypeError("list input must contain only strings")
        return tuple(
            item
            for item in (
                part.strip() for part in value if isinstance(part, str)
            )
            if item
        )
    raise TypeError("value must be a string or a list of strings")


class Settings(BaseSettings):
    """Runtime settings loaded from environment variables."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        env_ignore_empty=True,
        extra="ignore",
        validate_by_name=True,
        validate_by_alias=True,
        serialize_by_alias=False,
    )

    app_name: str = Field(
        default="nova-file-api",
        validation_alias="APP_NAME",
    )
    app_version: str = Field(
        default_factory=_default_app_version,
        validation_alias="APP_VERSION",
    )
    environment: str = Field(default="dev", validation_alias="ENVIRONMENT")
    cors_allowed_origins: tuple[str, ...] = Field(
        default=(),
        validation_alias="ALLOWED_ORIGINS",
    )

    file_transfer_enabled: bool = Field(
        default=True,
        validation_alias="FILE_TRANSFER_ENABLED",
    )
    file_transfer_bucket: str = Field(
        default="",
        validation_alias="FILE_TRANSFER_BUCKET",
    )
    file_transfer_upload_prefix: str = Field(
        default="uploads/",
        validation_alias="FILE_TRANSFER_UPLOAD_PREFIX",
    )
    file_transfer_export_prefix: str = Field(
        default="exports/",
        validation_alias="FILE_TRANSFER_EXPORT_PREFIX",
    )
    file_transfer_tmp_prefix: str = Field(
        default="tmp/",
        validation_alias="FILE_TRANSFER_TMP_PREFIX",
    )
    file_transfer_presign_upload_ttl_seconds: int = Field(
        default=1800,
        validation_alias="FILE_TRANSFER_PRESIGN_UPLOAD_TTL_SECONDS",
        ge=60,
        le=3600,
    )
    file_transfer_presign_download_ttl_seconds: int = Field(
        default=900,
        validation_alias="FILE_TRANSFER_PRESIGN_DOWNLOAD_TTL_SECONDS",
        ge=60,
        le=3600,
    )
    file_transfer_multipart_threshold_bytes: int = Field(
        default=100 * 1024 * 1024,
        validation_alias="FILE_TRANSFER_MULTIPART_THRESHOLD_BYTES",
        ge=5 * 1024 * 1024,
    )
    file_transfer_part_size_bytes: int = Field(
        default=128 * 1024 * 1024,
        validation_alias="FILE_TRANSFER_PART_SIZE_BYTES",
        ge=5 * 1024 * 1024,
        le=5 * 1024 * 1024 * 1024,
    )
    file_transfer_max_concurrency: int = Field(
        default=4,
        validation_alias="FILE_TRANSFER_MAX_CONCURRENCY",
        ge=1,
        le=32,
    )
    file_transfer_use_accelerate_endpoint: bool = Field(
        default=False,
        validation_alias="FILE_TRANSFER_USE_ACCELERATE_ENDPOINT",
    )
    max_upload_bytes: int = Field(
        default=500 * 1024 * 1024 * 1024,
        validation_alias="FILE_TRANSFER_MAX_UPLOAD_BYTES",
        ge=1,
    )

    oidc_issuer: str | None = Field(
        default=None, validation_alias="OIDC_ISSUER"
    )
    oidc_audience: str | None = Field(
        default=None, validation_alias="OIDC_AUDIENCE"
    )
    oidc_jwks_url: str | None = Field(
        default=None, validation_alias="OIDC_JWKS_URL"
    )
    oidc_required_scopes: str = Field(
        default="", validation_alias="OIDC_REQUIRED_SCOPES"
    )
    oidc_required_permissions: str = Field(
        default="",
        validation_alias="OIDC_REQUIRED_PERMISSIONS",
    )
    oidc_clock_skew_seconds: int = Field(
        default=0,
        validation_alias="OIDC_CLOCK_SKEW_SECONDS",
        ge=0,
        le=120,
    )
    blocking_io_thread_tokens: int = Field(
        default=80,
        validation_alias="BLOCKING_IO_THREAD_TOKENS",
        ge=1,
        le=1000,
    )

    cache_local_ttl_seconds: int = Field(
        default=120,
        validation_alias="CACHE_LOCAL_TTL_SECONDS",
        ge=1,
    )
    cache_local_max_entries: int = Field(
        default=2000,
        validation_alias="CACHE_LOCAL_MAX_ENTRIES",
        ge=10,
    )
    cache_key_prefix: str = Field(
        default="nova", validation_alias="CACHE_KEY_PREFIX"
    )
    cache_key_schema_version: int = Field(
        default=1,
        validation_alias="CACHE_KEY_SCHEMA_VERSION",
        ge=1,
    )
    auth_jwt_cache_max_ttl_seconds: int = Field(
        default=120,
        validation_alias="AUTH_JWT_CACHE_MAX_TTL_SECONDS",
        ge=1,
        le=3600,
    )

    idempotency_enabled: bool = Field(
        default=True,
        validation_alias="IDEMPOTENCY_ENABLED",
    )
    idempotency_ttl_seconds: int = Field(
        default=900,
        validation_alias="IDEMPOTENCY_TTL_SECONDS",
        ge=60,
        le=86400,
    )
    idempotency_dynamodb_table: str | None = Field(
        default=None,
        validation_alias="IDEMPOTENCY_DYNAMODB_TABLE",
    )

    jobs_enabled: bool = Field(default=True, validation_alias="JOBS_ENABLED")
    jobs_queue_backend: JobsQueueBackend = Field(
        default=JobsQueueBackend.MEMORY,
        validation_alias="JOBS_QUEUE_BACKEND",
    )
    jobs_repository_backend: JobsRepositoryBackend = Field(
        default=JobsRepositoryBackend.MEMORY,
        validation_alias="JOBS_REPOSITORY_BACKEND",
    )
    jobs_dynamodb_table: str | None = Field(
        default=None,
        validation_alias="JOBS_DYNAMODB_TABLE",
    )
    jobs_sqs_queue_url: str | None = Field(
        default=None, validation_alias="JOBS_SQS_QUEUE_URL"
    )
    jobs_step_functions_state_machine_arn: str | None = Field(
        default=None,
        validation_alias="JOBS_STEP_FUNCTIONS_STATE_MACHINE_ARN",
    )
    jobs_sqs_retry_mode: str = Field(
        default="standard",
        validation_alias="JOBS_SQS_RETRY_MODE",
        pattern="^(legacy|standard|adaptive)$",
    )
    jobs_sqs_retry_total_max_attempts: int = Field(
        default=3,
        validation_alias="JOBS_SQS_RETRY_TOTAL_MAX_ATTEMPTS",
        ge=1,
        le=10,
    )
    jobs_sqs_max_number_of_messages: int = Field(
        default=1,
        validation_alias="JOBS_SQS_MAX_NUMBER_OF_MESSAGES",
        ge=1,
        le=10,
    )
    jobs_sqs_wait_time_seconds: int = Field(
        default=20,
        validation_alias="JOBS_SQS_WAIT_TIME_SECONDS",
        ge=0,
        le=20,
    )
    jobs_sqs_visibility_timeout_seconds: int = Field(
        default=120,
        validation_alias="JOBS_SQS_VISIBILITY_TIMEOUT_SECONDS",
        ge=0,
        le=43200,
    )
    jobs_runtime_mode: str = Field(
        default="api",
        validation_alias="JOBS_RUNTIME_MODE",
        pattern="^(api|worker)$",
    )

    activity_store_backend: ActivityStoreBackend = Field(
        default=ActivityStoreBackend.MEMORY,
        validation_alias="ACTIVITY_STORE_BACKEND",
    )
    activity_rollups_table: str | None = Field(
        default=None,
        validation_alias="ACTIVITY_ROLLUPS_TABLE",
    )

    metrics_namespace: str = Field(
        default="NovaFileApi",
        validation_alias="METRICS_NAMESPACE",
    )

    @field_validator("cors_allowed_origins", mode="before")
    @classmethod
    def validate_cors_allowed_origins(
        cls,
        value: object,
    ) -> tuple[str, ...]:
        """Normalize configured CORS origins into a stable tuple."""
        return _parse_string_tuple(value)

    @property
    def default_required_scopes(self) -> tuple[str, ...]:
        """Return configured default required scopes as a tuple."""
        if not self.oidc_required_scopes.strip():
            return ()
        return tuple(s for s in self.oidc_required_scopes.split() if s)

    @property
    def default_required_permissions(self) -> tuple[str, ...]:
        """Return configured default required permissions as a tuple."""
        if not self.oidc_required_permissions.strip():
            return ()
        return tuple(
            permission
            for permission in self.oidc_required_permissions.split()
            if permission
        )

    @property
    def oidc_bearer_verifier_configured(self) -> bool:
        """Return whether the in-process bearer verifier can be built."""
        return all(
            value is not None and value.strip()
            for value in (
                self.oidc_issuer,
                self.oidc_audience,
                self.oidc_jwks_url,
            )
        )

    @property
    def resolved_cors_allowed_origins(self) -> tuple[str, ...]:
        """Return configured browser origins or explicit local defaults."""
        if self.cors_allowed_origins:
            return self.cors_allowed_origins
        stack_allowed_origins = _env_value_or_none("STACK_ALLOWED_ORIGINS")
        if stack_allowed_origins is not None:
            return _parse_string_tuple(stack_allowed_origins)
        environment = self.environment.strip().lower()
        if environment in {"dev", "development", "local", "test"}:
            return _DEFAULT_DEV_CORS_ALLOWED_ORIGINS
        return ()

    @model_validator(mode="after")
    def validate_cors_settings(self) -> Settings:
        """Require explicit origins when running a production environment."""
        if (
            self.environment.strip().lower() in {"prod", "production"}
            and not self.resolved_cors_allowed_origins
        ):
            raise ValueError(_MSG_PRODUCTION_CORS_REQUIRES_ALLOWED_ORIGINS)
        return self

    @model_validator(mode="after")
    def validate_step_functions_settings(self) -> Settings:
        """Validate required settings for the Step Functions backend."""
        if (
            not self.jobs_enabled
            or self.jobs_queue_backend != JobsQueueBackend.STEP_FUNCTIONS
        ):
            return self
        if _is_blank(self.jobs_step_functions_state_machine_arn):
            raise ValueError(_MSG_STEP_FUNCTIONS_REQUIRES_STATE_MACHINE_ARN)
        return self

    @model_validator(mode="after")
    def validate_worker_runtime_settings(self) -> Settings:
        """Validate required settings when the worker runtime is enabled."""
        if self.jobs_runtime_mode != "worker":
            return self
        if not self.jobs_enabled:
            raise ValueError(_MSG_WORKER_RUNTIME_REQUIRES_JOBS_ENABLED)
        if self.jobs_queue_backend != JobsQueueBackend.SQS:
            raise ValueError(_MSG_WORKER_RUNTIME_REQUIRES_SQS_BACKEND)
        if _is_blank(self.jobs_sqs_queue_url):
            raise ValueError(_MSG_WORKER_RUNTIME_REQUIRES_SQS_QUEUE_URL)
        if self.jobs_repository_backend != JobsRepositoryBackend.DYNAMODB:
            raise ValueError(_MSG_WORKER_RUNTIME_REQUIRES_DYNAMODB_JOBS_BACKEND)
        if _is_blank(self.jobs_dynamodb_table):
            raise ValueError(_MSG_WORKER_RUNTIME_REQUIRES_JOBS_TABLE)
        if self.activity_store_backend != ActivityStoreBackend.DYNAMODB:
            raise ValueError(
                _MSG_WORKER_RUNTIME_REQUIRES_DYNAMODB_ACTIVITY_BACKEND
            )
        if _is_blank(self.activity_rollups_table):
            raise ValueError(_MSG_WORKER_RUNTIME_REQUIRES_ACTIVITY_TABLE)
        return self

    @model_validator(mode="after")
    def validate_multipart_upload_capacity(self) -> Settings:
        """Ensure max upload bytes can be represented with multipart parts."""
        max_supported_upload_bytes = self.file_transfer_part_size_bytes * 10_000
        if self.max_upload_bytes > max_supported_upload_bytes:
            raise ValueError(
                "FILE_TRANSFER_MAX_UPLOAD_BYTES must be less than or equal to "
                "FILE_TRANSFER_PART_SIZE_BYTES * 10000"
            )
        return self

    @model_validator(mode="after")
    def validate_idempotency_settings(self) -> Settings:
        """Require DynamoDB table wiring for API-side idempotency."""
        if (
            self.idempotency_enabled
            and self.jobs_runtime_mode != "worker"
            and _is_blank(self.idempotency_dynamodb_table)
        ):
            raise ValueError(
                "IDEMPOTENCY_DYNAMODB_TABLE must be configured when "
                "IDEMPOTENCY_ENABLED=true"
            )
        return self
