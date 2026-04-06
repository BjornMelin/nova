from __future__ import annotations

from collections.abc import Mapping
from typing import (
    Any,
    TypeVar,
    cast,
)

from attrs import define as _attrs_define

from nova_sdk_py.types import UNSET, Unset

T = TypeVar("T", bound="CompletedPart")


@_attrs_define
class CompletedPart:
    """
    Part metadata needed for multipart completion.

    Attributes:
        checksum_sha256: Optional SHA-256 checksum for the completed
        multipart part.
        etag: ETag returned by S3 for the completed multipart part.
        part_number: Multipart part number included in the completion
        request.
    """

    etag: str
    """ETag returned by S3 for the completed multipart part."""
    part_number: int
    """Multipart part number included in the completion request."""
    checksum_sha256: None | str | Unset = UNSET
    """Optional SHA-256 checksum for the completed multipart part."""

    def to_dict(self) -> dict[str, Any]:
        etag = self.etag

        part_number = self.part_number

        checksum_sha256: None | str | Unset
        if isinstance(self.checksum_sha256, Unset):
            checksum_sha256 = UNSET
        else:
            checksum_sha256 = self.checksum_sha256

        field_dict: dict[str, Any] = {}

        field_dict.update(
            {
                "etag": etag,
                "part_number": part_number,
            }
        )
        if checksum_sha256 is not UNSET:
            field_dict["checksum_sha256"] = checksum_sha256

        return field_dict

    @classmethod
    def from_dict(cls: type[T], src_dict: Mapping[str, Any]) -> T:
        d = dict(src_dict)
        etag = d.pop("etag")

        part_number = d.pop("part_number")

        def _parse_checksum_sha256(data: object) -> None | str | Unset:
            if data is None:
                return data
            if isinstance(data, Unset):
                return data
            return cast(None | str | Unset, data)

        checksum_sha256 = _parse_checksum_sha256(
            d.pop("checksum_sha256", UNSET)
        )

        completed_part = cls(
            etag=etag,
            part_number=part_number,
            checksum_sha256=checksum_sha256,
        )

        return completed_part
