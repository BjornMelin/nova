from __future__ import annotations

from collections.abc import Mapping
from typing import Any, TypeVar

from attrs import define as _attrs_define

T = TypeVar("T", bound="UploadedPart")


@_attrs_define
class UploadedPart:
    """
    Part state returned for multipart upload introspection.

    Attributes:
        etag: ETag returned by S3 for the uploaded multipart part.
        part_number: Multipart part number that has already been uploaded.
    """

    etag: str
    """ ETag returned by S3 for the uploaded multipart part. """
    part_number: int
    """ Multipart part number that has already been uploaded. """

    def to_dict(self) -> dict[str, Any]:
        etag = self.etag

        part_number = self.part_number

        field_dict: dict[str, Any] = {}

        field_dict.update(
            {
                "etag": etag,
                "part_number": part_number,
            }
        )

        return field_dict

    @classmethod
    def from_dict(cls: type[T], src_dict: Mapping[str, Any]) -> T:
        d = dict(src_dict)
        etag = d.pop("etag")

        part_number = d.pop("part_number")

        uploaded_part = cls(
            etag=etag,
            part_number=part_number,
        )

        return uploaded_part
