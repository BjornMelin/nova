"""HTTP and public capability checks for runtime release validation."""

from __future__ import annotations

import json
from typing import Any, cast
from urllib.error import HTTPError, URLError
from urllib.parse import urlsplit
from urllib.request import Request, urlopen

from scripts.release.validate_runtime_release_shared import record_assertion
from scripts.release.validate_runtime_release_types import (
    AssertionCheck,
    RequestResult,
    RouteCheck,
)

TRANSFER_CAPABILITIES_PATH = "/v1/capabilities/transfers"
CORS_ALLOWED_HEADERS = {
    "authorization",
    "content-type",
    "idempotency-key",
}


def parse_json_object(payload: bytes | None, *, url: str) -> dict[str, Any]:
    """Parse one JSON response body into an object."""
    if payload is None:
        raise ValueError(f"Missing JSON response body for {url}")
    try:
        parsed = json.loads(payload.decode("utf-8"))
    except UnicodeDecodeError as exc:
        raise ValueError(f"Invalid UTF-8 JSON response body for {url}") from exc
    if not isinstance(parsed, dict):
        raise TypeError(f"JSON response must be an object for {url}")
    return parsed


def ceil_div(numerator: int, denominator: int) -> int:
    """Return the integer ceiling of ``numerator / denominator``."""
    return -(-numerator // denominator)


def request(
    url: str,
    *,
    method: str = "GET",
    headers: dict[str, str] | None = None,
    body: bytes | None = None,
) -> RequestResult:
    """Fetch one URL while preserving HTTP and transport errors."""
    parsed = urlsplit(url)
    if parsed.scheme != "https":
        raise ValueError(f"Validation fetch requires https URL: {url}")
    outbound = Request(  # noqa: S310 - scheme is checked above.
        url=url,
        method=method,
        headers=headers or {},
        data=body,
    )
    try:
        with urlopen(outbound, timeout=10) as response:  # noqa: S310
            return RequestResult(
                status_code=int(response.getcode()),
                headers={
                    key.lower(): value
                    for key, value in response.headers.items()
                },
                body=response.read(),
                error=None,
            )
    except HTTPError as exc:
        return RequestResult(
            status_code=int(exc.code),
            headers={key.lower(): value for key, value in exc.headers.items()},
            body=exc.read(),
            error=None,
        )
    except URLError as exc:
        return RequestResult(
            status_code=None,
            headers={},
            body=None,
            error=f"Request failed for {url}: {exc}",
        )


def record_check(
    *,
    checks: list[RouteCheck],
    failures: list[str],
    kind: str,
    method: str,
    path: str,
    expected: str,
    result: RequestResult,
    ok: bool,
) -> None:
    """Record one validation check and failure message when it fails."""
    checks.append(
        RouteCheck(
            kind=kind,
            method=method,
            path=path,
            expected=expected,
            status_code=0 if result.status_code is None else result.status_code,
            ok=ok,
        )
    )
    if ok:
        return
    if result.error:
        failures.append(f"{kind} {method} {path} request error: {result.error}")
        return
    failures.append(
        f"{kind} {method} {path} returned "
        f"{0 if result.status_code is None else result.status_code}"
    )


def validate_transfer_capabilities(
    *,
    base_url: str,
    representative_upload_bytes: int,
    checks: list[RouteCheck],
    capability_checks: list[AssertionCheck],
    failures: list[str],
) -> None:
    """Validate the public transfer policy envelope exposed by the runtime."""
    result = request(base_url + TRANSFER_CAPABILITIES_PATH)
    route_ok = result.error is None and result.status_code == 200
    record_check(
        checks=checks,
        failures=failures,
        kind="transfer_capabilities",
        method="GET",
        path=TRANSFER_CAPABILITIES_PATH,
        expected=(
            "status == 200 and payload exposes the effective transfer "
            "policy envelope"
        ),
        result=result,
        ok=route_ok,
    )
    if not route_ok:
        return

    try:
        payload = parse_json_object(
            result.body,
            url=base_url + TRANSFER_CAPABILITIES_PATH,
        )
    except (TypeError, ValueError, json.JSONDecodeError) as exc:
        failures.append(str(exc))
        return

    policy_id = payload.get("policy_id")
    policy_version = payload.get("policy_version")
    max_upload_bytes = payload.get("max_upload_bytes")
    target_upload_part_count = payload.get("target_upload_part_count")
    minimum_part_size_bytes = payload.get("minimum_part_size_bytes")
    maximum_part_size_bytes = payload.get("maximum_part_size_bytes")
    sign_batch_size_hint = payload.get("sign_batch_size_hint")
    accelerate_enabled = payload.get("accelerate_enabled")
    checksum_mode = payload.get("checksum_mode")
    active_multipart_upload_limit = payload.get("active_multipart_upload_limit")
    daily_ingress_budget_bytes = payload.get("daily_ingress_budget_bytes")
    sign_requests_per_upload_limit = payload.get(
        "sign_requests_per_upload_limit"
    )
    large_export_worker_threshold_bytes = payload.get(
        "large_export_worker_threshold_bytes"
    )

    typed_values_ok = all(
        (
            isinstance(policy_id, str) and policy_id.strip(),
            isinstance(policy_version, str) and policy_version.strip(),
            isinstance(max_upload_bytes, int) and max_upload_bytes > 0,
            isinstance(target_upload_part_count, int)
            and target_upload_part_count > 0,
            isinstance(minimum_part_size_bytes, int)
            and minimum_part_size_bytes > 0,
            isinstance(maximum_part_size_bytes, int)
            and maximum_part_size_bytes > 0,
            isinstance(sign_batch_size_hint, int) and sign_batch_size_hint > 0,
            isinstance(accelerate_enabled, bool),
            isinstance(checksum_mode, str) and checksum_mode.strip(),
            isinstance(active_multipart_upload_limit, int)
            and active_multipart_upload_limit > 0,
            isinstance(daily_ingress_budget_bytes, int)
            and daily_ingress_budget_bytes > 0,
            isinstance(sign_requests_per_upload_limit, int)
            and sign_requests_per_upload_limit > 0,
            isinstance(large_export_worker_threshold_bytes, int)
            and large_export_worker_threshold_bytes > 0,
        )
    )
    if not typed_values_ok:
        failures.append(
            "transfer capabilities payload is missing one or more required "
            "typed fields"
        )
        return

    policy_id = cast(str, policy_id)
    policy_version = cast(str, policy_version)
    max_upload_bytes = cast(int, max_upload_bytes)
    target_upload_part_count = cast(int, target_upload_part_count)
    minimum_part_size_bytes = cast(int, minimum_part_size_bytes)
    maximum_part_size_bytes = cast(int, maximum_part_size_bytes)
    sign_batch_size_hint = cast(int, sign_batch_size_hint)
    checksum_mode = cast(str, checksum_mode)
    active_multipart_upload_limit = cast(int, active_multipart_upload_limit)
    daily_ingress_budget_bytes = cast(int, daily_ingress_budget_bytes)
    sign_requests_per_upload_limit = cast(int, sign_requests_per_upload_limit)
    large_export_worker_threshold_bytes = cast(
        int, large_export_worker_threshold_bytes
    )

    derived_part_size = min(
        maximum_part_size_bytes,
        max(
            minimum_part_size_bytes,
            ceil_div(representative_upload_bytes, target_upload_part_count),
        ),
    )
    estimated_part_count = ceil_div(
        representative_upload_bytes,
        derived_part_size,
    )
    estimated_sign_requests = ceil_div(
        estimated_part_count,
        sign_batch_size_hint,
    )

    record_assertion(
        checks=capability_checks,
        failures=failures,
        name="policy_id_non_empty",
        expected="non-empty string",
        actual=policy_id,
        ok=bool(policy_id),
    )
    record_assertion(
        checks=capability_checks,
        failures=failures,
        name="policy_version_non_empty",
        expected="non-empty string",
        actual=policy_version,
        ok=bool(policy_version),
    )
    record_assertion(
        checks=capability_checks,
        failures=failures,
        name="representative_upload_allowed",
        expected=f">= {representative_upload_bytes}",
        actual=max_upload_bytes,
        ok=max_upload_bytes >= representative_upload_bytes,
    )
    record_assertion(
        checks=capability_checks,
        failures=failures,
        name="part_size_bounds_consistent",
        expected="minimum_part_size_bytes <= maximum_part_size_bytes",
        actual={
            "minimum_part_size_bytes": minimum_part_size_bytes,
            "maximum_part_size_bytes": maximum_part_size_bytes,
        },
        ok=minimum_part_size_bytes <= maximum_part_size_bytes,
    )
    record_assertion(
        checks=capability_checks,
        failures=failures,
        name="checksum_mode_supported",
        expected="one of none, optional, required",
        actual=checksum_mode,
        ok=checksum_mode in {"none", "optional", "required"},
    )
    record_assertion(
        checks=capability_checks,
        failures=failures,
        name="sign_batch_size_hint_floor",
        expected=">= 32",
        actual=sign_batch_size_hint,
        ok=sign_batch_size_hint >= 32,
    )
    record_assertion(
        checks=capability_checks,
        failures=failures,
        name="daily_ingress_budget_covers_representative_upload",
        expected=f">= {representative_upload_bytes}",
        actual=daily_ingress_budget_bytes,
        ok=daily_ingress_budget_bytes >= representative_upload_bytes,
    )
    record_assertion(
        checks=capability_checks,
        failures=failures,
        name="large_export_worker_threshold_above_single_copy_limit",
        expected=f"> {5 * 1024 * 1024 * 1024}",
        actual=large_export_worker_threshold_bytes,
        ok=large_export_worker_threshold_bytes > 5 * 1024 * 1024 * 1024,
    )
    record_assertion(
        checks=capability_checks,
        failures=failures,
        name="estimated_part_count_for_representative_upload",
        expected="between 1000 and 2000",
        actual=estimated_part_count,
        ok=1000 <= estimated_part_count <= 2000,
    )
    record_assertion(
        checks=capability_checks,
        failures=failures,
        name="estimated_sign_requests_for_representative_upload",
        expected="<= 64",
        actual=estimated_sign_requests,
        ok=estimated_sign_requests <= 64,
    )
    record_assertion(
        checks=capability_checks,
        failures=failures,
        name="sign_requests_per_upload_limit_covers_representative_upload",
        expected=f">= {estimated_sign_requests}",
        actual=sign_requests_per_upload_limit,
        ok=sign_requests_per_upload_limit >= estimated_sign_requests,
    )


def validate_cors_preflight(
    *,
    base_url: str,
    path: str,
    origin: str,
    checks: list[RouteCheck],
    failures: list[str],
) -> None:
    """Validate the browser preflight contract for one protected path."""
    result = request(
        base_url + path,
        method="OPTIONS",
        headers={
            "Origin": origin,
            "Access-Control-Request-Method": "POST",
            "Access-Control-Request-Headers": (
                "Authorization,Content-Type,Idempotency-Key"
            ),
        },
    )
    allow_origin = result.headers.get("access-control-allow-origin", "")
    allow_methods = {
        item.strip().upper()
        for item in result.headers.get(
            "access-control-allow-methods", ""
        ).split(",")
        if item.strip()
    }
    allow_headers = {
        item.strip().lower()
        for item in result.headers.get(
            "access-control-allow-headers", ""
        ).split(",")
        if item.strip()
    }
    ok = (
        result.error is None
        and result.status_code in {200, 204}
        and allow_origin in {"*", origin}
        and "POST" in allow_methods
        and allow_headers >= CORS_ALLOWED_HEADERS
    )
    record_check(
        checks=checks,
        failures=failures,
        kind="cors_preflight",
        method="OPTIONS",
        path=path,
        expected=(
            "status in {200,204}, allow-origin matches configured origin or "
            "*, POST allowed, and browser auth headers are allowed"
        ),
        result=result,
        ok=ok,
    )
