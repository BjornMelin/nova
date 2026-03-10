# ruff: noqa
from __future__ import annotations

from collections.abc import Mapping
from typing import Any, TypeVar, cast

from attrs import define as _attrs_define
from attrs import field as _attrs_field

from nova_sdk_py_auth.types import UNSET, Unset

T = TypeVar("T", bound="TokenIntrospectFormRequest")


@_attrs_define
class TokenIntrospectFormRequest:
    """RFC7662 form payload where token is rewritten to access_token by normalize_introspect_payload.

    Attributes:
        token (str): RFC7662 token value rewritten to access_token.
        required_permissions (list[str] | Unset):
        required_scopes (list[str] | Unset):
        token_type_hint (str | Unset): Optional RFC7662 token type hint.
    """

    token: str
    required_permissions: list[str] | Unset = UNSET
    required_scopes: list[str] | Unset = UNSET
    token_type_hint: str | Unset = UNSET

    def to_dict(self) -> dict[str, Any]:
        """Serialize this model to a JSON-compatible dict.

        Args:
            None.

        Returns:
            dict[str, Any]: Serialized token verification payload.
        """
        token = self.token

        required_permissions: list[str] | Unset = UNSET
        if not isinstance(self.required_permissions, Unset):
            required_permissions = list(self.required_permissions)

        required_scopes: list[str] | Unset = UNSET
        if not isinstance(self.required_scopes, Unset):
            required_scopes = list(self.required_scopes)

        token_type_hint = self.token_type_hint

        field_dict: dict[str, Any] = {}

        field_dict.update(
            {
                "token": token,
            }
        )
        if required_permissions is not UNSET:
            field_dict["required_permissions"] = required_permissions
        if required_scopes is not UNSET:
            field_dict["required_scopes"] = required_scopes
        if token_type_hint is not UNSET:
            field_dict["token_type_hint"] = token_type_hint

        return field_dict

    @classmethod
    def from_dict(cls: type[T], src_dict: Mapping[str, Any]) -> T:
        d = dict(src_dict)
        token = d.pop("token")

        def _parse_required_permissions(data: object) -> list[str] | Unset:
            if isinstance(data, Unset):
                return data
            if not isinstance(data, list):
                raise TypeError("required_permissions must be a list when set")
            return cast(list[str], data)

        required_permissions = _parse_required_permissions(
            d.pop("required_permissions", UNSET)
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

        token_type_hint = d.pop("token_type_hint", UNSET)

        token_introspect_form_request = cls(
            token=token,
            required_permissions=required_permissions,
            required_scopes=required_scopes,
            token_type_hint=token_type_hint,
        )

        return token_introspect_form_request
