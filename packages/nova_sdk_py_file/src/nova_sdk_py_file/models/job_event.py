from __future__ import annotations

import datetime
from collections.abc import Mapping
from typing import TYPE_CHECKING, Any, TypeVar

from attrs import define as _attrs_define
from dateutil.parser import isoparse

from ..models.job_event_type import JobEventType
from ..models.job_status import JobStatus
from ..types import UNSET, Unset

if TYPE_CHECKING:
    from ..models.job_event_data import JobEventData


T = TypeVar("T", bound="JobEvent")


@_attrs_define
class JobEvent:
    """Single event entry for a job event stream/poll response.

    Attributes:
        event_id (str):
        job_id (str):
        status (JobStatus): Lifecycle status of an async job.
        timestamp (datetime.datetime):
        data (JobEventData | Unset):
        event_type (JobEventType | Unset): Event kinds emitted by the v1 job events contract.
    """

    event_id: str
    job_id: str
    status: JobStatus
    timestamp: datetime.datetime
    data: JobEventData | Unset = UNSET
    event_type: JobEventType | Unset = UNSET

    def to_dict(self) -> dict[str, Any]:
        event_id = self.event_id

        job_id = self.job_id

        status = self.status.value

        timestamp = self.timestamp.isoformat()

        data: dict[str, Any] | Unset = UNSET
        if not isinstance(self.data, Unset):
            data = self.data.to_dict()

        event_type: str | Unset = UNSET
        if not isinstance(self.event_type, Unset):
            event_type = self.event_type.value

        field_dict: dict[str, Any] = {}

        field_dict.update(
            {
                "event_id": event_id,
                "job_id": job_id,
                "status": status,
                "timestamp": timestamp,
            }
        )
        if data is not UNSET:
            field_dict["data"] = data
        if event_type is not UNSET:
            field_dict["event_type"] = event_type

        return field_dict

    @classmethod
    def from_dict(cls: type[T], src_dict: Mapping[str, Any]) -> T:
        from ..models.job_event_data import JobEventData

        d = dict(src_dict)
        event_id = d.pop("event_id")

        job_id = d.pop("job_id")

        status = JobStatus(d.pop("status"))

        timestamp = isoparse(d.pop("timestamp"))

        _data = d.pop("data", UNSET)
        data: JobEventData | Unset
        if isinstance(_data, Unset):
            data = UNSET
        else:
            data = JobEventData.from_dict(_data)

        _event_type = d.pop("event_type", UNSET)
        event_type: JobEventType | Unset
        if isinstance(_event_type, Unset):
            event_type = UNSET
        else:
            event_type = JobEventType(_event_type)

        job_event = cls(
            event_id=event_id,
            job_id=job_id,
            status=status,
            timestamp=timestamp,
            data=data,
            event_type=event_type,
        )

        return job_event
