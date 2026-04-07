from __future__ import annotations

from collections.abc import Mapping
from typing import Any, TypeVar

from attrs import define as _attrs_define

T = TypeVar("T", bound="ReadinessChecks")


@_attrs_define
class ReadinessChecks:
    """
    Canonical live traffic gates reported by readiness.

    Attributes:
        activity_store: Whether the activity store is reachable for
        diagnostic rollups.
        auth_dependency: Whether the configured bearer-token verifier can
        currently resolve signing keys.
        export_runtime: Whether the export publisher and export repository
        are ready.
        idempotency_store: Whether the idempotency store is reachable when
        idempotency is enabled.
        transfer_runtime: Whether transfer persistence and the configured S3
        bucket are ready.
    """

    activity_store: bool
    """Whether the activity store is reachable for diagnostic rollups."""
    auth_dependency: bool
    """
    Whether the configured bearer-token verifier can currently resolve signing keys.
    """
    export_runtime: bool
    """Whether the export publisher and export repository are ready."""
    idempotency_store: bool
    """Whether the idempotency store is reachable when idempotency is enabled."""
    transfer_runtime: bool
    """Whether transfer persistence and the configured S3 bucket are ready."""

    def to_dict(self) -> dict[str, Any]:
        activity_store = self.activity_store

        auth_dependency = self.auth_dependency

        export_runtime = self.export_runtime

        idempotency_store = self.idempotency_store

        transfer_runtime = self.transfer_runtime

        field_dict: dict[str, Any] = {}

        field_dict.update(
            {
                "activity_store": activity_store,
                "auth_dependency": auth_dependency,
                "export_runtime": export_runtime,
                "idempotency_store": idempotency_store,
                "transfer_runtime": transfer_runtime,
            }
        )

        return field_dict

    @classmethod
    def from_dict(cls: type[T], src_dict: Mapping[str, Any]) -> T:
        d = dict(src_dict)
        activity_store = d.pop("activity_store")

        auth_dependency = d.pop("auth_dependency")

        export_runtime = d.pop("export_runtime")

        idempotency_store = d.pop("idempotency_store")

        transfer_runtime = d.pop("transfer_runtime")

        readiness_checks = cls(
            activity_store=activity_store,
            auth_dependency=auth_dependency,
            export_runtime=export_runtime,
            idempotency_store=idempotency_store,
            transfer_runtime=transfer_runtime,
        )

        return readiness_checks
