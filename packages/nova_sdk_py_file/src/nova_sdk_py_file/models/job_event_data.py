"""Model definitions for dynamic asynchronous job event payloads."""

# ruff: noqa
from __future__ import annotations

from collections.abc import Mapping
from typing import Any, TypeVar

from attrs import define as _attrs_define
from attrs import field as _attrs_field

T = TypeVar("T", bound="JobEventData")


@_attrs_define
class JobEventData:
    """Event payload map for asynchronous job events."""

    additional_properties: dict[str, Any] = _attrs_field(
        init=False, factory=dict
    )

    def to_dict(self) -> dict[str, Any]:
        """Serialize this model to a JSON-compatible dict."""

        field_dict: dict[str, Any] = {}
        field_dict.update(self.additional_properties)

        return field_dict

    @classmethod
    def from_dict(cls: type[T], src_dict: Mapping[str, Any]) -> T:
        """Build this model from a JSON-compatible mapping."""
        d = dict(src_dict)
        job_event_data = cls()

        job_event_data.additional_properties = d
        return job_event_data

    @property
    def additional_keys(self) -> list[str]:
        """Return dynamic payload keys captured on this model."""
        return list(self.additional_properties.keys())

    def __getitem__(self, key: str) -> Any:
        return self.additional_properties[key]

    def __setitem__(self, key: str, value: Any) -> None:
        self.additional_properties[key] = value

    def __delitem__(self, key: str) -> None:
        del self.additional_properties[key]

    def __contains__(self, key: str) -> bool:
        return key in self.additional_properties
