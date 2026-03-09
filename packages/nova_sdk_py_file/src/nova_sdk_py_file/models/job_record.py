from __future__ import annotations

import datetime
from collections.abc import Mapping
from typing import TYPE_CHECKING, Any, TypeVar, cast

from attrs import define as _attrs_define
from dateutil.parser import isoparse

from ..models.job_status import JobStatus
from ..types import UNSET, Unset

if TYPE_CHECKING:
    from ..models.job_record_payload import JobRecordPayload
    from ..models.job_record_result_type_0 import JobRecordResultType0


T = TypeVar("T", bound="JobRecord")


@_attrs_define
class JobRecord:
    """Persistent job representation.

    Attributes:
        created_at (datetime.datetime):
        job_id (str):
        job_type (str):
        payload (JobRecordPayload):
        scope_id (str):
        status (JobStatus): Lifecycle status of an async job.
        updated_at (datetime.datetime):
        error (None | str | Unset):
        result (JobRecordResultType0 | None | Unset):
    """

    created_at: datetime.datetime
    job_id: str
    job_type: str
    payload: JobRecordPayload
    scope_id: str
    status: JobStatus
    updated_at: datetime.datetime
    error: None | str | Unset = UNSET
    result: JobRecordResultType0 | None | Unset = UNSET

    def to_dict(self) -> dict[str, Any]:
        from ..models.job_record_result_type_0 import JobRecordResultType0

        created_at = self.created_at.isoformat()

        job_id = self.job_id

        job_type = self.job_type

        payload = self.payload.to_dict()

        scope_id = self.scope_id

        status = self.status.value

        updated_at = self.updated_at.isoformat()

        error: None | str | Unset
        if isinstance(self.error, Unset):
            error = UNSET
        else:
            error = self.error

        result: dict[str, Any] | None | Unset
        if isinstance(self.result, Unset):
            result = UNSET
        elif isinstance(self.result, JobRecordResultType0):
            result = self.result.to_dict()
        else:
            result = self.result

        field_dict: dict[str, Any] = {}

        field_dict.update(
            {
                "created_at": created_at,
                "job_id": job_id,
                "job_type": job_type,
                "payload": payload,
                "scope_id": scope_id,
                "status": status,
                "updated_at": updated_at,
            }
        )
        if error is not UNSET:
            field_dict["error"] = error
        if result is not UNSET:
            field_dict["result"] = result

        return field_dict

    @classmethod
    def from_dict(cls: type[T], src_dict: Mapping[str, Any]) -> T:
        from ..models.job_record_payload import JobRecordPayload
        from ..models.job_record_result_type_0 import JobRecordResultType0

        d = dict(src_dict)
        created_at = isoparse(d.pop("created_at"))

        job_id = d.pop("job_id")

        job_type = d.pop("job_type")

        payload = JobRecordPayload.from_dict(d.pop("payload"))

        scope_id = d.pop("scope_id")

        status = JobStatus(d.pop("status"))

        updated_at = isoparse(d.pop("updated_at"))

        def _parse_error(data: object) -> None | str | Unset:
            if data is None:
                return data
            if isinstance(data, Unset):
                return data
            return cast(None | str | Unset, data)

        error = _parse_error(d.pop("error", UNSET))

        def _parse_result(data: object) -> JobRecordResultType0 | None | Unset:
            if data is None:
                return data
            if isinstance(data, Unset):
                return data
            try:
                if not isinstance(data, dict):
                    raise TypeError()
                result_type_0 = JobRecordResultType0.from_dict(data)

                return result_type_0
            except (TypeError, ValueError, AttributeError, KeyError):
                pass
            return cast(JobRecordResultType0 | None | Unset, data)

        result = _parse_result(d.pop("result", UNSET))

        job_record = cls(
            created_at=created_at,
            job_id=job_id,
            job_type=job_type,
            payload=payload,
            scope_id=scope_id,
            status=status,
            updated_at=updated_at,
            error=error,
            result=result,
        )

        return job_record
