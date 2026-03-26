"""Create-export request model for the public Python SDK."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any, TypeVar

from attrs import define as _attrs_define

T = TypeVar("T", bound="CreateExportRequest")


@_attrs_define
class CreateExportRequest:
    """Request payload for export creation.

    Attributes:
        filename (str): Client-facing filename to preserve in the export.
        source_key (str): Storage key of the source object to export.
    """

    filename: str
    source_key: str

    def to_dict(self) -> dict[str, Any]:
        """Serialize the request payload to a JSON-compatible mapping."""
        filename = self.filename

        source_key = self.source_key

        field_dict: dict[str, Any] = {}

        field_dict.update(
            {
                "filename": filename,
                "source_key": source_key,
            }
        )

        return field_dict

    @classmethod
    def from_dict(cls: type[T], src_dict: Mapping[str, Any]) -> T:
        """Deserialize the request payload from a JSON-compatible mapping."""
        d = dict(src_dict)
        filename = d.pop("filename")

        source_key = d.pop("source_key")

        create_export_request = cls(
            filename=filename,
            source_key=source_key,
        )

        return create_export_request
