from __future__ import annotations

from collections.abc import Mapping
from typing import (
    TYPE_CHECKING,
    Any,
    TypeVar,
)

from attrs import define as _attrs_define

from ..types import UNSET, Unset

if TYPE_CHECKING:
    from ..models.capability_descriptor_details import (
        CapabilityDescriptorDetails,
    )


T = TypeVar("T", bound="CapabilityDescriptor")


@_attrs_define
class CapabilityDescriptor:
    """Machine-readable capability declaration.

    Attributes:
        enabled (bool):
        key (str):
        details (CapabilityDescriptorDetails | Unset):
    """

    enabled: bool
    key: str
    details: CapabilityDescriptorDetails | Unset = UNSET

    def to_dict(self) -> dict[str, Any]:
        enabled = self.enabled

        key = self.key

        details: dict[str, Any] | Unset = UNSET
        if not isinstance(self.details, Unset):
            details = self.details.to_dict()

        field_dict: dict[str, Any] = {}

        field_dict.update(
            {
                "enabled": enabled,
                "key": key,
            }
        )
        if details is not UNSET:
            field_dict["details"] = details

        return field_dict

    @classmethod
    def from_dict(cls: type[T], src_dict: Mapping[str, Any]) -> T:
        from ..models.capability_descriptor_details import (
            CapabilityDescriptorDetails,
        )

        d = dict(src_dict)
        enabled = d.pop("enabled")

        key = d.pop("key")

        _details = d.pop("details", UNSET)
        details: CapabilityDescriptorDetails | Unset
        if isinstance(_details, Unset):
            details = UNSET
        else:
            details = CapabilityDescriptorDetails.from_dict(_details)

        capability_descriptor = cls(
            enabled=enabled,
            key=key,
            details=details,
        )

        return capability_descriptor
