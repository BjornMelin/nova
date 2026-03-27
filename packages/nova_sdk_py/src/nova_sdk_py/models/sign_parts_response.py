from __future__ import annotations

from collections.abc import Mapping
from typing import (
    TYPE_CHECKING,
    Any,
    TypeVar,
)

from attrs import define as _attrs_define

if TYPE_CHECKING:
    from ..models.sign_parts_response_urls import SignPartsResponseUrls


T = TypeVar("T", bound="SignPartsResponse")


@_attrs_define
class SignPartsResponse:
    """Multipart sign-parts response.

    Attributes:
        expires_in_seconds (int):
        urls (SignPartsResponseUrls):
    """

    expires_in_seconds: int
    urls: SignPartsResponseUrls

    def to_dict(self) -> dict[str, Any]:
        expires_in_seconds = self.expires_in_seconds

        urls = self.urls.to_dict()

        field_dict: dict[str, Any] = {}

        field_dict.update(
            {
                "expires_in_seconds": expires_in_seconds,
                "urls": urls,
            }
        )

        return field_dict

    @classmethod
    def from_dict(cls: type[T], src_dict: Mapping[str, Any]) -> T:
        from ..models.sign_parts_response_urls import SignPartsResponseUrls

        d = dict(src_dict)
        expires_in_seconds = d.pop("expires_in_seconds")

        urls = SignPartsResponseUrls.from_dict(d.pop("urls"))

        sign_parts_response = cls(
            expires_in_seconds=expires_in_seconds,
            urls=urls,
        )

        return sign_parts_response
