"""Transfer policy resolution for public file-transfer endpoints."""

from __future__ import annotations

import inspect
import json
import logging
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from math import ceil
from typing import Any, Protocol, cast

from nova_file_api.transfer_config import TransferConfig
from nova_runtime_support.transfer_policy_document import (
    TransferPolicyDocument,
)

_DEFAULT_POLICY_ID = "default"
_DEFAULT_POLICY_VERSION = "2026-04-03"
_TARGET_UPLOAD_PART_COUNT = 2000
_MINIMUM_UPLOAD_PART_SIZE_BYTES = 64 * 1024 * 1024
_MAXIMUM_UPLOAD_PART_SIZE_BYTES = 512 * 1024 * 1024
_MIN_SIGN_BATCH_SIZE = 32
_MAX_SIGN_BATCH_SIZE = 128
_DEFAULT_ACTIVE_MULTIPART_UPLOAD_LIMIT = 200
_DEFAULT_DAILY_INGRESS_BUDGET_BYTES = 1024 * 1024 * 1024 * 1024
_DEFAULT_SIGN_REQUESTS_PER_UPLOAD_LIMIT = 512
_LOGGER = logging.getLogger(__name__)


@dataclass(slots=True, frozen=True, kw_only=True)
class TransferPolicy:
    """Resolved transfer policy for one caller and file size."""

    policy_id: str
    policy_version: str
    max_upload_bytes: int
    multipart_threshold_bytes: int
    target_upload_part_count: int
    minimum_part_size_bytes: int
    maximum_part_size_bytes: int
    upload_part_size_bytes: int
    max_concurrency_hint: int
    sign_batch_size_hint: int
    accelerate_enabled: bool
    checksum_algorithm: str | None
    resumable_ttl_seconds: int
    active_multipart_upload_limit: int
    daily_ingress_budget_bytes: int
    sign_requests_per_upload_limit: int


class AppConfigDataClient(Protocol):
    """Subset of AppConfigData client operations used by the runtime."""

    async def start_configuration_session(
        self,
        **kwargs: object,
    ) -> dict[str, object]:
        """Start one configuration session."""

    async def get_latest_configuration(
        self,
        **kwargs: object,
    ) -> dict[str, object]:
        """Retrieve the latest deployed configuration."""


class TransferPolicyProvider(Protocol):
    """Resolve the effective transfer policy for one caller scope."""

    async def resolve(self, *, scope_id: str | None) -> TransferPolicy:
        """Return the effective transfer policy."""


@dataclass(slots=True)
class AppConfigTransferPolicySource:
    """Best-effort AppConfig-backed transfer policy source."""

    client: AppConfigDataClient
    application_identifier: str
    environment_identifier: str
    configuration_profile_identifier: str
    minimum_poll_interval_seconds: int
    _token: str | None = None
    _cached_document: TransferPolicyDocument | None = None
    _next_refresh_at: datetime | None = None

    async def get_document(self) -> TransferPolicyDocument | None:
        """Return the latest AppConfig document or ``None`` on failure."""
        now = datetime.now(tz=UTC)
        if (
            self._cached_document is not None
            and self._next_refresh_at is not None
            and now < self._next_refresh_at
        ):
            return self._cached_document
        try:
            if self._token is None:
                session = await self.client.start_configuration_session(
                    ApplicationIdentifier=self.application_identifier,
                    EnvironmentIdentifier=self.environment_identifier,
                    ConfigurationProfileIdentifier=(
                        self.configuration_profile_identifier
                    ),
                    RequiredMinimumPollIntervalInSeconds=(
                        self.minimum_poll_interval_seconds
                    ),
                )
                self._token = _opt_str(session.get("InitialConfigurationToken"))
            if self._token is None:
                return self._cached_document
            latest = await self.client.get_latest_configuration(
                ConfigurationToken=self._token,
            )
            self._token = _opt_str(latest.get("NextPollConfigurationToken"))
            poll_interval = (
                _as_int(latest.get("NextPollIntervalInSeconds"))
                or self.minimum_poll_interval_seconds
            )
            self._next_refresh_at = now + timedelta(seconds=poll_interval)
            payload = await _read_configuration_payload(
                latest.get("Configuration")
            )
            if payload:
                self._cached_document = (
                    TransferPolicyDocument.model_validate_json(payload)
                )
            else:
                return self._cached_document
        except Exception:
            _LOGGER.warning(
                "transfer_policy_appconfig_refresh_failed",
                exc_info=True,
            )
            return self._cached_document
        return self._cached_document


