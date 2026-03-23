from __future__ import annotations

from collections.abc import Mapping
from typing import (
    TYPE_CHECKING,
    Any,
    TypeVar,
)

from attrs import define as _attrs_define

if TYPE_CHECKING:
    from ..models.job_record import JobRecord


T = TypeVar("T", bound="JobListResponse")


@_attrs_define
class JobListResponse:
    """Response payload for job listing endpoint.

    Attributes:
        jobs (list[JobRecord]):
    """

    jobs: list[JobRecord]

    def to_dict(self) -> dict[str, Any]:
        jobs = []
        for jobs_item_data in self.jobs:
            jobs_item = jobs_item_data.to_dict()
            jobs.append(jobs_item)

        field_dict: dict[str, Any] = {}

        field_dict.update(
            {
                "jobs": jobs,
            }
        )

        return field_dict

    @classmethod
    def from_dict(cls: type[T], src_dict: Mapping[str, Any]) -> T:
        from ..models.job_record import JobRecord

        d = dict(src_dict)
        jobs = []
        _jobs = d.pop("jobs")
        for jobs_item_data in _jobs:
            jobs_item = JobRecord.from_dict(jobs_item_data)

            jobs.append(jobs_item)

        job_list_response = cls(
            jobs=jobs,
        )

        return job_list_response
