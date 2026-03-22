# ruff: noqa
from __future__ import annotations

from collections.abc import Mapping
from typing import TYPE_CHECKING, Any, TypeVar, cast

from attrs import define as _attrs_define

from nova_sdk_py_file.types import UNSET, Unset

if TYPE_CHECKING:
    from ..models.error_body_details import ErrorBodyDetails


T = TypeVar("T", bound="ErrorBody")


@_attrs_define
class ErrorBody:
    """Standard API error body.

    Attributes:
        code (str):
        message (str):
        details (ErrorBodyDetails | Unset):
        request_id (None | str | Unset):
    """

    code: str
    message: str
    details: ErrorBodyDetails | Unset = UNSET
    request_id: None | str | Unset = UNSET

    def to_dict(self) -> dict[str, Any]:
        code = self.code

        message = self.message

        details: dict[str, Any] | Unset = UNSET
        if not isinstance(self.details, Unset):
            details = self.details.to_dict()

        request_id: None | str | Unset
        if isinstance(self.request_id, Unset):
            request_id = UNSET
        else:
            request_id = self.request_id

        field_dict: dict[str, Any] = {}

        field_dict.update(
            {
                "code": code,
                "message": message,
            }
        )
        if details is not UNSET:
            field_dict["details"] = details
        if request_id is not UNSET:
            field_dict["request_id"] = request_id

        return field_dict

    @classmethod
    def from_dict(cls: type[T], src_dict: Mapping[str, Any]) -> T:
        from ..models.error_body_details import ErrorBodyDetails

        d = dict(src_dict)
        code = d.pop("code")

        message = d.pop("message")

        _details = d.pop("details", UNSET)
        details: ErrorBodyDetails | Unset
        if isinstance(_details, Unset):
            details = UNSET
        else:
            details = ErrorBodyDetails.from_dict(_details)

        def _parse_request_id(data: object) -> None | str | Unset:
            if data is None:
                return data
            if isinstance(data, Unset):
                return data
            return cast(None | str | Unset, data)

        request_id = _parse_request_id(d.pop("request_id", UNSET))

        error_body = cls(
            code=code,
            message=message,
            details=details,
            request_id=request_id,
        )

        return error_body