def resolve_transfer_policy(
    *,
    config: TransferConfig,
    document: TransferPolicyDocument | None = None,
) -> TransferPolicy:
    """Resolve the current transfer policy from static runtime settings."""
    active_multipart_upload_limit = (
        config.active_multipart_upload_limit
        or _DEFAULT_ACTIVE_MULTIPART_UPLOAD_LIMIT
    )
    daily_ingress_budget_bytes = (
        config.daily_ingress_budget_bytes or _DEFAULT_DAILY_INGRESS_BUDGET_BYTES
    )
    sign_requests_per_upload_limit = (
        config.sign_requests_per_upload_limit
        or _DEFAULT_SIGN_REQUESTS_PER_UPLOAD_LIMIT
    )
    target_upload_part_count = _bounded_int(
        configured=document.target_upload_part_count if document else None,
        default=config.target_upload_part_count or _TARGET_UPLOAD_PART_COUNT,
        minimum=1,
        maximum=10_000,
    )
    max_concurrency_hint = _bounded_int(
        configured=document.max_concurrency_hint if document else None,
        default=config.max_concurrency,
        minimum=1,
        maximum=32,
    )
    sign_batch_size_hint = _bounded_int(
        configured=document.sign_batch_size_hint if document else None,
        default=max(_MIN_SIGN_BATCH_SIZE, max_concurrency_hint * 4),
        minimum=_MIN_SIGN_BATCH_SIZE,
        maximum=_MAX_SIGN_BATCH_SIZE,
    )
    return TransferPolicy(
        policy_id=_opt_str(document.policy_id if document else None)
        or config.policy_id
        or _DEFAULT_POLICY_ID,
        policy_version=_opt_str(document.policy_version if document else None)
        or config.policy_version
        or _DEFAULT_POLICY_VERSION,
        max_upload_bytes=min(
            config.max_upload_bytes,
            document.max_upload_bytes
            if document and document.max_upload_bytes is not None
            else config.max_upload_bytes,
        ),
        multipart_threshold_bytes=_bounded_int(
            configured=(
                document.multipart_threshold_bytes if document else None
            ),
            default=config.multipart_threshold_bytes,
            minimum=5 * 1024 * 1024,
            maximum=config.max_upload_bytes,
        ),
        target_upload_part_count=target_upload_part_count,
        minimum_part_size_bytes=_MINIMUM_UPLOAD_PART_SIZE_BYTES,
        maximum_part_size_bytes=_MAXIMUM_UPLOAD_PART_SIZE_BYTES,
        upload_part_size_bytes=_bounded_int(
            configured=document.upload_part_size_bytes if document else None,
            default=config.part_size_bytes,
            minimum=_MINIMUM_UPLOAD_PART_SIZE_BYTES,
            maximum=_MAXIMUM_UPLOAD_PART_SIZE_BYTES,
        ),
        max_concurrency_hint=max_concurrency_hint,
        sign_batch_size_hint=sign_batch_size_hint,
        accelerate_enabled=(
            document.accelerate_enabled
            if document and document.accelerate_enabled is not None
            else config.use_accelerate_endpoint
        ),
        checksum_algorithm=(
            document.checksum_algorithm
            if document and document.checksum_algorithm is not None
            else config.checksum_algorithm
        ),
        resumable_ttl_seconds=_bounded_int(
            configured=document.resumable_ttl_seconds if document else None,
            default=config.resumable_window_seconds,
            minimum=60,
            maximum=30 * 24 * 60 * 60,
        ),
        active_multipart_upload_limit=(
            _bounded_int(
                configured=(
                    document.active_multipart_upload_limit if document else None
                ),
                default=active_multipart_upload_limit,
                minimum=1,
                maximum=active_multipart_upload_limit,
            )
        ),
        daily_ingress_budget_bytes=(
            _bounded_int(
                configured=(
                    document.daily_ingress_budget_bytes if document else None
                ),
                default=daily_ingress_budget_bytes,
                minimum=1,
                maximum=daily_ingress_budget_bytes,
            )
        ),
        sign_requests_per_upload_limit=(
            _bounded_int(
                configured=(
                    document.sign_requests_per_upload_limit
                    if document
                    else None
                ),
                default=sign_requests_per_upload_limit,
                minimum=1,
                maximum=sign_requests_per_upload_limit,
            )
        ),
    )


