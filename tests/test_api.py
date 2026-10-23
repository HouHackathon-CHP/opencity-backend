# SPDX-License-Identifier: Apache-2.0
import os

os.environ["INTERNAL_GATEWAY_SECRET"] = "test-secret"

from fastapi.testclient import TestClient  # noqa: E402
from app import main  # noqa: E402


client = TestClient(main.app)
CITIZEN = {"X-Internal-Secret": "test-secret", "X-DXOS-User": "citizen-1", "X-DXOS-Tenant": "tenant-1", "X-DXOS-Roles": "citizen"}


def test_direct_request_is_rejected():
    assert client.get("/reports").status_code == 403


def test_citizen_cannot_transition_a_report():
    assert client.post("/reports/report-1/actions/triage", headers=CITIZEN).status_code == 403


def test_invalid_category_is_rejected_before_core_call(monkeypatch):
    async def unexpected(*args, **kwargs):
        raise AssertionError("Core must not be called")

    monkeypatch.setattr(main, "core_json", unexpected)
    result = client.post("/reports", headers=CITIZEN, data={
        "title": "Đèn đường bị hỏng", "description": "Đèn đường đã không sáng trong nhiều ngày.",
        "category": "Không xác định", "address": "Phố thử nghiệm",
    })
    assert result.status_code == 422


def test_spoofed_image_is_rejected_before_core_call(monkeypatch):
    async def unexpected(*args, **kwargs):
        raise AssertionError("Core must not be called")

    monkeypatch.setattr(main, "core_json", unexpected)
    result = client.post("/reports", headers=CITIZEN, data={
        "title": "Đèn đường bị hỏng", "description": "Đèn đường đã không sáng trong nhiều ngày.",
        "category": "Chiếu sáng", "address": "Phố thử nghiệm",
    }, files={"photo": ("fake.png", b"not-an-image", "image/png")})
    assert result.status_code == 422


def test_create_report_uses_data_and_workflow(monkeypatch):
    calls = []

    async def fake_core(base, path, identity, method="GET", **kwargs):
        calls.append((base, path, method, identity.tenant))
        if path == "/records":
            payload = kwargs["json_body"]["payload"]
            return {"id": "record-1", "kind": "field-report", "payload": dict(payload),
                    "created_by": identity.user, "created_at": "2026-10-23T00:00:00Z", "updated_at": "2026-10-23T00:00:00Z"}
        if path == "/instances":
            return {"id": "workflow-1", "state": "submitted", "reference_id": "record-1"}
        if path == "/records/record-1":
            return {"id": "record-1", "kind": "field-report", "payload": kwargs["json_body"]["payload"],
                    "created_by": identity.user, "created_at": "2026-10-23T00:00:00Z", "updated_at": "2026-10-23T00:00:00Z"}
        raise AssertionError(f"Unexpected core call: {path}")

    monkeypatch.setattr(main, "core_json", fake_core)
    result = client.post("/reports", headers=CITIZEN, data={
        "title": "Đèn đường bị hỏng", "description": "Đèn đường đã không sáng trong nhiều ngày.",
        "category": "Chiếu sáng", "address": "Phố thử nghiệm",
    })
    assert result.status_code == 201
    assert result.json()["state"] == "submitted"
    assert [entry[1] for entry in calls] == ["/records", "/instances", "/records/record-1"]
    assert all(entry[3] == "tenant-1" for entry in calls)
