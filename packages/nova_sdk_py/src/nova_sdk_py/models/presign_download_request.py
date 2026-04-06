from __future__ import annotations

from collections.abc import Mapping
from typing import (
    Any,
    TypeVar,
    cast,
)

from attrs import define as _attrs_define

from nova_sdk_py.types import UNSET, Unset

T = TypeVar("T", bound="PresignDownloadRequest")


@_attrs_define
class PresignDownloadRequest:
    """
    Presign download request.

    Attributes:
        content_disposition: Optional Content-Disposition override for the
        download response.
        content_type: Optional Content-Type override for the download
        response.
        filename: Optional filename hint applied to Content-Disposition.
        key: Storage key of the object to download.
    """

    key: str
    """Storage key of the object to download."""
    content_disposition: None | str | Unset = UNSET
    """Optional Content-Disposition override for the download response."""
    content_type: None | str | Unset = UNSET
    """Optional Content-Type override for the download response."""
    filename: None | str | Unset = UNSET
    """Optional filename hint applied to Content-Disposition."""

    def to_dict(self) -> dict[str, Any]:
        key = self.key

        content_disposition: None | str | Unset
        if isinstance(self.content_disposition, Unset):
            content_disposition = UNSET
        else:
            content_disposition = self.content_disposition

        content_type: None | str | Unset
        if isinstance(self.content_type, Unset):
            content_type = UNSET
        else:
            content_type = self.content_type

        filename: None | str | Unset
        if isinstance(self.filename, Unset):
            filename = UNSET
        else:
            filename = self.filename

        field_dict: dict[str, Any] = {}

        field_dict.update(
            {
                "key": key,
            }
        )
        if content_disposition is not UNSET:
            field_dict["content_disposition"] = content_disposition
        if content_type is not UNSET:
            field_dict["content_type"] = content_type
        if filename is not UNSET:
            field_dict["filename"] = filename

        return field_dict

    @classmethod
    def from_dict(cls: type[T], src_dict: Mapping[str, Any]) -> T:
        d = dict(src_dict)
        key = d.pop("key")

        def _parse_content_disposition(data: object) -> None | str | Unset:
            if data is None:
                return data
            if isinstance(data, Unset):
                return data
            return cast(None | str | Unset, data)

        content_disposition = _parse_content_disposition(
            d.pop("content_disposition", UNSET)
        )

        def _parse_content_type(data: object) -> None | str | Unset:
            if data is None:
                return data
            if isinstance(data, Unset):
                return data
            return cast(None | str | Unset, data)

        content_type = _parse_content_type(d.pop("content_type", UNSET))

        def _parse_filename(data: object) -> None | str | Unset:
            if data is None:
                return data
            if isinstance(data, Unset):
                return data
            return cast(None | str | Unset, data)

        filename = _parse_filename(d.pop("filename", UNSET))

        presign_download_request = cls(
            key=key,
            content_disposition=content_disposition,
            content_type=content_type,
            filename=filename,
        )

        return presign_download_request
