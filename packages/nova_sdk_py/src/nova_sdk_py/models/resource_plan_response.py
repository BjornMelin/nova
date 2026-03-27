from __future__ import annotations

from collections.abc import Mapping
from typing import (
    TYPE_CHECKING,
    Any,
    TypeVar,
)

from attrs import define as _attrs_define

if TYPE_CHECKING:
    from nova_sdk_py.models.resource_plan_item import ResourcePlanItem


T = TypeVar("T", bound="ResourcePlanResponse")


@_attrs_define
class ResourcePlanResponse:
    """Resource planning response body.

    Attributes:
        plan (list[ResourcePlanItem]):
    """

    plan: list[ResourcePlanItem]

    def to_dict(self) -> dict[str, Any]:
        plan = []
        for plan_item_data in self.plan:
            plan_item = plan_item_data.to_dict()
            plan.append(plan_item)

        field_dict: dict[str, Any] = {}

        field_dict.update(
            {
                "plan": plan,
            }
        )

        return field_dict

    @classmethod
    def from_dict(cls: type[T], src_dict: Mapping[str, Any]) -> T:
        from nova_sdk_py.models.resource_plan_item import ResourcePlanItem

        d = dict(src_dict)
        plan = []
        _plan = d.pop("plan")
        for plan_item_data in _plan:
            plan_item = ResourcePlanItem.from_dict(plan_item_data)

            plan.append(plan_item)

        resource_plan_response = cls(
            plan=plan,
        )

        return resource_plan_response
