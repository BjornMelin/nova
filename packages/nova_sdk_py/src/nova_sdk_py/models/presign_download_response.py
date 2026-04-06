from __future__ import annotations

from collections.abc import Mapping
from typing import Any, TypeVar

from attrs import define as _attrs_define, field as _attrs_field

T = TypeVar("T", bound="PresignDownloadResponse")


@_attrs_define
class PresignDownloadResponse:
    """Presign download response."""

    bucket: str
    expires_in_seconds: int
    key: str
    url: str = _attrs_field(repr=False)

    def to_dict(self) -> dict[str, Any]:
        bucket = self.bucket

        expires_in_seconds = self.expires_in_seconds

        key = self.key

        url = self.url

        field_dict: dict[str, Any] = {}

        field_dict.update(
            {
                "bucket": bucket,
                "expires_in_seconds": expires_in_seconds,
                "key": key,
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

        url = d.pop("url")

        presign_download_response = cls(
            bucket=bucket,
            expires_in_seconds=expires_in_seconds,
            key=key,
            url=url,
        )

        return presign_download_response
