from __future__ import annotations

from collections.abc import Mapping
from typing import (
    TYPE_CHECKING,
    Any,
    TypeVar,
)

from attrs import define as _attrs_define

if TYPE_CHECKING:
    from nova_sdk_py.models.capability_descriptor import CapabilityDescriptor


T = TypeVar("T", bound="CapabilitiesResponse")


@_attrs_define
class CapabilitiesResponse:
    """
    Capabilities endpoint response.

    Attributes:
        capabilities: Capability declarations exposed by the running API.
    """

    capabilities: list[CapabilityDescriptor]
    """Capability declarations exposed by the running API."""

    def to_dict(self) -> dict[str, Any]:
        capabilities = []
        for capabilities_item_data in self.capabilities:
            capabilities_item = capabilities_item_data.to_dict()
            capabilities.append(capabilities_item)

        field_dict: dict[str, Any] = {}

        field_dict.update(
            {
                "capabilities": capabilities,
            }
        )

        return field_dict

    @classmethod
    def from_dict(cls: type[T], src_dict: Mapping[str, Any]) -> T:
        from nova_sdk_py.models.capability_descriptor import (
            CapabilityDescriptor,
        )

        d = dict(src_dict)
        capabilities = []
        _capabilities = d.pop("capabilities")
        for capabilities_item_data in _capabilities:
            capabilities_item = CapabilityDescriptor.from_dict(
                capabilities_item_data
            )

            capabilities.append(capabilities_item)

        capabilities_response = cls(
            capabilities=capabilities,
        )

        return capabilities_response
