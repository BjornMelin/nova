"""Application configuration models."""

from __future__ import annotations

import importlib.metadata
import warnings

from pydantic import Field, SecretStr, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

from nova_file_api.models import (
    ActivityStoreBackend,
    AuthMode,
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
_MSG_WORKER_RUNTIME_REQUIRES_API_BASE_URL = (
    "JOBS_API_BASE_URL must be configured when JOBS_RUNTIME_MODE=worker"
)
_MSG_WORKER_RUNTIME_REQUIRES_UPDATE_TOKEN = (
    "JOBS_WORKER_UPDATE_TOKEN must be configured when JOBS_RUNTIME_MODE=worker"
)


def _default_app_version() -> str:
    """Return installed package version with resilient fallback."""
    try:
        return importlib.metadata.version("nova-file-api")
    except importlib.metadata.PackageNotFoundError:
        return "0.0.0"


class Settings(BaseSettings):
    """Runtime settings loaded from environment variables."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    app_name: str = Field(default="nova-file-api")
    app_version: str = Field(
        default_factory=_default_app_version,
        alias="APP_VERSION",
    )
    environment: str = Field(default="dev")

    file_transfer_enabled: bool = Field(
        default=True,
        alias="FILE_TRANSFER_ENABLED",
    )
    file_transfer_bucket: str = Field(
        default="",
        alias="FILE_TRANSFER_BUCKET",
    )
    file_transfer_upload_prefix: str = Field(
        default="uploads/",
        alias="FILE_TRANSFER_UPLOAD_PREFIX",
    )
    file_transfer_export_prefix: str = Field(
        default="exports/",
        alias="FILE_TRANSFER_EXPORT_PREFIX",
    )
    file_transfer_tmp_prefix: str = Field(
        default="tmp/",
        alias="FILE_TRANSFER_TMP_PREFIX",
    )
    file_transfer_presign_upload_ttl_seconds: int = Field(
        default=900,
        alias="FILE_TRANSFER_PRESIGN_UPLOAD_TTL_SECONDS",
        ge=60,
        le=3600,
    )
    file_transfer_presign_download_ttl_seconds: int = Field(
        default=900,
        alias="FILE_TRANSFER_PRESIGN_DOWNLOAD_TTL_SECONDS",
        ge=60,
        le=3600,
    )
    file_transfer_multipart_threshold_bytes: int = Field(
        default=100 * 1024 * 1024,
        alias="FILE_TRANSFER_MULTIPART_THRESHOLD_BYTES",
        ge=5 * 1024 * 1024,
    )
    file_transfer_part_size_bytes: int = Field(
        default=128 * 1024 * 1024,
        alias="FILE_TRANSFER_PART_SIZE_BYTES",
        ge=5 * 1024 * 1024,
        le=5 * 1024 * 1024 * 1024,
    )
    file_transfer_max_concurrency: int = Field(
        default=4,
        alias="FILE_TRANSFER_MAX_CONCURRENCY",
        ge=1,
        le=32,
    )
    file_transfer_use_accelerate_endpoint: bool = Field(
        default=False,
        alias="FILE_TRANSFER_USE_ACCELERATE_ENDPOINT",
    )
    max_upload_bytes: int = Field(
        default=5 * 1024 * 1024 * 1024,
        alias="FILE_TRANSFER_MAX_UPLOAD_BYTES",
        ge=1,
    )

    auth_mode: AuthMode = Field(default=AuthMode.SAME_ORIGIN, alias="AUTH_MODE")
    oidc_issuer: str | None = Field(default=None, alias="OIDC_ISSUER")
    oidc_audience: str | None = Field(default=None, alias="OIDC_AUDIENCE")
    oidc_jwks_url: str | None = Field(default=None, alias="OIDC_JWKS_URL")
    oidc_required_scopes: str = Field(default="", alias="OIDC_REQUIRED_SCOPES")
    oidc_required_permissions: str = Field(
        default="",
        alias="OIDC_REQUIRED_PERMISSIONS",
    )
    oidc_clock_skew_seconds: int = Field(
        default=0,
        alias="OIDC_CLOCK_SKEW_SECONDS",
        ge=0,
        le=120,
    )
    oidc_verifier_thread_tokens: int = Field(
        default=40,
        alias="OIDC_VERIFIER_THREAD_TOKENS",
        ge=1,
        le=1000,
    )
    blocking_io_thread_tokens: int = Field(
        default=80,
        alias="BLOCKING_IO_THREAD_TOKENS",
        ge=1,
        le=1000,
    )

    remote_auth_base_url: str | None = Field(
        default=None,
        alias="REMOTE_AUTH_BASE_URL",
    )
    remote_auth_timeout_seconds: float = Field(
        default=2.0,
        alias="REMOTE_AUTH_TIMEOUT_SECONDS",
        gt=0.0,
        le=10.0,
    )

    cache_redis_url: str | None = Field(default=None, alias="CACHE_REDIS_URL")
    cache_redis_max_connections: int = Field(
        default=64,
        alias="CACHE_REDIS_MAX_CONNECTIONS",
        ge=1,
        le=10000,
    )
    cache_redis_socket_timeout_seconds: float = Field(
        default=0.5,
        alias="CACHE_REDIS_SOCKET_TIMEOUT_SECONDS",
        gt=0.0,
        le=30.0,
    )
    cache_redis_socket_connect_timeout_seconds: float = Field(
        default=0.5,
        alias="CACHE_REDIS_SOCKET_CONNECT_TIMEOUT_SECONDS",
        gt=0.0,
        le=30.0,
    )
    cache_redis_health_check_interval_seconds: int = Field(
        default=30,
        alias="CACHE_REDIS_HEALTH_CHECK_INTERVAL_SECONDS",
        ge=1,
        le=300,
    )
    cache_redis_retry_base_seconds: float = Field(
        default=0.05,
        alias="CACHE_REDIS_RETRY_BASE_SECONDS",
        gt=0.0,
        le=5.0,
    )
    cache_redis_retry_cap_seconds: float = Field(
        default=0.5,
        alias="CACHE_REDIS_RETRY_CAP_SECONDS",
        gt=0.0,
        le=30.0,
    )
    cache_redis_retry_attempts: int = Field(
        default=2,
        alias="CACHE_REDIS_RETRY_ATTEMPTS",
        ge=0,
        le=10,
    )
    cache_redis_decode_responses: bool = Field(
        default=False,
        alias="CACHE_REDIS_DECODE_RESPONSES",
    )
    cache_redis_protocol: int = Field(
        default=2,
        alias="CACHE_REDIS_PROTOCOL",
        ge=2,
        le=3,
    )
    cache_local_ttl_seconds: int = Field(
        default=120,
        alias="CACHE_LOCAL_TTL_SECONDS",
        ge=1,
    )
    cache_local_max_entries: int = Field(
        default=2000,
        alias="CACHE_LOCAL_MAX_ENTRIES",
        ge=10,
    )
    cache_shared_ttl_seconds: int = Field(
        default=300,
        alias="CACHE_SHARED_TTL_SECONDS",
        ge=1,
    )
    cache_key_prefix: str = Field(default="nova", alias="CACHE_KEY_PREFIX")
    cache_key_schema_version: int = Field(
        default=1,
        alias="CACHE_KEY_SCHEMA_VERSION",
        ge=1,
    )
    auth_jwt_cache_max_ttl_seconds: int = Field(
        default=120,
        alias="AUTH_JWT_CACHE_MAX_TTL_SECONDS",
        ge=1,
        le=3600,
    )

    idempotency_enabled: bool = Field(
        default=True,
        alias="IDEMPOTENCY_ENABLED",
    )
    idempotency_ttl_seconds: int = Field(
        default=900,
        alias="IDEMPOTENCY_TTL_SECONDS",
        ge=60,
        le=86400,
    )

    jobs_enabled: bool = Field(default=True, alias="JOBS_ENABLED")
    jobs_queue_backend: JobsQueueBackend = Field(
        default=JobsQueueBackend.MEMORY,
        alias="JOBS_QUEUE_BACKEND",
    )
    jobs_repository_backend: JobsRepositoryBackend = Field(
        default=JobsRepositoryBackend.MEMORY,
        alias="JOBS_REPOSITORY_BACKEND",
    )
    jobs_dynamodb_table: str | None = Field(
        default=None,
        alias="JOBS_DYNAMODB_TABLE",
    )
    jobs_sqs_queue_url: str | None = Field(
        default=None, alias="JOBS_SQS_QUEUE_URL"
    )
    jobs_sqs_retry_mode: str = Field(
        default="standard",
        alias="JOBS_SQS_RETRY_MODE",
        pattern="^(legacy|standard|adaptive)$",
    )
    jobs_sqs_retry_total_max_attempts: int = Field(
        default=3,
        alias="JOBS_SQS_RETRY_TOTAL_MAX_ATTEMPTS",
        ge=1,
        le=10,
    )
    jobs_sqs_max_number_of_messages: int = Field(
        default=1,
        alias="JOBS_SQS_MAX_NUMBER_OF_MESSAGES",
        ge=1,
        le=10,
    )
    jobs_sqs_wait_time_seconds: int = Field(
        default=20,
        alias="JOBS_SQS_WAIT_TIME_SECONDS",
        ge=0,
        le=20,
    )
    jobs_sqs_visibility_timeout_seconds: int = Field(
        default=120,
        alias="JOBS_SQS_VISIBILITY_TIMEOUT_SECONDS",
        ge=0,
        le=43200,
    )
    jobs_runtime_mode: str = Field(
        default="api",
        alias="JOBS_RUNTIME_MODE",
        pattern="^(api|worker)$",
    )
    jobs_api_base_url: str | None = Field(
        default=None,
        alias="JOBS_API_BASE_URL",
    )
    jobs_worker_update_token: SecretStr | None = Field(
        default=None,
        alias="JOBS_WORKER_UPDATE_TOKEN",
    )
    jobs_allow_insecure_missing_worker_token_nonprod: bool = Field(
        default=False,
        alias="JOBS_ALLOW_INSECURE_MISSING_WORKER_TOKEN_NONPROD",
    )

    activity_store_backend: ActivityStoreBackend = Field(
        default=ActivityStoreBackend.MEMORY,
        alias="ACTIVITY_STORE_BACKEND",
    )
    activity_rollups_table: str | None = Field(
        default=None,
        alias="ACTIVITY_ROLLUPS_TABLE",
    )

    metrics_namespace: str = Field(
        default="NovaFileApi",
        alias="METRICS_NAMESPACE",
    )

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
    def local_oidc_verifier_configured(self) -> bool:
        """Return whether jwt_local mode has the required OIDC settings."""
        return all(
            value is not None and value.strip()
            for value in (
                self.oidc_issuer,
                self.oidc_audience,
                self.oidc_jwks_url,
            )
        )

    @property
    def required_scopes(self) -> tuple[str, ...]:
        """Backward-compatible alias for default_required_scopes."""
        warnings.warn(
            (
                "Settings.required_scopes is deprecated; "
                "use default_required_scopes"
            ),
            DeprecationWarning,
            stacklevel=2,
        )
        return self.default_required_scopes

    @property
    def required_permissions(self) -> tuple[str, ...]:
        """Backward-compatible alias for default_required_permissions."""
        warnings.warn(
            (
                "Settings.required_permissions is deprecated; "
                "use default_required_permissions"
            ),
            DeprecationWarning,
            stacklevel=2,
        )
        return self.default_required_permissions

    @model_validator(mode="after")
    def validate_worker_runtime_settings(self) -> Settings:
        """Validate required settings when the worker runtime is enabled."""
        if self.jobs_runtime_mode != "worker":
            return self
        if not self.jobs_enabled:
            raise ValueError(_MSG_WORKER_RUNTIME_REQUIRES_JOBS_ENABLED)
        if self.jobs_queue_backend != JobsQueueBackend.SQS:
            raise ValueError(_MSG_WORKER_RUNTIME_REQUIRES_SQS_BACKEND)
        queue_url = (self.jobs_sqs_queue_url or "").strip()
        if not queue_url:
            raise ValueError(_MSG_WORKER_RUNTIME_REQUIRES_SQS_QUEUE_URL)
        api_base_url = (self.jobs_api_base_url or "").strip()
        if not api_base_url:
            raise ValueError(_MSG_WORKER_RUNTIME_REQUIRES_API_BASE_URL)
        token = (
            self.jobs_worker_update_token.get_secret_value()
            if self.jobs_worker_update_token is not None
            else ""
        ).strip()
        if not token:
            raise ValueError(_MSG_WORKER_RUNTIME_REQUIRES_UPDATE_TOKEN)
        return self
