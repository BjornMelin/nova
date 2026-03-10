"""Request parsing helpers for nova-auth-api."""

from __future__ import annotations

from json import JSONDecodeError
from typing import Annotated, Any
from urllib.parse import parse_qs

from fastapi import Depends, Request
from fastapi.exceptions import RequestValidationError
from pydantic import ValidationError

from nova_auth_api.models import TokenIntrospectRequest

FORM_MEDIA_TYPE = "application/x-www-form-urlencoded"
JSON_MEDIA_TYPE = "application/json"
TOKEN_INTROSPECT_JSON_REQUEST_SCHEMA_REF = {
    "$ref": "#/components/schemas/TokenIntrospectRequest"
}
TOKEN_INTROSPECT_FORM_REQUEST_SCHEMA_REF = {
    "$ref": "#/components/schemas/TokenIntrospectFormRequest"
}
INTROSPECT_REQUEST_BODY: dict[str, Any] = {
    "required": True,
    "content": {
        JSON_MEDIA_TYPE: {"schema": TOKEN_INTROSPECT_JSON_REQUEST_SCHEMA_REF},
        FORM_MEDIA_TYPE: {"schema": TOKEN_INTROSPECT_FORM_REQUEST_SCHEMA_REF},
    },
}
TOKEN_INTROSPECT_REQUEST_SCHEMA = TokenIntrospectRequest.model_json_schema(
    ref_template="#/components/schemas/{model}"
)
TOKEN_INTROSPECT_FORM_REQUEST_SCHEMA = {
    **TOKEN_INTROSPECT_REQUEST_SCHEMA,
    "title": "TokenIntrospectFormRequest",
}


async def parse_introspect_request(
    request: Request,
) -> TokenIntrospectRequest:
    """Parse token-introspection payloads from JSON or RFC7662 forms.

    Args:
        request: Incoming FastAPI request object.

    Returns:
        Validated introspection request payload.

    Raises:
        RequestValidationError: If payload decoding fails, if the payload is not
            a mapping, or if request validation fails.
    """
    media_type = request_media_type(request=request)
    if media_type == FORM_MEDIA_TYPE:
        raw_payload = parse_form_payload(body=await request.body())
    else:
        try:
            raw_payload = await request.json()
        except (JSONDecodeError, UnicodeDecodeError) as exc:
            raise RequestValidationError(
                [
                    {
                        "type": "json_invalid",
                        "loc": ("body",),
                        "msg": "JSON decode error",
                        "input": None,
                    }
                ]
            ) from exc

    if not isinstance(raw_payload, dict):
        raise RequestValidationError(
            [
                {
                    "type": "model_attributes_type",
                    "loc": ("body",),
                    "msg": "Input should be a valid dictionary",
                    "input": None,
                }
            ]
        )

    normalized_payload = normalize_introspect_payload(raw_payload=raw_payload)
    try:
        return TokenIntrospectRequest.model_validate(normalized_payload)
    except ValidationError as exc:
        raise RequestValidationError(
            with_body_loc(errors=exc.errors(include_input=False))
        ) from exc


IntrospectRequestDep = Annotated[
    TokenIntrospectRequest,
    Depends(parse_introspect_request),
]


def request_media_type(*, request: Request) -> str:
    """Return the normalized request content type.

    Args:
        request: Incoming FastAPI request object.

    Returns:
        Normalized content type, defaulting to JSON media type.
    """
    value = request.headers.get("content-type")
    if not isinstance(value, str):
        return JSON_MEDIA_TYPE
    return value.split(";", 1)[0].strip().lower()


def parse_form_payload(*, body: bytes) -> dict[str, Any]:
    """Parse UTF-8 form-encoded introspection bodies."""
    try:
        decoded_body = body.decode("utf-8")
    except UnicodeDecodeError as exc:
        raise RequestValidationError(
            [
                {
                    "type": "unicode_decode_error",
                    "loc": ("body",),
                    "msg": "request body must be UTF-8 encoded",
                    "input": None,
                }
            ]
        ) from exc

    parsed = parse_qs(decoded_body, keep_blank_values=True)
    payload: dict[str, Any] = {}
    for key, values in parsed.items():
        if key in {"required_scopes", "required_permissions"}:
            payload[key] = values
            continue
        payload[key] = values[-1] if values else ""
    return payload


def normalize_introspect_payload(
    *,
    raw_payload: dict[str, Any],
) -> dict[str, Any]:
    """Normalize RFC7662 form names into the canonical request payload."""
    payload = dict(raw_payload)
    token_value = payload.get("token")
    if "access_token" not in payload and token_value is not None:
        payload["access_token"] = token_value
    payload.pop("token", None)
    payload.pop("token_type_hint", None)
    return payload


def with_body_loc(*, errors: list[Any]) -> list[dict[str, Any]]:
    """Prefix validation locations with body for request-body errors."""
    output: list[dict[str, Any]] = []
    for error in errors:
        if not isinstance(error, dict):
            continue
        output.append(
            {
                **error,
                "loc": ("body", *error.get("loc", ())),
            }
        )
    return output
