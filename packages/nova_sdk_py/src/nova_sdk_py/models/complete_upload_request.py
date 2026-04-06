from __future__ import annotations

from collections.abc import Mapping
from typing import (
    TYPE_CHECKING,
    Any,
    TypeVar,
)

from attrs import define as _attrs_define

if TYPE_CHECKING:
    from nova_sdk_py.models.completed_part import CompletedPart


T = TypeVar("T", bound="CompleteUploadRequest")


@_attrs_define
class CompleteUploadRequest:
    """
    Multipart completion request.

    Attributes:
        key: Storage key reserved for the multipart upload.
        parts: Ordered multipart parts to finalize in S3.
        upload_id: S3 multipart upload identifier being finalized.
    """

    key: str
    """ Storage key reserved for the multipart upload. """
    parts: list[CompletedPart]
    """ Ordered multipart parts to finalize in S3. """
    upload_id: str
    """ S3 multipart upload identifier being finalized. """

    def to_dict(self) -> dict[str, Any]:
        key = self.key

        parts = []
        for parts_item_data in self.parts:
            parts_item = parts_item_data.to_dict()
            parts.append(parts_item)

        upload_id = self.upload_id

        field_dict: dict[str, Any] = {}

        field_dict.update(
            {
                "key": key,
                "parts": parts,
                "upload_id": upload_id,
            }
        )

        return field_dict

    @classmethod
    def from_dict(cls: type[T], src_dict: Mapping[str, Any]) -> T:
        from nova_sdk_py.models.completed_part import CompletedPart

        d = dict(src_dict)
        key = d.pop("key")

        parts = []
        _parts = d.pop("parts")
        for parts_item_data in _parts:
            parts_item = CompletedPart.from_dict(parts_item_data)

            parts.append(parts_item)

        upload_id = d.pop("upload_id")

        complete_upload_request = cls(
            key=key,
            parts=parts,
            upload_id=upload_id,
        )

        return complete_upload_request
