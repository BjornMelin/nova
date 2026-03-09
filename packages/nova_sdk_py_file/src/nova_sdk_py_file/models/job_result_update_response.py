from __future__ import annotations

import datetime
from collections.abc import Mapping
from typing import Any, TypeVar

from attrs import define as _attrs_define
from dateutil.parser import isoparse

from ..models.job_status import JobStatus

T = TypeVar("T", bound="JobResultUpdateResponse")


@_attrs_define
class JobResultUpdateResponse:
    """Response payload for internal job result updates.

    Attributes:
        job_id (str):
        status (JobStatus): Lifecycle status of an async job.
        updated_at (datetime.datetime):
    """

    job_id: str
    status: JobStatus
    updated_at: datetime.datetime

    def to_dict(self) -> dict[str, Any]:
        job_id = self.job_id

        status = self.status.value

        updated_at = self.updated_at.isoformat()

        field_dict: dict[str, Any] = {}

        field_dict.update(
            {
                "job_id": job_id,
                "status": status,
                "updated_at": updated_at,
            }
        )

        return field_dict

    @classmethod
    def from_dict(cls: type[T], src_dict: Mapping[str, Any]) -> T:
        d = dict(src_dict)
        job_id = d.pop("job_id")

        status = JobStatus(d.pop("status"))

        updated_at = isoparse(d.pop("updated_at"))

        job_result_update_response = cls(
            job_id=job_id,
            status=status,
            updated_at=updated_at,
        )

        return job_result_update_response
