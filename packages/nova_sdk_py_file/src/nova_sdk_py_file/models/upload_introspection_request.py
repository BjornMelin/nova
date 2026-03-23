from __future__ import annotations

from collections.abc import Mapping
from typing import Any, TypeVar

from attrs import define as _attrs_define

T = TypeVar("T", bound="UploadIntrospectionRequest")


@_attrs_define
class UploadIntrospectionRequest:
    """Multipart upload introspection request.

    Attributes:
        key (str):
        upload_id (str):
    """

    key: str
    upload_id: str

    def to_dict(self) -> dict[str, Any]:
        key = self.key

        upload_id = self.upload_id

        field_dict: dict[str, Any] = {}

        field_dict.update(
            {
                "key": key,
                "upload_id": upload_id,
            }
        )

        return field_dict

    @classmethod
    def from_dict(cls: type[T], src_dict: Mapping[str, Any]) -> T:
        d = dict(src_dict)
        key = d.pop("key")

        upload_id = d.pop("upload_id")

        upload_introspection_request = cls(
            key=key,
            upload_id=upload_id,
        )

        return upload_introspection_request
