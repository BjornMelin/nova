from __future__ import annotations

from collections.abc import Mapping
from typing import (
    TYPE_CHECKING,
    Any,
    TypeVar,
)

from attrs import define as _attrs_define

if TYPE_CHECKING:
    from nova_sdk_py.models.error_body import ErrorBody


T = TypeVar("T", bound="ErrorEnvelope")


@_attrs_define
class ErrorEnvelope:
    """Standard API error envelope.

    Attributes:
        error (ErrorBody): Standard API error body.
    """

    error: ErrorBody

    def to_dict(self) -> dict[str, Any]:
        error = self.error.to_dict()

        field_dict: dict[str, Any] = {}

        field_dict.update(
            {
                "error": error,
            }
        )

        return field_dict

    @classmethod
    def from_dict(cls: type[T], src_dict: Mapping[str, Any]) -> T:
        from nova_sdk_py.models.error_body import ErrorBody

        d = dict(src_dict)
        error = ErrorBody.from_dict(d.pop("error"))

        error_envelope = cls(
            error=error,
        )

        return error_envelope
