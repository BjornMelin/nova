from __future__ import annotations

from collections.abc import Mapping
from typing import (
    TYPE_CHECKING,
    Any,
    TypeVar,
)

from attrs import define as _attrs_define

if TYPE_CHECKING:
    from nova_sdk_py.models.uploaded_part import UploadedPart


T = TypeVar("T", bound="UploadIntrospectionResponse")


@_attrs_define
class UploadIntrospectionResponse:
    """
    Multipart upload introspection response.

    Attributes:
        bucket: Bucket that owns the multipart upload.
        key: Storage key reserved for the multipart upload.
        part_size_bytes: Configured multipart part size in bytes for this
        session.
        parts: Multipart parts that have already been uploaded.
        upload_id: S3 multipart upload identifier.
    """

    bucket: str
    """Bucket that owns the multipart upload."""
    key: str
    """Storage key reserved for the multipart upload."""
    part_size_bytes: int
    """Configured multipart part size in bytes for this session."""
    parts: list[UploadedPart]
    """Multipart parts that have already been uploaded."""
    upload_id: str
    """S3 multipart upload identifier."""

    def to_dict(self) -> dict[str, Any]:
        bucket = self.bucket

        key = self.key

        part_size_bytes = self.part_size_bytes

        parts = []
        for parts_item_data in self.parts:
            parts_item = parts_item_data.to_dict()
            parts.append(parts_item)

        upload_id = self.upload_id

        field_dict: dict[str, Any] = {}

        field_dict.update(
            {
                "bucket": bucket,
                "key": key,
                "part_size_bytes": part_size_bytes,
                "parts": parts,
                "upload_id": upload_id,
            }
        )

        return field_dict

    @classmethod
    def from_dict(cls: type[T], src_dict: Mapping[str, Any]) -> T:
        from nova_sdk_py.models.uploaded_part import UploadedPart

        d = dict(src_dict)
        bucket = d.pop("bucket")

        key = d.pop("key")

        part_size_bytes = d.pop("part_size_bytes")

        parts = []
        _parts = d.pop("parts")
        for parts_item_data in _parts:
            parts_item = UploadedPart.from_dict(parts_item_data)

            parts.append(parts_item)

        upload_id = d.pop("upload_id")

        upload_introspection_response = cls(
            bucket=bucket,
            key=key,
            part_size_bytes=part_size_bytes,
            parts=parts,
            upload_id=upload_id,
        )

        return upload_introspection_response
