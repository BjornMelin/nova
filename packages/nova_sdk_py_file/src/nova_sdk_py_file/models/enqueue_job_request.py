from __future__ import annotations

from collections.abc import Mapping
from typing import (
    TYPE_CHECKING,
    Any,
    TypeVar,
)

from attrs import define as _attrs_define

from ..types import UNSET, Unset

if TYPE_CHECKING:
    from ..models.enqueue_job_request_payload import EnqueueJobRequestPayload


T = TypeVar("T", bound="EnqueueJobRequest")


@_attrs_define
class EnqueueJobRequest:
    """Request payload for job enqueue endpoint.

    Attributes:
        job_type (str):
        payload (EnqueueJobRequestPayload | Unset):
    """

    job_type: str
    payload: EnqueueJobRequestPayload | Unset = UNSET

    def to_dict(self) -> dict[str, Any]:
        job_type = self.job_type

        payload: dict[str, Any] | Unset = UNSET
        if not isinstance(self.payload, Unset):
            payload = self.payload.to_dict()

        field_dict: dict[str, Any] = {}

        field_dict.update(
            {
                "job_type": job_type,
            }
        )
        if payload is not UNSET:
            field_dict["payload"] = payload

        return field_dict

    @classmethod
    def from_dict(cls: type[T], src_dict: Mapping[str, Any]) -> T:
        from ..models.enqueue_job_request_payload import (
            EnqueueJobRequestPayload,
        )

        d = dict(src_dict)
        job_type = d.pop("job_type")

        _payload = d.pop("payload", UNSET)
        payload: EnqueueJobRequestPayload | Unset
        if isinstance(_payload, Unset):
            payload = UNSET
        else:
            payload = EnqueueJobRequestPayload.from_dict(_payload)

        enqueue_job_request = cls(
            job_type=job_type,
            payload=payload,
        )

        return enqueue_job_request
