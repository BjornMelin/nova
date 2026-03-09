# ruff: noqa
from __future__ import annotations

from collections.abc import Mapping
from typing import Any, TypeVar, cast

from attrs import define as _attrs_define

from nova_sdk_py_file.types import UNSET, Unset

T = TypeVar("T", bound="CompleteUploadResponse")


@_attrs_define
class CompleteUploadResponse:
    """Multipart completion response.

    Attributes:
        bucket (str):
        key (str):
        etag (None | str | Unset): Entity tag for the completed object.
        version_id (None | str | Unset): Version identifier when bucket versioning is enabled.
    """

    bucket: str
    key: str
    etag: None | str | Unset = UNSET
    version_id: None | str | Unset = UNSET

    def to_dict(self) -> dict[str, Any]:
        bucket = self.bucket

        key = self.key

        etag: None | str | Unset
        if isinstance(self.etag, Unset):
            etag = UNSET
        else:
            etag = self.etag

        version_id: None | str | Unset
        if isinstance(self.version_id, Unset):
            version_id = UNSET
        else:
            version_id = self.version_id

        field_dict: dict[str, Any] = {}

        field_dict.update(
            {
                "bucket": bucket,
                "key": key,
            }
        )
        if etag is not UNSET:
            field_dict["etag"] = etag
        if version_id is not UNSET:
            field_dict["version_id"] = version_id

        return field_dict

    @classmethod
    def from_dict(cls: type[T], src_dict: Mapping[str, Any]) -> T:
        d = dict(src_dict)
        bucket = d.pop("bucket")

        key = d.pop("key")

        def _parse_optional_string(data: object) -> None | str | Unset:
            if data is None:
                return data
            if isinstance(data, Unset):
                return data
            return cast(None | str | Unset, data)

        etag = _parse_optional_string(d.pop("etag", UNSET))
        version_id = _parse_optional_string(d.pop("version_id", UNSET))

        complete_upload_response = cls(
            bucket=bucket,
            key=key,
            etag=etag,
            version_id=version_id,
        )

        return complete_upload_response
