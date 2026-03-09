from __future__ import annotations

from collections.abc import Mapping
from typing import TYPE_CHECKING, Any, TypeVar

from attrs import define as _attrs_define

if TYPE_CHECKING:
    from ..models.job_record import JobRecord


T = TypeVar("T", bound="JobStatusResponse")


@_attrs_define
class JobStatusResponse:
    """Response payload for status endpoint.

    Attributes:
        job (JobRecord): Persistent job representation.
    """

    job: JobRecord

    def to_dict(self) -> dict[str, Any]:
        job = self.job.to_dict()

        field_dict: dict[str, Any] = {}

        field_dict.update(
            {
                "job": job,
            }
        )

        return field_dict

    @classmethod
    def from_dict(cls: type[T], src_dict: Mapping[str, Any]) -> T:
        from ..models.job_record import JobRecord

        d = dict(src_dict)
        job = JobRecord.from_dict(d.pop("job"))

        job_status_response = cls(
            job=job,
        )

        return job_status_response
