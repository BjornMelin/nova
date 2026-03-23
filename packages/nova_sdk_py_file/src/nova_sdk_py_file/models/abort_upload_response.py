from __future__ import annotations

from collections.abc import Mapping
from typing import Any, TypeVar

from attrs import define as _attrs_define

from ..types import UNSET, Unset

T = TypeVar("T", bound="AbortUploadResponse")


@_attrs_define
class AbortUploadResponse:
    """Multipart abort response.

    Attributes:
        ok (bool | Unset):  Default: True.
    """

    ok: bool | Unset = True

    def to_dict(self) -> dict[str, Any]:
        ok = self.ok

        field_dict: dict[str, Any] = {}

        field_dict.update({})
        if ok is not UNSET:
            field_dict["ok"] = ok

        return field_dict

    @classmethod
    def from_dict(cls: type[T], src_dict: Mapping[str, Any]) -> T:
        d = dict(src_dict)
        ok = d.pop("ok", UNSET)

        abort_upload_response = cls(
            ok=ok,
        )

        return abort_upload_response
