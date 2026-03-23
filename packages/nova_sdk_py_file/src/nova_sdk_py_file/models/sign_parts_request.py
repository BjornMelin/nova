from __future__ import annotations

from collections.abc import Mapping
from typing import (
    Any,
    TypeVar,
    cast,
)

from attrs import define as _attrs_define

T = TypeVar("T", bound="SignPartsRequest")


@_attrs_define
class SignPartsRequest:
    """Multipart sign-parts request.

    Attributes:
        key (str):
        part_numbers (list[int]):
        upload_id (str):
    """

    key: str
    part_numbers: list[int]
    upload_id: str

    def to_dict(self) -> dict[str, Any]:
        key = self.key

        part_numbers = self.part_numbers

        upload_id = self.upload_id

        field_dict: dict[str, Any] = {}

        field_dict.update(
            {
                "key": key,
                "part_numbers": part_numbers,
                "upload_id": upload_id,
            }
        )

        return field_dict

    @classmethod
    def from_dict(cls: type[T], src_dict: Mapping[str, Any]) -> T:
        d = dict(src_dict)
        key = d.pop("key")

        part_numbers = cast(list[int], d.pop("part_numbers"))

        upload_id = d.pop("upload_id")

        sign_parts_request = cls(
            key=key,
            part_numbers=part_numbers,
            upload_id=upload_id,
        )

        return sign_parts_request
