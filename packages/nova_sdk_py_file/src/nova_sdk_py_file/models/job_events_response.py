# ruff: noqa
"""Polling/SSE job events envelope used by client model code generation."""

from __future__ import annotations

from collections.abc import Mapping
from typing import TYPE_CHECKING, Any, TypeVar

from attrs import define as _attrs_define

if TYPE_CHECKING:
    from nova_sdk_py_file.models.job_event import JobEvent


T = TypeVar("T", bound="JobEventsResponse")


@_attrs_define
class JobEventsResponse:
    """Polling/SSE-compatible events envelope.

    Attributes:
        events (list[JobEvent]): Job event records in stream order.
        job_id (str): Job identifier for the event stream.
        next_cursor (str): Cursor used to fetch subsequent events.
    """

    events: list[JobEvent]
    job_id: str
    next_cursor: str

    def to_dict(self) -> dict[str, Any]:
        """Serialize this model to a JSON-compatible dict.

        Args:
            None.

        Returns:
            dict[str, Any]: Serialized event envelope.
        """
        events = []
        for events_item_data in self.events:
            events_item = events_item_data.to_dict()
            events.append(events_item)

        job_id = self.job_id

        next_cursor = self.next_cursor

        field_dict: dict[str, Any] = {}

        field_dict.update(
            {
                "events": events,
                "job_id": job_id,
                "next_cursor": next_cursor,
            }
        )

        return field_dict

    @classmethod
    def from_dict(cls: type[T], src_dict: Mapping[str, Any]) -> T:
        """Build this model from a JSON-compatible mapping.

        Args:
            src_dict (Mapping[str, Any]): Source mapping used to create
                the model.

        Returns:
            JobEventsResponse: Parsed model instance.

        Raises:
            TypeError: If src_dict is missing required fields.
        """
        from nova_sdk_py_file.models.job_event import JobEvent

        d = dict(src_dict)
        events = []
        _events = d.pop("events")
        for events_item_data in _events:
            events_item = JobEvent.from_dict(events_item_data)

            events.append(events_item)

        job_id = d.pop("job_id")

        next_cursor = d.pop("next_cursor")

        job_events_response = cls(
            events=events,
            job_id=job_id,
            next_cursor=next_cursor,
        )

        return job_events_response
