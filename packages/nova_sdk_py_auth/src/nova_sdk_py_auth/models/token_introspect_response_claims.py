"""Models dynamic claims returned by token introspection responses."""

# ruff: noqa
from __future__ import annotations

from collections.abc import Mapping
from typing import Any, TypeVar

from attrs import define as _attrs_define
from attrs import field as _attrs_field

T = TypeVar("T", bound="TokenIntrospectResponseClaims")


@_attrs_define
class TokenIntrospectResponseClaims:
    """Container for arbitrary token introspection claims."""

    additional_properties: dict[str, Any] = _attrs_field(
        init=False, factory=dict
    )

    def to_dict(self) -> dict[str, Any]:
        """Serialize this model to a JSON-compatible mapping."""

        field_dict: dict[str, Any] = {}
        field_dict.update(self.additional_properties)

        return field_dict

    @classmethod
    def from_dict(cls: type[T], src_dict: Mapping[str, Any]) -> T:
        """Build this model from a JSON-compatible mapping."""
        d = dict(src_dict)
        token_introspect_response_claims = cls()

        token_introspect_response_claims.additional_properties = d
        return token_introspect_response_claims

    @property
    def additional_keys(self) -> list[str]:
        """Return dynamic claim keys captured on this model."""
        return list(self.additional_properties.keys())

    def __getitem__(self, key: str) -> Any:
        return self.additional_properties[key]

    def __setitem__(self, key: str, value: Any) -> None:
        self.additional_properties[key] = value

    def __delitem__(self, key: str) -> None:
        del self.additional_properties[key]

    def __contains__(self, key: str) -> bool:
        return key in self.additional_properties
