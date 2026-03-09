# ruff: noqa
from __future__ import annotations

from collections.abc import Mapping
from typing import TYPE_CHECKING, Any, TypeVar, cast

from attrs import define as _attrs_define

from nova_sdk_py_file.types import UNSET, Unset

if TYPE_CHECKING:
    from ..models.completed_part import CompletedPart


T = TypeVar("T", bound="CompleteUploadRequest")


@_attrs_define
class CompleteUploadRequest:
    """Multipart completion request.

    Attributes:
        key (str):
        parts (list[CompletedPart]):
        upload_id (str):
        session_id (None | str | Unset):
    """

    key: str
    parts: list[CompletedPart]
    upload_id: str
    session_id: None | str | Unset = UNSET

    def to_dict(self) -> dict[str, Any]:
        key = self.key

        parts = []
        for parts_item_data in self.parts:
            parts_item = parts_item_data.to_dict()
            parts.append(parts_item)

        upload_id = self.upload_id

        session_id: None | str | Unset
        if isinstance(self.session_id, Unset):
            session_id = UNSET
        else:
            session_id = self.session_id

        field_dict: dict[str, Any] = {}

        field_dict.update(
            {
                "key": key,
                "parts": parts,
                "upload_id": upload_id,
            }
        )
        if session_id is not UNSET:
            field_dict["session_id"] = session_id

        return field_dict

    @classmethod
    def from_dict(cls: type[T], src_dict: Mapping[str, Any]) -> T:
        from ..models.completed_part import CompletedPart

        d = dict(src_dict)
        key = d.pop("key")

        parts = []
        _parts = d.pop("parts")
        for parts_item_data in _parts:
            parts_item = CompletedPart.from_dict(parts_item_data)

            parts.append(parts_item)

        upload_id = d.pop("upload_id")

        def _parse_session_id(data: object) -> None | str | Unset:
            if data is None:
                return data
            if isinstance(data, Unset):
                return data
            return cast(None | str | Unset, data)

        session_id = _parse_session_id(d.pop("session_id", UNSET))

        complete_upload_request = cls(
            key=key,
            parts=parts,
            upload_id=upload_id,
            session_id=session_id,
        )

        return complete_upload_request
