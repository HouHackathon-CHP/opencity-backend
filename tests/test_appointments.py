# SPDX-License-Identifier: Apache-2.0
"""Authorization, tenant isolation and capacity for appointment requests."""

import os
from datetime import datetime, timedelta, timezone

os.environ["INTERNAL_GATEWAY_SECRET"] = "test-secret"

from fastapi.testclient import TestClient  # noqa: E402
from app.main import app  # noqa: E402
from app.core import config  # noqa: E402


client = TestClient(app)
CITIZEN = {"X-Internal-Secret": "test-secret", "X-DXOS-User": "citizen-1", "X-DXOS-Tenant": "tenant-1", "X-DXOS-Roles": "citizen"}
OTHER = {**CITIZEN, "X-DXOS-User": "citizen-2"}
OUTSIDER = {**CITIZEN, "X-DXOS-Tenant": "tenant-2"}
OPERATOR = {**CITIZEN, "X-DXOS-User": "appointments-1", "X-DXOS-Roles": "appointments_operator"}


def test_appointment_module_enforces_roles_tenant_and_capacity(monkeypatch, tmp_path):
    monkeypatch.setattr(config, "APPOINTMENT_DB_PATH", str(tmp_path / "appointments.sqlite3"))
    start = datetime.now(timezone.utc) + timedelta(days=2)
    slot_body = {
        "starts_at": start.isoformat(), "ends_at": (start + timedelta(minutes=30)).isoformat(),
        "location": "Điểm tiếp dân thử nghiệm", "capacity": 1,
    }
    assert client.get("/appointments/slots").status_code == 403
    assert client.post("/appointments/slots", headers=CITIZEN, json=slot_body).status_code == 403
    invalid = {**slot_body, "starts_at": start.replace(tzinfo=None).isoformat()}
    assert client.post("/appointments/slots", headers=OPERATOR, json=invalid).status_code == 422
    created = client.post("/appointments/slots", headers=OPERATOR, json=slot_body)
    assert created.status_code == 201
    slot_id = created.json()["id"]
    assert created.json()["remaining_capacity"] == 1
    assert [slot["id"] for slot in client.get("/appointments/slots", headers=CITIZEN).json()] == [slot_id]
    assert client.get("/appointments/slots", headers=OUTSIDER).json() == []

    first = client.post("/appointments", headers=CITIZEN,
                        json={"slot_id": slot_id, "reason": "Trao đổi về hồ sơ của tôi"})
    assert first.status_code == 201 and first.json()["status"] == "pending"
    appointment_id = first.json()["id"]
    assert client.post("/appointments", headers=CITIZEN,
                       json={"slot_id": slot_id, "reason": "Một yêu cầu trùng thời gian"}).status_code == 409
    assert client.get("/appointments", headers=OUTSIDER).json() == []
    assert client.get("/appointments", headers=OTHER).json() == []
    assert client.post(f"/appointments/{appointment_id}/decision", headers=CITIZEN,
                       json={"decision": "confirmed"}).status_code == 403
    assert client.post(f"/appointments/{appointment_id}/decision", headers={**OPERATOR, "X-DXOS-Tenant": "tenant-2"},
                       json={"decision": "confirmed"}).status_code == 404
    assert client.post(f"/appointments/{appointment_id}/cancel", headers=OTHER).status_code == 404

    second = client.post("/appointments", headers=OTHER,
                         json={"slot_id": slot_id, "reason": "Trao đổi về thủ tục địa phương"})
    assert second.status_code == 201
    assert client.post(f"/appointments/{appointment_id}/decision", headers=OPERATOR,
                       json={"decision": "confirmed"}).status_code == 200
    assert client.get("/appointments/slots", headers=CITIZEN).json()[0]["remaining_capacity"] == 0
    assert client.post(f"/appointments/{second.json()['id']}/decision", headers=OPERATOR,
                       json={"decision": "confirmed"}).status_code == 409
    cancelled = client.post(f"/appointments/{appointment_id}/cancel", headers=CITIZEN)
    assert cancelled.status_code == 200 and cancelled.json()["status"] == "cancelled"
    assert client.post(f"/appointments/{second.json()['id']}/decision", headers=OPERATOR,
                       json={"decision": "confirmed"}).status_code == 200
    assert client.get("/appointments", headers=CITIZEN).json()[0]["status"] == "cancelled"
    assert len(client.get("/appointments", headers=OPERATOR).json()) == 2


def test_rejected_appointment_requires_reason_and_frees_active_request(monkeypatch, tmp_path):
    monkeypatch.setattr(config, "APPOINTMENT_DB_PATH", str(tmp_path / "appointments.sqlite3"))
    start = datetime.now(timezone.utc) + timedelta(days=1)
    slot = client.post("/appointments/slots", headers=OPERATOR, json={
        "starts_at": start.isoformat(), "ends_at": (start + timedelta(hours=1)).isoformat(),
        "location": "Điểm tiếp dân thử nghiệm", "capacity": 2,
    }).json()
    body = {"slot_id": slot["id"], "reason": "Xin trao đổi về thủ tục hành chính"}
    created = client.post("/appointments", headers=CITIZEN, json=body).json()
    decision_url = f"/appointments/{created['id']}/decision"
    assert client.post(decision_url, headers=OPERATOR,
                       json={"decision": "rejected", "note": ""}).status_code == 422
    rejected = client.post(decision_url, headers=OPERATOR,
                           json={"decision": "rejected", "note": "Cần thêm thông tin hồ sơ"})
    assert rejected.status_code == 200 and rejected.json()["status"] == "rejected"
    assert client.post(decision_url, headers=OPERATOR,
                       json={"decision": "confirmed"}).status_code == 409
    assert client.post("/appointments", headers=CITIZEN, json=body).status_code == 201
