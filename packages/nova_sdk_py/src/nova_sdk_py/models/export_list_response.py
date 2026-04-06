from __future__ import annotations

from collections.abc import Mapping
from typing import (
    TYPE_CHECKING,
    Any,
    TypeVar,
)

from attrs import define as _attrs_define

if TYPE_CHECKING:
    from nova_sdk_py.models.export_resource import ExportResource


T = TypeVar("T", bound="ExportListResponse")


@_attrs_define
class ExportListResponse:
    """
    Response payload for export listing endpoint.

    Attributes:
        exports: Caller-owned export workflow resources ordered by recency.
    """

    exports: list[ExportResource]
    """Caller-owned export workflow resources ordered by recency."""

    def to_dict(self) -> dict[str, Any]:
        exports = []
        for exports_item_data in self.exports:
            exports_item = exports_item_data.to_dict()
            exports.append(exports_item)

        field_dict: dict[str, Any] = {}

        field_dict.update(
            {
                "exports": exports,
            }
        )

        return field_dict

    @classmethod
    def from_dict(cls: type[T], src_dict: Mapping[str, Any]) -> T:
        from nova_sdk_py.models.export_resource import ExportResource

        d = dict(src_dict)
        exports = []
        _exports = d.pop("exports")
        for exports_item_data in _exports:
            exports_item = ExportResource.from_dict(exports_item_data)

            exports.append(exports_item)

        export_list_response = cls(
            exports=exports,
        )

        return export_list_response
