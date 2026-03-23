from __future__ import annotations

from collections.abc import Mapping
from typing import Any, TypeVar

from attrs import define as _attrs_define
from attrs import field as _attrs_field

T = TypeVar("T", bound="SignPartsResponseUrls")


@_attrs_define
class SignPartsResponseUrls:
    """Signed upload-part URLs returned by the API."""

    additional_properties: dict[str, str] = _attrs_field(
        init=False, factory=dict
    )

    def to_dict(self) -> dict[str, Any]:

        field_dict: dict[str, Any] = {}
        field_dict.update(self.additional_properties)

        return field_dict

    @classmethod
    def from_dict(cls: type[T], src_dict: Mapping[str, Any]) -> T:
        d = dict(src_dict)
        sign_parts_response_urls = cls()
        additional_properties: dict[str, str] = {}
        for key, value in d.items():
            if not isinstance(value, str):
                raise TypeError(
                    f"Invalid value for {key!r}: expected str, got {type(value).__name__}"
                )
            additional_properties[key] = value

        sign_parts_response_urls.additional_properties = additional_properties
        return sign_parts_response_urls

    @property
    def additional_keys(self) -> list[str]:
        return list(self.additional_properties.keys())

    def __getitem__(self, key: str) -> str:
        return self.additional_properties[key]

    def __setitem__(self, key: str, value: str) -> None:
        self.additional_properties[key] = value

    def __delitem__(self, key: str) -> None:
        del self.additional_properties[key]

    def __contains__(self, key: str) -> bool:
        return key in self.additional_properties
