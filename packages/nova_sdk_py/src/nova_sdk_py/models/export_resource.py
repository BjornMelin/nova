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

from nova_sdk_py.models.export_status import ExportStatus
from nova_sdk_py.types import UNSET, Unset

if TYPE_CHECKING:
    from nova_sdk_py.models.export_output import ExportOutput


T = TypeVar("T", bound="ExportResource")


@_attrs_define
class ExportResource:
    """
    Public export workflow resource.

    Attributes:
        cancel_requested_at: Timestamp when cancel intent was persisted for
        the export.
        created_at: Timestamp when the export workflow resource was created.
        error: Terminal error message when the export fails.
        execution_arn: Step Functions execution ARN for the active export
        workflow.
        export_id: Identifier of the caller-owned export workflow resource.
        filename: Filename presented to callers when downloading the export.
        output: Completed output metadata when the export succeeds.
        source_key: Storage key of the object managed by the export
        workflow.
        status: Current lifecycle state of the export workflow.
        updated_at: Timestamp when the export workflow resource last
        changed.
    """

    created_at: datetime.datetime
    """ Timestamp when the export workflow resource was created. """
    export_id: str
    """ Identifier of the caller-owned export workflow resource. """
    filename: str
    """ Filename presented to callers when downloading the export. """
    source_key: str
    """ Storage key of the object managed by the export workflow. """
    status: ExportStatus
    """ Lifecycle status of an export workflow. """
    updated_at: datetime.datetime
    """ Timestamp when the export workflow resource last changed. """
    cancel_requested_at: datetime.datetime | None | Unset = UNSET
    """ Timestamp when cancel intent was persisted for the export. """
    error: None | str | Unset = UNSET
    """ Terminal error message when the export fails. """
    execution_arn: None | str | Unset = UNSET
    """ Step Functions execution ARN for the active export workflow. """
    output: ExportOutput | None | Unset = UNSET
    """ Completed output metadata when the export succeeds. """

    def to_dict(self) -> dict[str, Any]:
        from nova_sdk_py.models.export_output import ExportOutput

        created_at = self.created_at.isoformat()

        export_id = self.export_id

        filename = self.filename

        source_key = self.source_key

        status = self.status.value

        updated_at = self.updated_at.isoformat()

        cancel_requested_at: None | str | Unset
        if isinstance(self.cancel_requested_at, Unset):
            cancel_requested_at = UNSET
        elif isinstance(self.cancel_requested_at, datetime.datetime):
            cancel_requested_at = self.cancel_requested_at.isoformat()
        else:
            cancel_requested_at = self.cancel_requested_at

        error: None | str | Unset
        if isinstance(self.error, Unset):
            error = UNSET
        else:
            error = self.error

        execution_arn: None | str | Unset
        if isinstance(self.execution_arn, Unset):
            execution_arn = UNSET
        else:
            execution_arn = self.execution_arn

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
        if cancel_requested_at is not UNSET:
            field_dict["cancel_requested_at"] = cancel_requested_at
        if error is not UNSET:
            field_dict["error"] = error
        if execution_arn is not UNSET:
            field_dict["execution_arn"] = execution_arn
        if output is not UNSET:
            field_dict["output"] = output

        return field_dict

    @classmethod
    def from_dict(cls: type[T], src_dict: Mapping[str, Any]) -> T:
        from nova_sdk_py.models.export_output import ExportOutput

        d = dict(src_dict)
        created_at = isoparse(d.pop("created_at"))

        export_id = d.pop("export_id")

        filename = d.pop("filename")

        source_key = d.pop("source_key")

        status = ExportStatus(d.pop("status"))

        updated_at = isoparse(d.pop("updated_at"))

        def _parse_cancel_requested_at(
            data: object,
        ) -> datetime.datetime | None | Unset:
            if data is None:
                return data
            if isinstance(data, Unset):
                return data
            try:
                if not isinstance(data, str):
                    raise TypeError()
                cancel_requested_at_type_0 = isoparse(data)

                return cancel_requested_at_type_0
            except (TypeError, ValueError, AttributeError, KeyError):
                pass
            return cast(datetime.datetime | None | Unset, data)

        cancel_requested_at = _parse_cancel_requested_at(
            d.pop("cancel_requested_at", UNSET)
        )

        def _parse_error(data: object) -> None | str | Unset:
            if data is None:
                return data
            if isinstance(data, Unset):
                return data
            return cast(None | str | Unset, data)

        error = _parse_error(d.pop("error", UNSET))

        def _parse_execution_arn(data: object) -> None | str | Unset:
            if data is None:
                return data
            if isinstance(data, Unset):
                return data
            return cast(None | str | Unset, data)

        execution_arn = _parse_execution_arn(d.pop("execution_arn", UNSET))

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
            cancel_requested_at=cancel_requested_at,
            error=error,
            execution_arn=execution_arn,
            output=output,
        )

        return export_resource
