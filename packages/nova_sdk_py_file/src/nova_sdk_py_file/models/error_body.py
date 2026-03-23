from __future__ import annotations

from collections.abc import Mapping
from typing import (
    TYPE_CHECKING,
    Any,
    TypeVar,
    cast,
)

from attrs import define as _attrs_define

if TYPE_CHECKING:
    from nova_sdk_py_file.models.error_body_details import ErrorBodyDetails


T = TypeVar("T", bound="ErrorBody")


@_attrs_define
class ErrorBody:
    """Standard API error body.

    Attributes:
        code (str):
        details (ErrorBodyDetails):
        message (str):
        request_id (None | str):
    """

    code: str
    details: ErrorBodyDetails
    message: str
    request_id: None | str

    def to_dict(self) -> dict[str, Any]:
        code = self.code

        details = self.details.to_dict()

        message = self.message

        request_id: None | str
        request_id = self.request_id

        field_dict: dict[str, Any] = {}

        field_dict.update(
            {
                "code": code,
                "details": details,
                "message": message,
                "request_id": request_id,
            }
        )

        return field_dict

    @classmethod
    def from_dict(cls: type[T], src_dict: Mapping[str, Any]) -> T:
        from nova_sdk_py_file.models.error_body_details import ErrorBodyDetails

        d = dict(src_dict)
        code = d.pop("code")

        details = ErrorBodyDetails.from_dict(d.pop("details"))

        message = d.pop("message")

        def _parse_request_id(data: object) -> None | str:
            if data is None:
                return data
            return cast(None | str, data)

        request_id = _parse_request_id(d.pop("request_id"))

        error_body = cls(
            code=code,
            details=details,
            message=message,
            request_id=request_id,
        )

        return error_body
