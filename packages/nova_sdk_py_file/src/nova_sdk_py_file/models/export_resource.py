from __future__ import annotations

import datetime
from collections.abc import Mapping
from typing import (
    TYPE_CHECKING,
    Any,
    TypeVar,
    cast,
)

from attrs import define as _attrs_define
from dateutil.parser import isoparse

from nova_sdk_py_file.models.export_status import ExportStatus
from nova_sdk_py_file.types import UNSET, Unset

if TYPE_CHECKING:
    from nova_sdk_py_file.models.export_output import ExportOutput


T = TypeVar("T", bound="ExportResource")


@_attrs_define
class ExportResource:
    """Public export workflow resource.

    Attributes:
        created_at (datetime.datetime):
        export_id (str):
        filename (str):
        source_key (str):
        status (ExportStatus): Lifecycle status of an export workflow.
        updated_at (datetime.datetime):
        error (None | str | Unset):
        output (ExportOutput | None | Unset):
    """

    created_at: datetime.datetime
    export_id: str
    filename: str
    source_key: str
    status: ExportStatus
    updated_at: datetime.datetime
    error: None | str | Unset = UNSET
    output: ExportOutput | None | Unset = UNSET

    def to_dict(self) -> dict[str, Any]:
        from nova_sdk_py_file.models.export_output import ExportOutput

        created_at = self.created_at.isoformat()

        export_id = self.export_id

        filename = self.filename

        source_key = self.source_key

        status = self.status.value

        updated_at = self.updated_at.isoformat()

        error: None | str | Unset
        if isinstance(self.error, Unset):
            error = UNSET
        else:
            error = self.error

        output: dict[str, Any] | None | Unset
        if isinstance(self.output, Unset):
            output = UNSET
        elif isinstance(self.output, ExportOutput):
            output = self.output.to_dict()
        else:
            output = self.output

        field_dict: dict[str, Any] = {}

        field_dict.update(
            {
                "created_at": created_at,
                "export_id": export_id,
                "filename": filename,
                "source_key": source_key,
                "status": status,
                "updated_at": updated_at,
            }
        )
        if error is not UNSET:
            field_dict["error"] = error
        if output is not UNSET:
            field_dict["output"] = output

        return field_dict

    @classmethod
    def from_dict(cls: type[T], src_dict: Mapping[str, Any]) -> T:
        from nova_sdk_py_file.models.export_output import ExportOutput

        d = dict(src_dict)
        created_at = isoparse(d.pop("created_at"))

        export_id = d.pop("export_id")

        filename = d.pop("filename")

        source_key = d.pop("source_key")

        status = ExportStatus(d.pop("status"))

        updated_at = isoparse(d.pop("updated_at"))

        def _parse_error(data: object) -> None | str | Unset:
            if data is None:
                return data
            if isinstance(data, Unset):
                return data
            return cast(None | str | Unset, data)

        error = _parse_error(d.pop("error", UNSET))

        def _parse_output(
            data: object,
        ) -> ExportOutput | None | Unset:
            if data is None:
                return data
            if isinstance(data, Unset):
                return data
            if not isinstance(data, Mapping):
                raise TypeError(
                    "Expected output payload to be a mapping or null"
                )
            output_data = cast("Mapping[str, Any]", data)
            return ExportOutput.from_dict(output_data)

        output = _parse_output(d.pop("output", UNSET))

        export_resource = cls(
            created_at=created_at,
            export_id=export_id,
            filename=filename,
            source_key=source_key,
            status=status,
            updated_at=updated_at,
            error=error,
            output=output,
        )

        return export_resource
