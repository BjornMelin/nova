# ruff: noqa
from __future__ import annotations

from collections.abc import Mapping
from typing import Any, TypeVar

from attrs import define as _attrs_define

T = TypeVar("T", bound="HealthResponse")


@_attrs_define
class HealthResponse:
    """Health endpoint response body.

    Attributes:
        ok (bool):
    """

    ok: bool

    def to_dict(self) -> dict[str, Any]:
        """Serialize this model to a JSON-compatible dict."""
        ok = self.ok

        field_dict: dict[str, Any] = {}

        field_dict.update(
            {
                "ok": ok,
            }
        )

        return field_dict

    @classmethod
    def from_dict(cls: type[T], src_dict: Mapping[str, Any]) -> T:
        """Build this model from a JSON-compatible mapping."""
        d = dict(src_dict)
        ok = d.pop("ok")

        health_response = cls(
            ok=ok,
        )

        return health_response
