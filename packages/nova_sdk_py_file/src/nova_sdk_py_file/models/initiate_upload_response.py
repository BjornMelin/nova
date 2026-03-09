# ruff: noqa
from __future__ import annotations

from collections.abc import Mapping
from typing import Any, TypeVar, cast

from attrs import define as _attrs_define

from nova_sdk_py_file.models.upload_strategy import UploadStrategy
from nova_sdk_py_file.types import UNSET, Unset

T = TypeVar("T", bound="InitiateUploadResponse")


@_attrs_define
class InitiateUploadResponse:
    """Initiate-upload response model.

    Attributes:
        bucket (str):
        expires_in_seconds (int):
        key (str):
        strategy (UploadStrategy): Upload strategy options returned by initiate endpoint.
        part_size_bytes (int | None | Unset):
        upload_id (None | str | Unset):
        url (None | str | Unset):
    """

    bucket: str
    expires_in_seconds: int
    key: str
    strategy: UploadStrategy
    part_size_bytes: int | None | Unset = UNSET
    upload_id: None | str | Unset = UNSET
    url: None | str | Unset = UNSET

    def to_dict(self) -> dict[str, Any]:
        bucket = self.bucket

        expires_in_seconds = self.expires_in_seconds

        key = self.key

        strategy = self.strategy.value

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
                "bucket": bucket,
                "expires_in_seconds": expires_in_seconds,
                "key": key,
                "strategy": strategy,
            }
        )
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
        bucket = d.pop("bucket")

        expires_in_seconds = d.pop("expires_in_seconds")

        key = d.pop("key")

        strategy = UploadStrategy(d.pop("strategy"))

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
            bucket=bucket,
            expires_in_seconds=expires_in_seconds,
            key=key,
            strategy=strategy,
            part_size_bytes=part_size_bytes,
            upload_id=upload_id,
            url=url,
        )

        return initiate_upload_response
