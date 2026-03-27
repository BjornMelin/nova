from __future__ import annotations

from collections.abc import Mapping
from typing import (
    Any,
    TypeVar,
    cast,
)

from attrs import define as _attrs_define

from nova_sdk_py.types import UNSET, Unset

T = TypeVar("T", bound="ResourcePlanItem")


@_attrs_define
class ResourcePlanItem:
    """Resource planning decision per requested resource.

    Attributes:
        resource (str):
        supported (bool):
        reason (None | str | Unset):
    """

    resource: str
    supported: bool
    reason: None | str | Unset = UNSET

    def to_dict(self) -> dict[str, Any]:
        resource = self.resource

        supported = self.supported

        reason: None | str | Unset
        if isinstance(self.reason, Unset):
            reason = UNSET
        else:
            reason = self.reason

        field_dict: dict[str, Any] = {}

        field_dict.update(
            {
                "resource": resource,
                "supported": supported,
            }
        )
        if reason is not UNSET:
            field_dict["reason"] = reason

        return field_dict

    @classmethod
    def from_dict(cls: type[T], src_dict: Mapping[str, Any]) -> T:
        d = dict(src_dict)
        resource = d.pop("resource")

        supported = d.pop("supported")

        def _parse_reason(data: object) -> None | str | Unset:
            if data is None:
                return data
            if isinstance(data, Unset):
                return data
            return cast(None | str | Unset, data)

        reason = _parse_reason(d.pop("reason", UNSET))

        resource_plan_item = cls(
            resource=resource,
            supported=supported,
            reason=reason,
        )

        return resource_plan_item
