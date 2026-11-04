# SPDX-License-Identifier: Apache-2.0
import os

os.environ["INTERNAL_GATEWAY_SECRET"] = "test-secret"

from fastapi.testclient import TestClient  # noqa: E402
from app.core import config  # noqa: E402
from app.main import app  # noqa: E402

client = TestClient(app)
BASE = {"X-Internal-Secret": "test-secret", "X-DXOS-User": "citizen",
        "X-DXOS-Tenant": "tenant-one", "X-DXOS-Roles": "citizen"}
OPERATOR = {**BASE, "X-DXOS-User": "consultation-staff", "X-DXOS-Roles": "social_feedback_operator"}
BODY = {"title": "Góp ý kế hoạch chỉnh trang", "description": "Mời cư dân góp ý phương án chỉnh trang khu vực thử nghiệm.", "area": "Phường thử nghiệm"}


def test_consultation_permissions_lifecycle_and_scope(monkeypatch, tmp_path):
    monkeypatch.setattr(config, "SOCIAL_FEEDBACK_DB_PATH", str(tmp_path / "consultation.db"))
    assert client.get("/social-feedback/topics").status_code == 403
    assert client.post("/social-feedback/topics", headers=BASE, json=BODY).status_code == 403
    created = client.post("/social-feedback/topics", headers=OPERATOR, json=BODY)
    assert created.status_code == 201
    topic_id = created.json()["id"]
    assert created.json()["status"] == "open"
    assert client.get("/social-feedback/topics", headers=BASE).json()[0]["my_opinion"] is None
    assert client.get(f"/social-feedback/topics/{topic_id}/opinions", headers=BASE).status_code == 403
    opinion = client.put(f"/social-feedback/topics/{topic_id}/opinion", headers=BASE,
                         json={"body": "Tôi đồng ý bổ sung thêm cây xanh."})
    assert opinion.status_code == 200
    assert client.put(f"/social-feedback/topics/{topic_id}/opinion", headers=BASE,
                      json={"body": "Tôi đề nghị giữ lại nhiều cây xanh hơn."}).status_code == 200
    mine = client.get("/social-feedback/topics", headers=BASE).json()[0]
    assert mine["opinion_count"] == 1 and "giữ lại" in mine["my_opinion"]["body"]
    assert len(client.get(f"/social-feedback/topics/{topic_id}/opinions", headers=OPERATOR).json()) == 1
    other = {**BASE, "X-DXOS-Tenant": "tenant-two"}
    assert client.get("/social-feedback/topics", headers=other).json() == []
    assert client.put(f"/social-feedback/topics/{topic_id}/opinion", headers=other,
                      json={"body": "Ý kiến từ đơn vị khác."}).status_code == 404
    assert client.post(f"/social-feedback/topics/{topic_id}/close", headers=BASE).status_code == 403
    assert client.post(f"/social-feedback/topics/{topic_id}/close", headers=OPERATOR).json()["status"] == "closed"
    assert client.put(f"/social-feedback/topics/{topic_id}/opinion", headers=BASE,
                      json={"body": "Không thể sửa sau khi đóng."}).status_code == 409
