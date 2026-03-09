from __future__ import annotations

from collections.abc import Mapping
from typing import TYPE_CHECKING, Any, TypeVar, cast

from attrs import define as _attrs_define

from ..types import UNSET, Unset

if TYPE_CHECKING:
    from ..models.principal import Principal
    from ..models.token_introspect_response_claims import (
        TokenIntrospectResponseClaims,
    )


T = TypeVar("T", bound="TokenIntrospectResponse")


@_attrs_define
class TokenIntrospectResponse:
    """Response payload for token introspection.

    Attributes:
        active (bool):
        claims (TokenIntrospectResponseClaims | Unset):
        principal (None | Principal | Unset):
    """

    active: bool
    claims: TokenIntrospectResponseClaims | Unset = UNSET
    principal: None | Principal | Unset = UNSET

    def to_dict(self) -> dict[str, Any]:
        from ..models.principal import Principal

        active = self.active

        claims: dict[str, Any] | Unset = UNSET
        if not isinstance(self.claims, Unset):
            claims = self.claims.to_dict()

        principal: dict[str, Any] | None | Unset
        if isinstance(self.principal, Unset):
            principal = UNSET
        elif isinstance(self.principal, Principal):
            principal = self.principal.to_dict()
        else:
            principal = self.principal

        field_dict: dict[str, Any] = {}

        field_dict.update(
            {
                "active": active,
            }
        )
        if claims is not UNSET:
            field_dict["claims"] = claims
        if principal is not UNSET:
            field_dict["principal"] = principal

        return field_dict

    @classmethod
    def from_dict(cls: type[T], src_dict: Mapping[str, Any]) -> T:
        from ..models.principal import Principal
        from ..models.token_introspect_response_claims import (
            TokenIntrospectResponseClaims,
        )

        d = dict(src_dict)
        active = d.pop("active")

        _claims = d.pop("claims", UNSET)
        claims: TokenIntrospectResponseClaims | Unset
        if isinstance(_claims, Unset):
            claims = UNSET
        else:
            claims = TokenIntrospectResponseClaims.from_dict(_claims)

        def _parse_principal(data: object) -> None | Principal | Unset:
            if data is None:
                return data
            if isinstance(data, Unset):
                return data
            try:
                if not isinstance(data, dict):
                    raise TypeError()
                principal_type_0 = Principal.from_dict(data)

                return principal_type_0
            except (TypeError, ValueError, AttributeError, KeyError):
                pass
            return cast(None | Principal | Unset, data)

        principal = _parse_principal(d.pop("principal", UNSET))

        token_introspect_response = cls(
            active=active,
            claims=claims,
            principal=principal,
        )

        return token_introspect_response
