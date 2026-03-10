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
    """
    Parse an incoming HTTP request into a validated TokenIntrospectRequest.
    
    Accepts either JSON or RFC7662 application/x-www-form-urlencoded form payloads, normalizes RFC7662 field names, and validates the resulting payload against the TokenIntrospectRequest model.
    
    Parameters:
        request (Request): The incoming HTTP request to parse.
    
    Returns:
        TokenIntrospectRequest: A validated introspection request model.
    
    Raises:
        RequestValidationError: If the request body contains invalid JSON or cannot be decoded, if the parsed body is not a mapping, or if model validation fails (errors will be scoped to the request body).
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
    """
    Determine the normalized media type from the request's Content-Type header.
    
    Strips any parameters (everything after ';'), trims whitespace, and lowercases the result. Defaults to "application/json" when the header is missing or not a string.
    
    Returns:
        media_type (str): The normalized media type (e.g. "application/json", "application/x-www-form-urlencoded").
    """
    value = request.headers.get("content-type")
    if not isinstance(value, str):
        return JSON_MEDIA_TYPE
    return value.split(";", 1)[0].strip().lower()


def parse_form_payload(*, body: bytes) -> dict[str, Any]:
    """
    Parse an x-www-form-urlencoded introspection request body into a normalized payload dictionary.
    
    Decodes the raw bytes as UTF-8, parses the form-encoded string into keys and values, and returns a dictionary where:
    - "required_scopes" and "required_permissions" map to the full list of values (list[str]).
    - All other keys map to the last value provided for that key, or an empty string if no value was provided.
    
    Parameters:
        body (bytes): Raw request body.
    
    Returns:
        dict[str, Any]: Parsed payload with string keys and either str or list[str] values.
    
    Raises:
        RequestValidationError: If the body cannot be decoded as UTF-8; the error will include a `"type": "unicode_decode_error"` entry.
    """
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
    """
    Normalize an introspection request payload to canonical field names.
    
    Parameters:
    	raw_payload (dict[str, Any]): Parsed request payload (form-encoded or JSON).
    
    Returns:
    	normalized_payload (dict[str, Any]): Copy of the payload where a present `token` value is copied to `access_token` if `access_token` is missing, and the keys `token` and `token_type_hint` are removed.
    """
    payload = dict(raw_payload)
    token_value = payload.get("token")
    if "access_token" not in payload and token_value is not None:
        payload["access_token"] = token_value
    payload.pop("token", None)
    payload.pop("token_type_hint", None)
    return payload


def with_body_loc(*, errors: list[Any]) -> list[dict[str, Any]]:
    """
    Prefix the `loc` entries of validation error dictionaries with `"body"`.
    
    Non-dictionary entries in `errors` are ignored. For each dictionary error, returns a shallow copy with its `loc` value replaced by a tuple starting with `"body"` followed by the original location components (uses an empty tuple if `loc` is missing).
    
    Parameters:
        errors (list[Any]): A list of validation error objects; dictionary entries are processed, others are skipped.
    
    Returns:
        list[dict[str, Any]]: A list of error dictionaries with `loc` values prefixed by `"body"`.
    """
    output: list[dict[str, Any]] = []
    for error in errors:
        if not isinstance(error, dict):
            continue
        output.append(
            {
                **error,
                "loc": ("body", *list(error.get("loc", ()))),
            }
        )
    return output
