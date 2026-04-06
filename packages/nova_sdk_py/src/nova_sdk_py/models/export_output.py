from __future__ import annotations

from collections.abc import Mapping
from typing import Any, TypeVar

from attrs import define as _attrs_define

T = TypeVar("T", bound="ExportOutput")


@_attrs_define
class ExportOutput:
    """
    Completed export output metadata.

    Attributes:
        download_filename: Filename presented to clients when downloading.
        key: Storage key for the exported object.
    """

    download_filename: str
    """Filename presented to clients when downloading."""
    key: str
    """Storage key for the exported object."""

    def to_dict(self) -> dict[str, Any]:
        download_filename = self.download_filename

        key = self.key

        field_dict: dict[str, Any] = {}

        field_dict.update(
            {
                "download_filename": download_filename,
                "key": key,
            }
        )

        return field_dict

    @classmethod
    def from_dict(cls: type[T], src_dict: Mapping[str, Any]) -> T:
        d = dict(src_dict)
        download_filename = d.pop("download_filename")

        key = d.pop("key")

        export_output = cls(
            download_filename=download_filename,
            key=key,
        )

        return export_output
