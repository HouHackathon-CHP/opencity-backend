# SPDX-License-Identifier: Apache-2.0
import os

os.environ["INTERNAL_GATEWAY_SECRET"] = "test-secret"

from fastapi.testclient import TestClient  # noqa: E402
from app.core import config  # noqa: E402
from app.main import app  # noqa: E402

client = TestClient(app)
BASE = {"X-Internal-Secret": "test-secret", "X-DXOS-User": "citizen",
        "X-DXOS-Tenant": "tenant-one", "X-DXOS-Roles": "citizen"}
OPERATOR = {**BASE, "X-DXOS-User": "ward-staff", "X-DXOS-Roles": "digital_ward_operator"}
BODY = {"code": "WARD-01", "name": "Phường Thử Nghiệm", "address": "Số 1 đường Thử Nghiệm",
        "phone": "0000000000", "office_hours": "Thứ 2 đến thứ 6",
        "description": "Thông tin minh họa về điểm phục vụ cấp cơ sở.",
        "latitude": 21.0285, "longitude": 105.8542, "active": True}


def test_ward_directory_permissions_and_visibility(monkeypatch, tmp_path):
    monkeypatch.setattr(config, "DIGITAL_WARD_DB_PATH", str(tmp_path / "ward.db"))
    assert client.get("/digital-wards").status_code == 403
    assert client.post("/digital-wards", headers=BASE, json=BODY).status_code == 403
    assert client.post("/digital-wards", headers={**OPERATOR, "X-DXOS-Roles": "hotlines_operator"}, json=BODY).status_code == 403
    assert client.post("/digital-wards", headers=OPERATOR,
                       json={**BODY, "longitude": None}).status_code == 422
    created = client.post("/digital-wards", headers=OPERATOR, json=BODY)
    assert created.status_code == 201
    ward_id = created.json()["id"]
    assert "updated_by" not in created.json()
    assert client.post("/digital-wards", headers=OPERATOR, json=BODY).status_code == 409
    assert [ward["id"] for ward in client.get("/digital-wards", headers=BASE).json()] == [ward_id]
    assert client.get(f"/digital-wards/{ward_id}", headers=BASE).status_code == 200
    other = {**BASE, "X-DXOS-Tenant": "tenant-two"}
    assert client.get("/digital-wards", headers=other).json() == []
    assert client.get(f"/digital-wards/{ward_id}", headers=other).status_code == 404
    hidden = client.put(f"/digital-wards/{ward_id}", headers=OPERATOR,
                        json={**BODY, "active": False})
    assert hidden.status_code == 200 and hidden.json()["active"] is False
    assert client.get("/digital-wards", headers=BASE).json() == []
    assert client.get(f"/digital-wards/{ward_id}", headers=BASE).status_code == 404
    assert len(client.get("/digital-wards", headers=OPERATOR).json()) == 1
    assert client.put(f"/digital-wards/{ward_id}", headers={**OPERATOR, "X-DXOS-Tenant": "tenant-two"},
                      json=BODY).status_code == 404
