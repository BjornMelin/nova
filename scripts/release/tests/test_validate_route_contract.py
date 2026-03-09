from __future__ import annotations

from scripts.release.validate_route_contract import _parse_paths


def test_parse_paths_reads_method_and_status_expectations() -> None:
    expectations = _parse_paths(
        "POST:/v1/token/verify=400|422,/v1/health/live",
        default_statuses=(200,),
    )

    assert expectations[0].method == "POST"
    assert expectations[0].path == "/v1/token/verify"
    assert expectations[0].allowed_statuses == (400, 422)
    assert expectations[1].method == "GET"
    assert expectations[1].path == "/v1/health/live"
    assert expectations[1].allowed_statuses == (200,)
