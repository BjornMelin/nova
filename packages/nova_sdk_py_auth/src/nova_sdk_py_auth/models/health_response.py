# ruff: noqa
from __future__ import annotations

from collections.abc import Mapping
from typing import (
    Any,
    Literal,
    TypeVar,
    cast,
)

from attrs import define as _attrs_define

T = TypeVar("T", bound="HealthResponse")


@_attrs_define
class HealthResponse:
    """Health check response payload.

    Attributes:
        request_id (str):
        service (Literal['nova-auth-api']):
        status (Literal['ok']):
    """

    request_id: str
    service: Literal["nova-auth-api"]
    status: Literal["ok"]

    def to_dict(self) -> dict[str, Any]:
        request_id = self.request_id

        service = self.service

        status = self.status

        field_dict: dict[str, Any] = {}

        field_dict.update(
            {
                "request_id": request_id,
                "service": service,
                "status": status,
            }
        )

        return field_dict

    @classmethod
    def from_dict(cls: type[T], src_dict: Mapping[str, Any]) -> T:
        d = dict(src_dict)
        request_id = d.pop("request_id")

        service = cast(Literal["nova-auth-api"], d.pop("service"))
        if service != "nova-auth-api":
            raise ValueError(
                f"service must match const 'nova-auth-api', got '{service}'"
            )

        status = cast(Literal["ok"], d.pop("status"))
        if status != "ok":
            raise ValueError(f"status must match const 'ok', got '{status}'")

        health_response = cls(
            request_id=request_id,
            service=service,
            status=status,
        )

        return health_response
