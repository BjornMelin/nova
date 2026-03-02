from __future__ import annotations

from fastapi.testclient import TestClient
from nova_file_api.app import create_app


def test_v1_health_and_capabilities() -> None:
    app = create_app()
    with TestClient(app) as client:
        live = client.get("/v1/health/live")
        ready = client.get("/v1/health/ready")
        caps = client.get("/v1/capabilities")

    assert live.status_code == 200
    assert live.json() == {"ok": True}
    assert ready.status_code == 200
    assert "checks" in ready.json()
    assert caps.status_code == 200
    cap_keys = {entry["key"] for entry in caps.json()["capabilities"]}
    assert {"jobs", "jobs.events.poll", "transfers"}.issubset(cap_keys)


def test_v1_jobs_create_list_get_retry_and_events() -> None:
    app = create_app()
    with TestClient(app) as client:
        create_resp = client.post(
            "/v1/jobs",
            headers={"X-Session-Id": "scope-v1"},
            json={"job_type": "transform", "payload": {"input": "a"}},
        )
        assert create_resp.status_code == 200
        created = create_resp.json()
        job_id = created["job_id"]

        list_resp = client.get("/v1/jobs", headers={"X-Session-Id": "scope-v1"})
        assert list_resp.status_code == 200
        assert any(
            item["job_id"] == job_id for item in list_resp.json()["jobs"]
        )

        get_resp = client.get(
            f"/v1/jobs/{job_id}",
            headers={"X-Session-Id": "scope-v1"},
        )
        assert get_resp.status_code == 200
        assert get_resp.json()["job"]["job_id"] == job_id

        retry_resp = client.post(
            f"/v1/jobs/{job_id}/retry",
            headers={"X-Session-Id": "scope-v1"},
        )
        assert retry_resp.status_code == 409

        events_resp = client.get(
            f"/v1/jobs/{job_id}/events",
            headers={"X-Session-Id": "scope-v1"},
        )
        assert events_resp.status_code == 200
        events = events_resp.json()["events"]
        assert len(events) == 1
        assert events[0]["job_id"] == job_id


def test_v1_resource_plan_and_release_info() -> None:
    app = create_app()
    with TestClient(app) as client:
        plan = client.post(
            "/v1/resources/plan", json={"resources": ["jobs", "unknown"]}
        )
        info = client.get("/v1/releases/info")

    assert plan.status_code == 200
    payload = plan.json()
    assert len(payload["plan"]) == 2
    unknown = [i for i in payload["plan"] if i["resource"] == "unknown"][0]
    assert unknown["supported"] is False
    assert unknown["reason"] == "unsupported_resource"

    assert info.status_code == 200
    release = info.json()
    assert release["name"]
    assert release["version"]


def test_v1_jobs_rejects_blank_idempotency_key() -> None:
    app = create_app()
    with TestClient(app) as client:
        resp = client.post(
            "/v1/jobs",
            headers={
                "X-Session-Id": "scope-v1",
                "Idempotency-Key": "",
            },
            json={"job_type": "transform", "payload": {"input": "a"}},
        )
    assert resp.status_code == 422
    assert resp.json()["error"]["code"] == "invalid_request"
