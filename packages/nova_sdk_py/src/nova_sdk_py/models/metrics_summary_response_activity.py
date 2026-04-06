from __future__ import annotations

from collections.abc import Mapping
from typing import Any, TypeVar

from attrs import define as _attrs_define, field as _attrs_field

T = TypeVar("T", bound="MetricsSummaryResponseActivity")


@_attrs_define
class MetricsSummaryResponseActivity:
    additional_properties: dict[str, int] = _attrs_field(
        init=False, factory=dict
    )

    def to_dict(self) -> dict[str, Any]:

        field_dict: dict[str, Any] = {}
        field_dict.update(self.additional_properties)

        return field_dict

    @classmethod
    def from_dict(cls: type[T], src_dict: Mapping[str, Any]) -> T:
        d = dict(src_dict)
        metrics_summary_response_activity = cls()
        additional_properties: dict[str, int] = {}
        for key, value in d.items():
            if isinstance(value, bool):
                raise TypeError(
                    f"Invalid value for {key!r}: expected int, got bool"
                )
            additional_properties[key] = int(value)

        metrics_summary_response_activity.additional_properties = (
            additional_properties
        )
        return metrics_summary_response_activity

    @property
    def additional_keys(self) -> list[str]:
        return list(self.additional_properties.keys())

    def __getitem__(self, key: str) -> int:
        return self.additional_properties[key]

    def __setitem__(self, key: str, value: int) -> None:
        self.additional_properties[key] = value

    def __delitem__(self, key: str) -> None:
        del self.additional_properties[key]

    def __contains__(self, key: str) -> bool:
        return key in self.additional_properties
