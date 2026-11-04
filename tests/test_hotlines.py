# SPDX-License-Identifier: Apache-2.0
"""Hotline publication, visibility and tenant isolation."""

import os

os.environ["INTERNAL_GATEWAY_SECRET"] = "test-secret"

from fastapi.testclient import TestClient  # noqa: E402
from app.core import config  # noqa: E402
from app.main import app  # noqa: E402


client = TestClient(app)
BASE = {"X-Internal-Secret": "test-secret", "X-DXOS-User": "citizen-1",
        "X-DXOS-Tenant": "tenant-one", "X-DXOS-Roles": "citizen"}
OPERATOR = {**BASE, "X-DXOS-User": "hotline-staff", "X-DXOS-Roles": "hotlines_operator"}
OTHER_ROLE = {**OPERATOR, "X-DXOS-Roles": "bulletins_operator"}
BODY = {"name": "Đường dây hỗ trợ đô thị", "unit": "Trung tâm tiếp nhận",
        "phone": "024 1234 5678", "area": "Khu vực trung tâm",
        "hours": "24/7", "description": "Tiếp nhận câu hỏi của người dân", "active": True}


def test_hotline_directory_permissions_and_scope(monkeypatch, tmp_path):
    monkeypatch.setattr(config, "HOTLINES_DB_PATH", str(tmp_path / "hotlines.db"))
    assert client.get("/hotlines").status_code == 403
    assert client.post("/hotlines", headers=BASE, json=BODY).status_code == 403
    assert client.post("/hotlines", headers=OTHER_ROLE, json=BODY).status_code == 403
    assert client.post("/hotlines", headers=OPERATOR,
                       json={**BODY, "phone": "javascript:alert(1)"}).status_code == 422

    created = client.post("/hotlines", headers=OPERATOR, json=BODY)
    assert created.status_code == 201
    hotline_id = created.json()["id"]
    assert created.json()["active"] is True
    assert "created_by" not in created.json()
    assert [item["id"] for item in client.get("/hotlines", headers=BASE).json()] == [hotline_id]
    assert client.get("/hotlines", headers={**BASE, "X-DXOS-Tenant": "tenant-two"}).json() == []

    updated = client.put(f"/hotlines/{hotline_id}", headers=OPERATOR,
                         json={**BODY, "active": False})
    assert updated.status_code == 200 and updated.json()["active"] is False
    assert client.get("/hotlines", headers=BASE).json() == []
    assert len(client.get("/hotlines", headers=OPERATOR).json()) == 1
    assert client.put(f"/hotlines/{hotline_id}",
                      headers={**OPERATOR, "X-DXOS-Tenant": "tenant-two"},
                      json=BODY).status_code == 404
