from __future__ import annotations

from collections.abc import Mapping
from typing import (
    Any,
    TypeVar,
    cast,
)

from attrs import define as _attrs_define

from nova_sdk_py.types import UNSET, Unset

T = TypeVar("T", bound="TransferCapabilitiesResponse")


@_attrs_define
class TransferCapabilitiesResponse:
    """Transfer policy capabilities exposed to clients and operators.

    Attributes:
        accelerate_enabled (bool):
        max_concurrency_hint (int):
        max_upload_bytes (int):
        maximum_part_size_bytes (int):
        minimum_part_size_bytes (int):
        multipart_threshold_bytes (int):
        policy_id (str):
        policy_version (str):
        resumable_ttl_seconds (int):
        sign_batch_size_hint (int):
        target_upload_part_count (int):
        active_multipart_upload_limit (int | None | Unset):
        checksum_algorithm (None | str | Unset):
        daily_ingress_budget_bytes (int | None | Unset):
        sign_requests_per_upload_limit (int | None | Unset):
    """

    accelerate_enabled: bool
    max_concurrency_hint: int
    max_upload_bytes: int
    maximum_part_size_bytes: int
    minimum_part_size_bytes: int
    multipart_threshold_bytes: int
    policy_id: str
    policy_version: str
    resumable_ttl_seconds: int
    sign_batch_size_hint: int
    target_upload_part_count: int
    active_multipart_upload_limit: int | None | Unset = UNSET
    checksum_algorithm: None | str | Unset = UNSET
    daily_ingress_budget_bytes: int | None | Unset = UNSET
    sign_requests_per_upload_limit: int | None | Unset = UNSET

    def to_dict(self) -> dict[str, Any]:
        accelerate_enabled = self.accelerate_enabled

        max_concurrency_hint = self.max_concurrency_hint

        max_upload_bytes = self.max_upload_bytes

        maximum_part_size_bytes = self.maximum_part_size_bytes

        minimum_part_size_bytes = self.minimum_part_size_bytes

        multipart_threshold_bytes = self.multipart_threshold_bytes

        policy_id = self.policy_id

        policy_version = self.policy_version

        resumable_ttl_seconds = self.resumable_ttl_seconds

        sign_batch_size_hint = self.sign_batch_size_hint

        target_upload_part_count = self.target_upload_part_count

        active_multipart_upload_limit: int | None | Unset
        if isinstance(self.active_multipart_upload_limit, Unset):
            active_multipart_upload_limit = UNSET
        else:
            active_multipart_upload_limit = self.active_multipart_upload_limit

        checksum_algorithm: None | str | Unset
        if isinstance(self.checksum_algorithm, Unset):
            checksum_algorithm = UNSET
        else:
            checksum_algorithm = self.checksum_algorithm

        daily_ingress_budget_bytes: int | None | Unset
        if isinstance(self.daily_ingress_budget_bytes, Unset):
            daily_ingress_budget_bytes = UNSET
        else:
            daily_ingress_budget_bytes = self.daily_ingress_budget_bytes

        sign_requests_per_upload_limit: int | None | Unset
        if isinstance(self.sign_requests_per_upload_limit, Unset):
            sign_requests_per_upload_limit = UNSET
        else:
            sign_requests_per_upload_limit = self.sign_requests_per_upload_limit

        field_dict: dict[str, Any] = {}

        field_dict.update(
            {
                "accelerate_enabled": accelerate_enabled,
                "max_concurrency_hint": max_concurrency_hint,
                "max_upload_bytes": max_upload_bytes,
                "maximum_part_size_bytes": maximum_part_size_bytes,
                "minimum_part_size_bytes": minimum_part_size_bytes,
                "multipart_threshold_bytes": multipart_threshold_bytes,
                "policy_id": policy_id,
                "policy_version": policy_version,
                "resumable_ttl_seconds": resumable_ttl_seconds,
                "sign_batch_size_hint": sign_batch_size_hint,
                "target_upload_part_count": target_upload_part_count,
            }
        )
        if active_multipart_upload_limit is not UNSET:
            field_dict["active_multipart_upload_limit"] = (
                active_multipart_upload_limit
            )
        if checksum_algorithm is not UNSET:
            field_dict["checksum_algorithm"] = checksum_algorithm
        if daily_ingress_budget_bytes is not UNSET:
            field_dict["daily_ingress_budget_bytes"] = (
                daily_ingress_budget_bytes
            )
        if sign_requests_per_upload_limit is not UNSET:
            field_dict["sign_requests_per_upload_limit"] = (
                sign_requests_per_upload_limit
            )

        return field_dict

    @classmethod
    def from_dict(cls: type[T], src_dict: Mapping[str, Any]) -> T:
        d = dict(src_dict)
        accelerate_enabled = d.pop("accelerate_enabled")

        max_concurrency_hint = d.pop("max_concurrency_hint")

        max_upload_bytes = d.pop("max_upload_bytes")

        maximum_part_size_bytes = d.pop("maximum_part_size_bytes")

        minimum_part_size_bytes = d.pop("minimum_part_size_bytes")

        multipart_threshold_bytes = d.pop("multipart_threshold_bytes")

        policy_id = d.pop("policy_id")

        policy_version = d.pop("policy_version")

        resumable_ttl_seconds = d.pop("resumable_ttl_seconds")

        sign_batch_size_hint = d.pop("sign_batch_size_hint")

        target_upload_part_count = d.pop("target_upload_part_count")

        def _parse_active_multipart_upload_limit(
            data: object,
        ) -> int | None | Unset:
            if data is None:
                return data
            if isinstance(data, Unset):
                return data
            return cast(int | None | Unset, data)

        active_multipart_upload_limit = _parse_active_multipart_upload_limit(
            d.pop("active_multipart_upload_limit", UNSET)
        )

        def _parse_checksum_algorithm(data: object) -> None | str | Unset:
            if data is None:
                return data
            if isinstance(data, Unset):
                return data
            return cast(None | str | Unset, data)

        checksum_algorithm = _parse_checksum_algorithm(
            d.pop("checksum_algorithm", UNSET)
        )

        def _parse_daily_ingress_budget_bytes(
            data: object,
        ) -> int | None | Unset:
            if data is None:
                return data
            if isinstance(data, Unset):
                return data
            return cast(int | None | Unset, data)

        daily_ingress_budget_bytes = _parse_daily_ingress_budget_bytes(
            d.pop("daily_ingress_budget_bytes", UNSET)
        )

        def _parse_sign_requests_per_upload_limit(
            data: object,
        ) -> int | None | Unset:
            if data is None:
                return data
            if isinstance(data, Unset):
                return data
            return cast(int | None | Unset, data)

        sign_requests_per_upload_limit = _parse_sign_requests_per_upload_limit(
            d.pop("sign_requests_per_upload_limit", UNSET)
        )

        transfer_capabilities_response = cls(
            accelerate_enabled=accelerate_enabled,
            max_concurrency_hint=max_concurrency_hint,
            max_upload_bytes=max_upload_bytes,
            maximum_part_size_bytes=maximum_part_size_bytes,
            minimum_part_size_bytes=minimum_part_size_bytes,
            multipart_threshold_bytes=multipart_threshold_bytes,
            policy_id=policy_id,
            policy_version=policy_version,
            resumable_ttl_seconds=resumable_ttl_seconds,
            sign_batch_size_hint=sign_batch_size_hint,
            target_upload_part_count=target_upload_part_count,
            active_multipart_upload_limit=active_multipart_upload_limit,
            checksum_algorithm=checksum_algorithm,
            daily_ingress_budget_bytes=daily_ingress_budget_bytes,
            sign_requests_per_upload_limit=sign_requests_per_upload_limit,
        )

        return transfer_capabilities_response
