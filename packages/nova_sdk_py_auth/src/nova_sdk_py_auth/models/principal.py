from __future__ import annotations

from collections.abc import Mapping
from typing import Any, TypeVar, cast

from attrs import define as _attrs_define

from ..types import UNSET, Unset

T = TypeVar("T", bound="Principal")


@_attrs_define
class Principal:
    """Authorized caller identity resolved from token claims.

    Attributes:
        scope_id (str):
        subject (str):
        permissions (list[str] | Unset):
        scopes (list[str] | Unset):
        tenant_id (None | str | Unset):
    """

    scope_id: str
    subject: str
    permissions: list[str] | Unset = UNSET
    scopes: list[str] | Unset = UNSET
    tenant_id: None | str | Unset = UNSET

    def to_dict(self) -> dict[str, Any]:
        scope_id = self.scope_id

        subject = self.subject

        permissions: list[str] | Unset = UNSET
        if not isinstance(self.permissions, Unset):
            permissions = self.permissions

        scopes: list[str] | Unset = UNSET
        if not isinstance(self.scopes, Unset):
            scopes = self.scopes

        tenant_id: None | str | Unset
        if isinstance(self.tenant_id, Unset):
            tenant_id = UNSET
        else:
            tenant_id = self.tenant_id

        field_dict: dict[str, Any] = {}

        field_dict.update(
            {
                "scope_id": scope_id,
                "subject": subject,
            }
        )
        if permissions is not UNSET:
            field_dict["permissions"] = permissions
        if scopes is not UNSET:
            field_dict["scopes"] = scopes
        if tenant_id is not UNSET:
            field_dict["tenant_id"] = tenant_id

        return field_dict

    @classmethod
    def from_dict(cls: type[T], src_dict: Mapping[str, Any]) -> T:
        d = dict(src_dict)
        scope_id = d.pop("scope_id")

        subject = d.pop("subject")

        permissions = cast(list[str], d.pop("permissions", UNSET))

        scopes = cast(list[str], d.pop("scopes", UNSET))

        def _parse_tenant_id(data: object) -> None | str | Unset:
            if data is None:
                return data
            if isinstance(data, Unset):
                return data
            return cast(None | str | Unset, data)

        tenant_id = _parse_tenant_id(d.pop("tenant_id", UNSET))

        principal = cls(
            scope_id=scope_id,
            subject=subject,
            permissions=permissions,
            scopes=scopes,
            tenant_id=tenant_id,
        )

        return principal
