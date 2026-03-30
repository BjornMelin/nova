from __future__ import annotations

from collections.abc import Mapping
from typing import Any, TypeVar

from attrs import define as _attrs_define, field as _attrs_field

T = TypeVar("T", bound="MetricsSummaryResponseLatenciesMs")


@_attrs_define
class MetricsSummaryResponseLatenciesMs:
    """Named latency metrics reported by the metrics summary endpoint in milliseconds.

    Attributes:
        additional_properties (dict[str, float]): Latency values keyed by name.
    """

    additional_properties: dict[str, float] = _attrs_field(
        init=False, factory=dict
    )

    def to_dict(self) -> dict[str, Any]:

        field_dict: dict[str, Any] = {}
        field_dict.update(self.additional_properties)

        return field_dict

    @classmethod
    def from_dict(cls: type[T], src_dict: Mapping[str, Any]) -> T:
        d = dict(src_dict)
        metrics_summary_response_latencies_ms = cls()
        additional_properties: dict[str, float] = {}
        for key, value in d.items():
            if isinstance(value, bool):
                raise TypeError(
                    f"Invalid value for {key!r}: expected float, got bool"
                )
            additional_properties[key] = float(value)

        metrics_summary_response_latencies_ms.additional_properties = (
            additional_properties
        )
        return metrics_summary_response_latencies_ms

    @property
    def additional_keys(self) -> list[str]:
        return list(self.additional_properties.keys())

    def __getitem__(self, key: str) -> float:
        return self.additional_properties[key]

    def __setitem__(self, key: str, value: float) -> None:
        self.additional_properties[key] = value

    def __delitem__(self, key: str) -> None:
        del self.additional_properties[key]

    def __contains__(self, key: str) -> bool:
        return key in self.additional_properties
