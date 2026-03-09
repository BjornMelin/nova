# ruff: noqa
from __future__ import annotations

from collections.abc import Mapping
from typing import Any, TypeVar, cast

from attrs import define as _attrs_define

from ..types import UNSET, Unset

T = TypeVar("T", bound="AbortUploadRequest")


@_attrs_define
class AbortUploadRequest:
    """Multipart abort request.

    Attributes:
        key (str):
        upload_id (str):
        session_id (None | str | Unset):
    """

    key: str
    upload_id: str
    session_id: None | str | Unset = UNSET

    def to_dict(self) -> dict[str, Any]:
        key = self.key

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
                "upload_id": upload_id,
            }
        )
        if session_id is not UNSET:
            field_dict["session_id"] = session_id

        return field_dict

    @classmethod
    def from_dict(cls: type[T], src_dict: Mapping[str, Any]) -> T:
        d = dict(src_dict)
        key = d.pop("key")

        upload_id = d.pop("upload_id")

        def _parse_session_id(data: object) -> None | str | Unset:
            if data is None:
                return data
            if isinstance(data, Unset):
                return data
            return cast(None | str | Unset, data)

        session_id = _parse_session_id(d.pop("session_id", UNSET))

        abort_upload_request = cls(
            key=key,
            upload_id=upload_id,
            session_id=session_id,
        )

        return abort_upload_request
