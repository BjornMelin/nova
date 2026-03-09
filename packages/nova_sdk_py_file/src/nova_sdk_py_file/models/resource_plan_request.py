from __future__ import annotations

from collections.abc import Mapping
from typing import Any, TypeVar, cast

from attrs import define as _attrs_define

T = TypeVar("T", bound="ResourcePlanRequest")


@_attrs_define
class ResourcePlanRequest:
    """Resource planning request body.

    Attributes:
        resources (list[str]):
    """

    resources: list[str]

    def to_dict(self) -> dict[str, Any]:
        resources = self.resources

        field_dict: dict[str, Any] = {}

        field_dict.update(
            {
                "resources": resources,
            }
        )

        return field_dict

    @classmethod
    def from_dict(cls: type[T], src_dict: Mapping[str, Any]) -> T:
        d = dict(src_dict)
        resources = cast(list[str], d.pop("resources"))

        resource_plan_request = cls(
            resources=resources,
        )

        return resource_plan_request
