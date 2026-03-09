# ruff: noqa
"""Readiness dependency check status map model."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any, TypeVar

from attrs import define as _attrs_define
from attrs import field as _attrs_field

T = TypeVar("T", bound="ReadinessResponseChecks")


@_attrs_define
class ReadinessResponseChecks:
    """Readiness dependency check status map.

    Attributes:
        additional_properties (dict[str, bool]): Mapping of component names
            to readiness booleans.
    """

    additional_properties: dict[str, bool] = _attrs_field(
        init=False, factory=dict
    )

    def to_dict(self) -> dict[str, Any]:
        """Serialize this model to a JSON-compatible dict.

        Args:
            None.

        Returns:
            dict[str, Any]: Serialized readiness status map.
        """

        field_dict: dict[str, Any] = {}
        field_dict.update(self.additional_properties)

        return field_dict

    @classmethod
    def from_dict(cls: type[T], src_dict: Mapping[str, Any]) -> T:
        """Build this model from a JSON-compatible mapping.

        Args:
            src_dict (Mapping[str, Any]): Source mapping.

        Returns:
            ReadinessResponseChecks: Parsed model instance.

        Raises:
            TypeError: If src_dict is not a mapping or values are invalid.
                For example, if a key does not map to bool-like data.
        """
        d = dict(src_dict)
        readiness_response_checks = cls()

        validated_values: dict[str, bool] = {}
        for key, value in d.items():
            if not isinstance(value, bool):
                raise TypeError(
                    f"readiness_response_checks[{key!r}] must be bool; "
                    f"got {value!r}"
                )
            validated_values[key] = value

        readiness_response_checks.additional_properties = validated_values
        return readiness_response_checks

    @property
    def additional_keys(self) -> list[str]:
        """List keys present in ``additional_properties``.

        Args:
            None.

        Returns:
            list[str]: Keys present in ``additional_properties``.
        """
        return list(self.additional_properties.keys())

    def __getitem__(self, key: str) -> bool:
        return self.additional_properties[key]

    def __setitem__(self, key: str, value: bool) -> None:
        self.additional_properties[key] = value

    def __delitem__(self, key: str) -> None:
        del self.additional_properties[key]

    def __contains__(self, key: str) -> bool:
        return key in self.additional_properties
