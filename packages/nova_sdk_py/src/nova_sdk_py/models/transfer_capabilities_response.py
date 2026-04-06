from __future__ import annotations

from collections.abc import Mapping
from typing import (
    Any,
    TypeVar,
    cast,
)

from attrs import define as _attrs_define

from nova_sdk_py.models.transfer_capabilities_response_checksum_mode import (
    TransferCapabilitiesResponseChecksumMode,
)
from nova_sdk_py.types import UNSET, Unset

T = TypeVar("T", bound="TransferCapabilitiesResponse")


@_attrs_define
class TransferCapabilitiesResponse:
    """
    Transfer policy capabilities exposed to clients and operators.

    Attributes:
        accelerate_enabled: Whether S3 Transfer Acceleration is enabled.
        active_multipart_upload_limit: Maximum number of active multipart
        uploads per scope.
        checksum_algorithm: Checksum algorithm callers should use when
        checksums apply.
        checksum_mode: Server-enforced checksum mode for uploads.
        daily_ingress_budget_bytes: Per-scope daily ingress budget in bytes.
        large_export_worker_threshold_bytes: Export size threshold in bytes
        for the worker-backed copy lane.
        max_concurrency_hint: Suggested maximum number of concurrent client
        uploads.
        max_upload_bytes: Maximum allowed upload size in bytes.
        maximum_part_size_bytes: Maximum multipart part size accepted by the
        API.
        minimum_part_size_bytes: Minimum multipart part size accepted by the
        API.
        multipart_threshold_bytes: Object size in bytes at which multipart
        upload becomes required.
        policy_id: Identifier of the effective transfer policy.
        policy_version: Version of the effective transfer policy.
        resumable_ttl_seconds: How long multipart resume state remains
        valid, in seconds.
        sign_batch_size_hint: Suggested maximum number of parts per
        sign-parts request.
        sign_requests_per_upload_limit: Maximum number of sign-parts
        requests allowed per upload.
        target_upload_part_count: Target number of multipart parts for large
        uploads.
    """

    accelerate_enabled: bool
    """Whether S3 Transfer Acceleration is enabled."""
    active_multipart_upload_limit: int
    """Maximum number of active multipart uploads per scope."""
    checksum_mode: TransferCapabilitiesResponseChecksumMode
    """Server-enforced checksum mode for uploads."""
    daily_ingress_budget_bytes: int
    """Per-scope daily ingress budget in bytes."""
    large_export_worker_threshold_bytes: int
    """Export size threshold in bytes for the worker-backed copy lane."""
    max_concurrency_hint: int
    """Suggested maximum number of concurrent client uploads."""
    max_upload_bytes: int
    """Maximum allowed upload size in bytes."""
    maximum_part_size_bytes: int
    """Maximum multipart part size accepted by the API."""
    minimum_part_size_bytes: int
    """Minimum multipart part size accepted by the API."""
    multipart_threshold_bytes: int
    """Object size in bytes at which multipart upload becomes required."""
    policy_id: str
    """Identifier of the effective transfer policy."""
    policy_version: str
    """Version of the effective transfer policy."""
    resumable_ttl_seconds: int
    """How long multipart resume state remains valid, in seconds."""
    sign_batch_size_hint: int
    """Suggested maximum number of parts per sign-parts request."""
    sign_requests_per_upload_limit: int
    """Maximum number of sign-parts requests allowed per upload."""
    target_upload_part_count: int
    """Target number of multipart parts for large uploads."""
    checksum_algorithm: None | str | Unset = UNSET
    """Checksum algorithm callers should use when checksums apply."""

    def to_dict(self) -> dict[str, Any]:
        accelerate_enabled = self.accelerate_enabled

        active_multipart_upload_limit = self.active_multipart_upload_limit

        checksum_mode = self.checksum_mode.value

        daily_ingress_budget_bytes = self.daily_ingress_budget_bytes

        large_export_worker_threshold_bytes = (
            self.large_export_worker_threshold_bytes
        )

        max_concurrency_hint = self.max_concurrency_hint

        max_upload_bytes = self.max_upload_bytes

        maximum_part_size_bytes = self.maximum_part_size_bytes

        minimum_part_size_bytes = self.minimum_part_size_bytes

        multipart_threshold_bytes = self.multipart_threshold_bytes

        policy_id = self.policy_id

        policy_version = self.policy_version

        resumable_ttl_seconds = self.resumable_ttl_seconds

        sign_batch_size_hint = self.sign_batch_size_hint

        sign_requests_per_upload_limit = self.sign_requests_per_upload_limit

        target_upload_part_count = self.target_upload_part_count

        checksum_algorithm: None | str | Unset
        if isinstance(self.checksum_algorithm, Unset):
            checksum_algorithm = UNSET
        else:
            checksum_algorithm = self.checksum_algorithm

        field_dict: dict[str, Any] = {}

        field_dict.update(
            {
                "accelerate_enabled": accelerate_enabled,
                "active_multipart_upload_limit": active_multipart_upload_limit,
                "checksum_mode": checksum_mode,
                "daily_ingress_budget_bytes": daily_ingress_budget_bytes,
                "large_export_worker_threshold_bytes": large_export_worker_threshold_bytes,
                "max_concurrency_hint": max_concurrency_hint,
                "max_upload_bytes": max_upload_bytes,
                "maximum_part_size_bytes": maximum_part_size_bytes,
                "minimum_part_size_bytes": minimum_part_size_bytes,
                "multipart_threshold_bytes": multipart_threshold_bytes,
                "policy_id": policy_id,
                "policy_version": policy_version,
                "resumable_ttl_seconds": resumable_ttl_seconds,
                "sign_batch_size_hint": sign_batch_size_hint,
                "sign_requests_per_upload_limit": sign_requests_per_upload_limit,
                "target_upload_part_count": target_upload_part_count,
            }
        )
        if checksum_algorithm is not UNSET:
            field_dict["checksum_algorithm"] = checksum_algorithm

        return field_dict

    @classmethod
    def from_dict(cls: type[T], src_dict: Mapping[str, Any]) -> T:
        d = dict(src_dict)
        accelerate_enabled = d.pop("accelerate_enabled")

        active_multipart_upload_limit = d.pop("active_multipart_upload_limit")

        checksum_mode = TransferCapabilitiesResponseChecksumMode(
            d.pop("checksum_mode")
        )

        daily_ingress_budget_bytes = d.pop("daily_ingress_budget_bytes")

        large_export_worker_threshold_bytes = d.pop(
            "large_export_worker_threshold_bytes"
        )

        max_concurrency_hint = d.pop("max_concurrency_hint")

        max_upload_bytes = d.pop("max_upload_bytes")

        maximum_part_size_bytes = d.pop("maximum_part_size_bytes")

        minimum_part_size_bytes = d.pop("minimum_part_size_bytes")

        multipart_threshold_bytes = d.pop("multipart_threshold_bytes")

        policy_id = d.pop("policy_id")

        policy_version = d.pop("policy_version")

        resumable_ttl_seconds = d.pop("resumable_ttl_seconds")

        sign_batch_size_hint = d.pop("sign_batch_size_hint")

        sign_requests_per_upload_limit = d.pop("sign_requests_per_upload_limit")

        target_upload_part_count = d.pop("target_upload_part_count")

        def _parse_checksum_algorithm(data: object) -> None | str | Unset:
            if data is None:
                return data
            if isinstance(data, Unset):
                return data
            return cast(None | str | Unset, data)

        checksum_algorithm = _parse_checksum_algorithm(
            d.pop("checksum_algorithm", UNSET)
        )

        transfer_capabilities_response = cls(
            accelerate_enabled=accelerate_enabled,
            active_multipart_upload_limit=active_multipart_upload_limit,
            checksum_mode=checksum_mode,
            daily_ingress_budget_bytes=daily_ingress_budget_bytes,
            large_export_worker_threshold_bytes=large_export_worker_threshold_bytes,
            max_concurrency_hint=max_concurrency_hint,
            max_upload_bytes=max_upload_bytes,
            maximum_part_size_bytes=maximum_part_size_bytes,
            minimum_part_size_bytes=minimum_part_size_bytes,
            multipart_threshold_bytes=multipart_threshold_bytes,
            policy_id=policy_id,
            policy_version=policy_version,
            resumable_ttl_seconds=resumable_ttl_seconds,
            sign_batch_size_hint=sign_batch_size_hint,
            sign_requests_per_upload_limit=sign_requests_per_upload_limit,
            target_upload_part_count=target_upload_part_count,
            checksum_algorithm=checksum_algorithm,
        )

        return transfer_capabilities_response