async def resolve_transfer_policy_document(
    *,
    source: AppConfigTransferPolicySource | None,
) -> TransferPolicyDocument | None:
    """Return the latest policy document when one is configured."""
    if source is None:
        return None
    return await source.get_document()


@dataclass(slots=True)
class StaticTransferPolicyProvider:
    """Resolve transfer policy from static runtime settings only."""

    config: TransferConfig

    async def resolve(self, *, scope_id: str | None) -> TransferPolicy:
        """Resolve the effective static transfer policy."""
        del scope_id
        return resolve_transfer_policy(config=self.config)


@dataclass(slots=True)
class AppConfigTransferPolicyProvider:
    """Resolve transfer policy with AppConfig as a best-effort overlay."""

    config: TransferConfig
    source: AppConfigTransferPolicySource

    async def resolve(self, *, scope_id: str | None) -> TransferPolicy:
        """Resolve transfer policy with AppConfig as a best-effort overlay."""
        del scope_id
        document = await resolve_transfer_policy_document(source=self.source)
        return resolve_transfer_policy(config=self.config, document=document)


def build_transfer_policy_provider(
    *,
    config: TransferConfig,
    appconfig_client: AppConfigDataClient | None = None,
) -> TransferPolicyProvider:
    """Create the configured transfer policy provider."""
    if (
        appconfig_client is not None
        and config.policy_appconfig_application
        and config.policy_appconfig_environment
        and config.policy_appconfig_profile
    ):
        return AppConfigTransferPolicyProvider(
            config=config,
            source=AppConfigTransferPolicySource(
                client=appconfig_client,
                application_identifier=config.policy_appconfig_application,
                environment_identifier=config.policy_appconfig_environment,
                configuration_profile_identifier=config.policy_appconfig_profile,
                minimum_poll_interval_seconds=(
                    config.policy_appconfig_poll_interval_seconds
                ),
            ),
        )
    return StaticTransferPolicyProvider(config=config)


def upload_part_size_bytes(
    *,
    file_size_bytes: int,
    policy: TransferPolicy,
) -> int:
    """Return the upload part size for one file under the resolved policy."""
    candidate_size = ceil(file_size_bytes / policy.target_upload_part_count)
    return _bounded_int(
        configured=max(policy.upload_part_size_bytes, candidate_size),
        default=policy.upload_part_size_bytes,
        minimum=policy.minimum_part_size_bytes,
        maximum=policy.maximum_part_size_bytes,
    )


async def _read_configuration_payload(configuration: object) -> str | None:
    if configuration is None:
        return None
    if isinstance(configuration, str):
        return configuration if configuration.strip() else None
    if isinstance(configuration, (bytes, bytearray, memoryview)):
        payload = bytes(configuration).decode("utf-8").strip()
        return payload or None
    reader = getattr(configuration, "read", None)
    if callable(reader):
        result = reader()
        if inspect.isawaitable(result):
            result = await cast(Any, result)
        if isinstance(result, (bytes, bytearray, memoryview)):
            payload = bytes(result).decode("utf-8").strip()
            return payload or None
        if isinstance(result, str):
            return result.strip() or None
    if hasattr(configuration, "__iter__"):
        chunks = list(cast(Any, configuration))
        if chunks and isinstance(chunks[0], (bytes, bytearray, memoryview)):
            bytes_payload = b"".join(bytes(chunk) for chunk in chunks)
            return bytes_payload.decode("utf-8").strip() or None
        payload = json.dumps(chunks).strip()
        return payload or None
    return None


def _bounded_int(
    *,
    configured: int | None,
    default: int,
    minimum: int,
    maximum: int,
) -> int:
    value = configured if configured is not None else default
    return max(minimum, min(value, maximum))


def _opt_str(value: object) -> str | None:
    return value if isinstance(value, str) and value.strip() else None


def _as_int(value: object) -> int | None:
    return (
        value
        if isinstance(value, int) and not isinstance(value, bool)
        else None
    )
