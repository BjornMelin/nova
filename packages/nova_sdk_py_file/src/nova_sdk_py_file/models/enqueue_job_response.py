# ruff: noqa
from __future__ import annotations

from collections.abc import Mapping
from typing import Any, TypeVar

from attrs import define as _attrs_define

from nova_sdk_py_file.models.job_status import JobStatus

T = TypeVar("T", bound="EnqueueJobResponse")


@_attrs_define
class EnqueueJobResponse:
    """Response payload for enqueue endpoint.

    Attributes:
        job_id (str):
        status (JobStatus): Lifecycle status of an async job.
    """

    job_id: str
    status: JobStatus

    def to_dict(self) -> dict[str, Any]:
        job_id = self.job_id

        status = self.status.value

        field_dict: dict[str, Any] = {}

        field_dict.update(
            {
                "job_id": job_id,
                "status": status,
            }
        )

        return field_dict

    @classmethod
    def from_dict(cls: type[T], src_dict: Mapping[str, Any]) -> T:
        d = dict(src_dict)
        job_id = d.pop("job_id")

        status = JobStatus(d.pop("status"))

        enqueue_job_response = cls(
            job_id=job_id,
            status=status,
        )

        return enqueue_job_response
