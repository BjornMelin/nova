# ruff: noqa
"""Error envelope body model for file API SDK responses."""

from __future__ import annotations

from collections.abc import Mapping
from typing import TYPE_CHECKING, Any, TypeVar, cast

from attrs import define as _attrs_define
from attrs import field as _attrs_field

from nova_sdk_py_file.types import UNSET, Unset

if TYPE_CHECKING:
    from ..models.error_envelope_error_details import ErrorEnvelopeErrorDetails


T = TypeVar("T", bound="ErrorEnvelopeError")


@_attrs_define
class ErrorEnvelopeError:
    """
    Attributes:
        code (str):
        message (str):
        details (ErrorEnvelopeErrorDetails | Unset):
        request_id (None | str | Unset):
    """

    code: str
    message: str
    details: ErrorEnvelopeErrorDetails | Unset = UNSET
    request_id: None | str | Unset = UNSET
    additional_properties: dict[str, Any] = _attrs_field(
        init=False, factory=dict
    )

    def to_dict(self) -> dict[str, Any]:
        """Serialize this model to a JSON-compatible dict."""
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
        field_dict.update(self.additional_properties)
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
        """Build this model from a JSON-compatible mapping."""
        from ..models.error_envelope_error_details import (
            ErrorEnvelopeErrorDetails,
        )

        d = dict(src_dict)
        code = d.pop("code")

        message = d.pop("message")

        _details = d.pop("details", UNSET)
        details: ErrorEnvelopeErrorDetails | Unset
        if isinstance(_details, Unset):
            details = UNSET
        else:
            details = ErrorEnvelopeErrorDetails.from_dict(_details)

        def _parse_request_id(data: object) -> None | str | Unset:
            if data is None:
                return data
            if isinstance(data, Unset):
                return data
            return cast(None | str | Unset, data)

        request_id = _parse_request_id(d.pop("request_id", UNSET))

        error_envelope_error = cls(
            code=code,
            message=message,
            details=details,
            request_id=request_id,
        )

        error_envelope_error.additional_properties = d
        return error_envelope_error

    @property
    def additional_keys(self) -> list[str]:
        return list(self.additional_properties.keys())

    def __getitem__(self, key: str) -> Any:
        return self.additional_properties[key]

    def __setitem__(self, key: str, value: Any) -> None:
        self.additional_properties[key] = value

    def __delitem__(self, key: str) -> None:
        del self.additional_properties[key]

    def __contains__(self, key: str) -> bool:
        return key in self.additional_properties
