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

T = TypeVar("T", bound="InitiateUploadResponseType0")


@_attrs_define
class InitiateUploadResponseType0:
    """
    Attributes:
        bucket (str):
        expires_in_seconds (int):
        key (str):
        strategy (Literal['single']):
        url (str):
    """

    bucket: str
    expires_in_seconds: int
    key: str
    strategy: Literal["single"]
    url: str

    def to_dict(self) -> dict[str, Any]:
        bucket = self.bucket

        expires_in_seconds = self.expires_in_seconds

        key = self.key

        strategy = self.strategy

        url = self.url

        field_dict: dict[str, Any] = {}

        field_dict.update(
            {
                "bucket": bucket,
                "expires_in_seconds": expires_in_seconds,
                "key": key,
                "strategy": strategy,
                "url": url,
            }
        )

        return field_dict

    @classmethod
    def from_dict(cls: type[T], src_dict: Mapping[str, Any]) -> T:
        d = dict(src_dict)
        bucket = d.pop("bucket")

        expires_in_seconds = d.pop("expires_in_seconds")

        key = d.pop("key")

        strategy = cast(Literal["single"], d.pop("strategy"))
        if strategy != "single":
            raise ValueError(
                f"strategy must match const 'single', got '{strategy}'"
            )

        url = d.pop("url")

        initiate_upload_response_type_0 = cls(
            bucket=bucket,
            expires_in_seconds=expires_in_seconds,
            key=key,
            strategy=strategy,
            url=url,
        )

        return initiate_upload_response_type_0
