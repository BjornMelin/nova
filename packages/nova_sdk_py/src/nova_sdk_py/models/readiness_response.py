from __future__ import annotations

from collections.abc import Mapping
from typing import (
    TYPE_CHECKING,
    Any,
    TypeVar,
)

from attrs import define as _attrs_define

if TYPE_CHECKING:
    from nova_sdk_py.models.readiness_checks import ReadinessChecks


T = TypeVar("T", bound="ReadinessResponse")


@_attrs_define
class ReadinessResponse:
    """
    Readiness endpoint response body.

    Attributes:
        checks: Canonical live traffic-gate results.
        ok: Whether every required traffic dependency is ready.
    """

    checks: ReadinessChecks
    """Canonical live traffic gates reported by readiness."""
    ok: bool
    """Whether every required traffic dependency is ready."""

    def to_dict(self) -> dict[str, Any]:
        checks = self.checks.to_dict()

        ok = self.ok

        field_dict: dict[str, Any] = {}

        field_dict.update(
            {
                "checks": checks,
                "ok": ok,
            }
        )

        return field_dict

    @classmethod
    def from_dict(cls: type[T], src_dict: Mapping[str, Any]) -> T:
        from nova_sdk_py.models.readiness_checks import ReadinessChecks

        d = dict(src_dict)
        checks = ReadinessChecks.from_dict(d.pop("checks"))

        ok = d.pop("ok")

        readiness_response = cls(
            checks=checks,
            ok=ok,
        )

        return readiness_response
