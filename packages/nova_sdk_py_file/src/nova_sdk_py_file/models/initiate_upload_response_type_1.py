# ruff: noqa
from __future__ import annotations

from collections.abc import Mapping
from typing import (
    Any,
    Literal,
    TypeVar,
    cast,
)

from attrs import define as _attrs_define

T = TypeVar("T", bound="InitiateUploadResponseType1")


@_attrs_define
class InitiateUploadResponseType1:
    """
    Attributes:
        bucket (str):
        expires_in_seconds (int):
        key (str):
        part_size_bytes (int):
        strategy (Literal['multipart']):
        upload_id (str):
    """

    bucket: str
    expires_in_seconds: int
    key: str
    part_size_bytes: int
    strategy: Literal["multipart"]
    upload_id: str

    def to_dict(self) -> dict[str, Any]:
        bucket = self.bucket

        expires_in_seconds = self.expires_in_seconds

        key = self.key

        part_size_bytes = self.part_size_bytes

        strategy = self.strategy

        upload_id = self.upload_id

        field_dict: dict[str, Any] = {}

        field_dict.update(
            {
                "bucket": bucket,
                "expires_in_seconds": expires_in_seconds,
                "key": key,
                "part_size_bytes": part_size_bytes,
                "strategy": strategy,
                "upload_id": upload_id,
            }
        )

        return field_dict

    @classmethod
    def from_dict(cls: type[T], src_dict: Mapping[str, Any]) -> T:
        d = dict(src_dict)
        bucket = d.pop("bucket")

        expires_in_seconds = d.pop("expires_in_seconds")

        key = d.pop("key")

        part_size_bytes = d.pop("part_size_bytes")

        strategy = cast(Literal["multipart"], d.pop("strategy"))
        if strategy != "multipart":
            raise ValueError(
                f"strategy must match const 'multipart', got '{strategy}'"
            )

        upload_id = d.pop("upload_id")

        initiate_upload_response_type_1 = cls(
            bucket=bucket,
            expires_in_seconds=expires_in_seconds,
            key=key,
            part_size_bytes=part_size_bytes,
            strategy=strategy,
            upload_id=upload_id,
        )

        return initiate_upload_response_type_1
