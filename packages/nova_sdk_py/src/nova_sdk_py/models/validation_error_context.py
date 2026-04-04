from __future__ import annotations

from collections.abc import Mapping
from typing import Any, TypeVar

from attrs import define as _attrs_define, field as _attrs_field

T = TypeVar("T", bound="ValidationErrorContext")


@_attrs_define
class ValidationErrorContext:
    """Hold arbitrary key/value pairs returned alongside validation errors."""

    additional_properties: dict[str, Any] = _attrs_field(
        init=False, factory=dict
    )

    def to_dict(self) -> dict[str, Any]:
        """Serialize additional properties to a plain ``dict``."""

        field_dict: dict[str, Any] = {}
        field_dict.update(self.additional_properties)

        return field_dict

    @classmethod
    def from_dict(cls: type[T], src_dict: Mapping[str, Any]) -> T:
        """Build an instance from a decoded mapping (all keys preserved)."""

        d = dict(src_dict)
        validation_error_context = cls()

        validation_error_context.additional_properties = d
        return validation_error_context

    @property
    def additional_keys(self) -> list[str]:
        """Return keys present in ``additional_properties``."""

        return list(self.additional_properties.keys())

    def __getitem__(self, key: str) -> Any:
        """Return the value for ``key`` from ``additional_properties``."""

        return self.additional_properties[key]

    def __setitem__(self, key: str, value: Any) -> None:
        """Set ``key`` on ``additional_properties``."""

        self.additional_properties[key] = value

    def __delitem__(self, key: str) -> None:
        """Remove ``key`` from ``additional_properties``."""

        del self.additional_properties[key]

    def __contains__(self, key: str) -> bool:
        """Return whether ``key`` exists in ``additional_properties``."""

        return key in self.additional_properties
