from __future__ import annotations

import datetime
from collections.abc import Mapping
from typing import (
    Any,
    TypeVar,
    cast,
)

from attrs import define as _attrs_define, field as _attrs_field
from dateutil.parser import isoparse

from nova_sdk_py.models.initiate_upload_response_checksum_mode import (
    InitiateUploadResponseChecksumMode,
)
from nova_sdk_py.models.upload_strategy import UploadStrategy
from nova_sdk_py.types import UNSET, Unset

T = TypeVar("T", bound="InitiateUploadResponse")


@_attrs_define
class InitiateUploadResponse:
    """Initiate-upload response model."""

    accelerate_enabled: bool
    bucket: str
    checksum_mode: InitiateUploadResponseChecksumMode
    expires_in_seconds: int
    key: str
    max_concurrency_hint: int
    policy_id: str
    policy_version: str
    resumable_until: datetime.datetime
    session_id: str
    sign_batch_size_hint: int
    strategy: UploadStrategy
    """ Upload strategy options returned by initiate endpoint. """
    checksum_algorithm: None | str | Unset = UNSET
    part_size_bytes: int | None | Unset = UNSET
    upload_id: None | str | Unset = UNSET
    url: None | str | Unset = _attrs_field(default=UNSET, repr=False)

    def to_dict(self) -> dict[str, Any]:
        accelerate_enabled = self.accelerate_enabled

        bucket = self.bucket

        checksum_mode = self.checksum_mode.value

        expires_in_seconds = self.expires_in_seconds

        key = self.key

        max_concurrency_hint = self.max_concurrency_hint

        policy_id = self.policy_id

        policy_version = self.policy_version

        resumable_until = self.resumable_until.isoformat()

        session_id = self.session_id

        sign_batch_size_hint = self.sign_batch_size_hint

        strategy = self.strategy.value

        checksum_algorithm: None | str | Unset
        if isinstance(self.checksum_algorithm, Unset):
            checksum_algorithm = UNSET
        else:
            checksum_algorithm = self.checksum_algorithm

        part_size_bytes: int | None | Unset
        if isinstance(self.part_size_bytes, Unset):
            part_size_bytes = UNSET
        else:
            part_size_bytes = self.part_size_bytes

        upload_id: None | str | Unset
        if isinstance(self.upload_id, Unset):
            upload_id = UNSET
        else:
            upload_id = self.upload_id

        url: None | str | Unset
        if isinstance(self.url, Unset):
            url = UNSET
        else:
            url = self.url

        field_dict: dict[str, Any] = {}

        field_dict.update(
            {
                "accelerate_enabled": accelerate_enabled,
                "bucket": bucket,
                "checksum_mode": checksum_mode,
                "expires_in_seconds": expires_in_seconds,
                "key": key,
                "max_concurrency_hint": max_concurrency_hint,
                "policy_id": policy_id,
                "policy_version": policy_version,
                "resumable_until": resumable_until,
                "session_id": session_id,
                "sign_batch_size_hint": sign_batch_size_hint,
                "strategy": strategy,
            }
        )
        if checksum_algorithm is not UNSET:
            field_dict["checksum_algorithm"] = checksum_algorithm
        if part_size_bytes is not UNSET:
            field_dict["part_size_bytes"] = part_size_bytes
        if upload_id is not UNSET:
            field_dict["upload_id"] = upload_id
        if url is not UNSET:
            field_dict["url"] = url

        return field_dict

    @classmethod
    def from_dict(cls: type[T], src_dict: Mapping[str, Any]) -> T:
        d = dict(src_dict)
        accelerate_enabled = d.pop("accelerate_enabled")

        bucket = d.pop("bucket")

        checksum_mode = InitiateUploadResponseChecksumMode(
            d.pop("checksum_mode")
        )

        expires_in_seconds = d.pop("expires_in_seconds")

        key = d.pop("key")

        max_concurrency_hint = d.pop("max_concurrency_hint")

        policy_id = d.pop("policy_id")

        policy_version = d.pop("policy_version")

        resumable_until = isoparse(d.pop("resumable_until"))

        session_id = d.pop("session_id")

        sign_batch_size_hint = d.pop("sign_batch_size_hint")

        strategy = UploadStrategy(d.pop("strategy"))

        def _parse_checksum_algorithm(data: object) -> None | str | Unset:
            if data is None:
                return data
            if isinstance(data, Unset):
                return data
            return cast(None | str | Unset, data)

        checksum_algorithm = _parse_checksum_algorithm(
            d.pop("checksum_algorithm", UNSET)
        )

        def _parse_part_size_bytes(data: object) -> int | None | Unset:
            if data is None:
                return data
            if isinstance(data, Unset):
                return data
            return cast(int | None | Unset, data)

        part_size_bytes = _parse_part_size_bytes(
            d.pop("part_size_bytes", UNSET)
        )

        def _parse_upload_id(data: object) -> None | str | Unset:
            if data is None:
                return data
            if isinstance(data, Unset):
                return data
            return cast(None | str | Unset, data)

        upload_id = _parse_upload_id(d.pop("upload_id", UNSET))

        def _parse_url(data: object) -> None | str | Unset:
            if data is None:
                return data
            if isinstance(data, Unset):
                return data
            return cast(None | str | Unset, data)

        url = _parse_url(d.pop("url", UNSET))

        initiate_upload_response = cls(
            accelerate_enabled=accelerate_enabled,
            bucket=bucket,
            checksum_mode=checksum_mode,
            expires_in_seconds=expires_in_seconds,
            key=key,
            max_concurrency_hint=max_concurrency_hint,
            policy_id=policy_id,
            policy_version=policy_version,
            resumable_until=resumable_until,
            session_id=session_id,
            sign_batch_size_hint=sign_batch_size_hint,
            strategy=strategy,
            checksum_algorithm=checksum_algorithm,
            part_size_bytes=part_size_bytes,
            upload_id=upload_id,
            url=url,
        )

        return initiate_upload_response
