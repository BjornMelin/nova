# ruff: noqa
from __future__ import annotations

from collections.abc import Mapping
from typing import Any, TypeVar, cast

from attrs import define as _attrs_define

from nova_sdk_py_auth.types import UNSET, Unset

T = TypeVar("T", bound="TokenIntrospectFormRequest")


@_attrs_define
class TokenIntrospectFormRequest:
    """Request payload for token introspection.

    Attributes:
        access_token (str):
        required_permissions (list[str] | Unset):
        required_scopes (list[str] | Unset):
    """

    access_token: str
    required_permissions: list[str] | Unset = UNSET
    required_scopes: list[str] | Unset = UNSET

    def to_dict(self) -> dict[str, Any]:
        access_token = self.access_token

        required_permissions: list[str] | Unset = UNSET
        if not isinstance(self.required_permissions, Unset):
            required_permissions = list(self.required_permissions)

        required_scopes: list[str] | Unset = UNSET
        if not isinstance(self.required_scopes, Unset):
            required_scopes = list(self.required_scopes)

        field_dict: dict[str, Any] = {}

        field_dict.update(
            {
                "access_token": access_token,
            }
        )
        if required_permissions is not UNSET:
            field_dict["required_permissions"] = required_permissions
        if required_scopes is not UNSET:
            field_dict["required_scopes"] = required_scopes

        return field_dict

    @classmethod
    def from_dict(cls: type[T], src_dict: Mapping[str, Any]) -> T:
        d = dict(src_dict)
        access_token = d.pop("access_token")

        required_permissions = cast(
            list[str], d.pop("required_permissions", UNSET)
        )

        def _parse_required_scopes(data: object) -> list[str] | Unset:
            if isinstance(data, Unset):
                return data
            if not isinstance(data, list):
                raise TypeError("required_scopes must be a list when set")
            return cast(list[str], data)

        required_scopes = _parse_required_scopes(
            d.pop("required_scopes", UNSET)
        )

        token_introspect_form_request = cls(
            access_token=access_token,
            required_permissions=required_permissions,
            required_scopes=required_scopes,
        )

        return token_introspect_form_request
