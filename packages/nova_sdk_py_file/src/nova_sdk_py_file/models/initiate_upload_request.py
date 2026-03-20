# ruff: noqa
from __future__ import annotations

from collections.abc import Mapping
from typing import Any, TypeVar, cast

from attrs import define as _attrs_define

from nova_sdk_py_file.types import UNSET, Unset

T = TypeVar("T", bound="InitiateUploadRequest")


@_attrs_define
class InitiateUploadRequest:
    """Initiate-upload request model.

    Attributes:
        filename (str):
        size_bytes (int):
        content_type (None | str | Unset):
    """

    filename: str
    size_bytes: int
    content_type: None | str | Unset = UNSET

    def to_dict(self) -> dict[str, Any]:
        filename = self.filename

        size_bytes = self.size_bytes

        content_type: None | str | Unset
        if isinstance(self.content_type, Unset):
            content_type = UNSET
        else:
            content_type = self.content_type

        field_dict: dict[str, Any] = {}

        field_dict.update(
            {
                "filename": filename,
                "size_bytes": size_bytes,
            }
        )
        if content_type is not UNSET:
            field_dict["content_type"] = content_type

        return field_dict

    @classmethod
    def from_dict(cls: type[T], src_dict: Mapping[str, Any]) -> T:
        d = dict(src_dict)
        filename = d.pop("filename")

        size_bytes = d.pop("size_bytes")

        def _parse_content_type(data: object) -> None | str | Unset:
            if data is None:
                return data
            if isinstance(data, Unset):
                return data
            return cast(None | str | Unset, data)

        content_type = _parse_content_type(d.pop("content_type", UNSET))

        initiate_upload_request = cls(
            filename=filename,
            size_bytes=size_bytes,
            content_type=content_type,
        )

        return initiate_upload_request
