from __future__ import annotations

from collections.abc import Mapping
from typing import TYPE_CHECKING, Any, TypeVar

from attrs import define as _attrs_define

if TYPE_CHECKING:
    from ..models.principal import Principal
    from ..models.token_verify_response_claims import TokenVerifyResponseClaims


T = TypeVar("T", bound="TokenVerifyResponse")


@_attrs_define
class TokenVerifyResponse:
    """Response payload for token verification.

    Attributes:
        claims (TokenVerifyResponseClaims):
        principal (Principal): Authorized caller identity resolved from token claims.
    """

    claims: TokenVerifyResponseClaims
    principal: Principal

    def to_dict(self) -> dict[str, Any]:
        claims = self.claims.to_dict()

        principal = self.principal.to_dict()

        field_dict: dict[str, Any] = {}

        field_dict.update(
            {
                "claims": claims,
                "principal": principal,
            }
        )

        return field_dict

    @classmethod
    def from_dict(cls: type[T], src_dict: Mapping[str, Any]) -> T:
        from ..models.principal import Principal
        from ..models.token_verify_response_claims import (
            TokenVerifyResponseClaims,
        )

        d = dict(src_dict)
        claims = TokenVerifyResponseClaims.from_dict(d.pop("claims"))

        principal = Principal.from_dict(d.pop("principal"))

        token_verify_response = cls(
            claims=claims,
            principal=principal,
        )

        return token_verify_response
