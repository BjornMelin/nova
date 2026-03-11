# ruff: noqa
from __future__ import annotations

from collections.abc import Mapping
from typing import TYPE_CHECKING, Any, TypeVar

from attrs import define as _attrs_define

from nova_sdk_py_file.types import UNSET, Unset

if TYPE_CHECKING:
    from ..models.uploaded_part import UploadedPart


T = TypeVar("T", bound="UploadIntrospectionResponse")


@_attrs_define
class UploadIntrospectionResponse:
    """Multipart upload introspection response.

    Attributes:
        bucket (str):
        key (str):
        part_size_bytes (int):
        upload_id (str):
        parts (list[UploadedPart] | Unset):
    """

    bucket: str
    key: str
    part_size_bytes: int
    upload_id: str
    parts: list[UploadedPart] | Unset = UNSET

    def to_dict(self) -> dict[str, Any]:
        bucket = self.bucket

        key = self.key

        part_size_bytes = self.part_size_bytes

        upload_id = self.upload_id

        parts: list[dict[str, Any]] | Unset = UNSET
        if not isinstance(self.parts, Unset):
            parts = []
            for parts_item_data in self.parts:
                parts_item = parts_item_data.to_dict()
                parts.append(parts_item)

        field_dict: dict[str, Any] = {}

        field_dict.update(
            {
                "bucket": bucket,
                "key": key,
                "part_size_bytes": part_size_bytes,
                "upload_id": upload_id,
            }
        )
        if parts is not UNSET:
            field_dict["parts"] = parts

        return field_dict

    @classmethod
    def from_dict(cls: type[T], src_dict: Mapping[str, Any]) -> T:
        from ..models.uploaded_part import UploadedPart

        d = dict(src_dict)
        bucket = d.pop("bucket")

        key = d.pop("key")

        part_size_bytes = d.pop("part_size_bytes")

        upload_id = d.pop("upload_id")

        _parts = d.pop("parts", UNSET)
        parts: list[UploadedPart] | Unset = UNSET
        if _parts is not UNSET:
            parts = []
            for parts_item_data in _parts:
                parts_item = UploadedPart.from_dict(parts_item_data)

                parts.append(parts_item)

        upload_introspection_response = cls(
            bucket=bucket,
            key=key,
            part_size_bytes=part_size_bytes,
            upload_id=upload_id,
            parts=parts,
        )

        return upload_introspection_response
