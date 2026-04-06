from __future__ import annotations

from collections.abc import Mapping
from typing import Any, TypeVar

from attrs import define as _attrs_define

T = TypeVar("T", bound="ReleaseInfoResponse")


@_attrs_define
class ReleaseInfoResponse:
    """Release metadata for conformance/debug clients."""

    environment: str
    name: str
    version: str

    def to_dict(self) -> dict[str, Any]:
        environment = self.environment

        name = self.name

        version = self.version

        field_dict: dict[str, Any] = {}

        field_dict.update(
            {
                "environment": environment,
                "name": name,
                "version": version,
            }
        )

        return field_dict

    @classmethod
    def from_dict(cls: type[T], src_dict: Mapping[str, Any]) -> T:
        d = dict(src_dict)
        environment = d.pop("environment")

        name = d.pop("name")

        version = d.pop("version")

        release_info_response = cls(
            environment=environment,
            name=name,
            version=version,
        )

        return release_info_response
