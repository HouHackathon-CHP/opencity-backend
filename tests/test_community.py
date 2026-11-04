# SPDX-License-Identifier: Apache-2.0
import os

os.environ["INTERNAL_GATEWAY_SECRET"] = "test-secret"

from fastapi.testclient import TestClient  # noqa: E402
from app.core import config  # noqa: E402
from app.main import app  # noqa: E402

client = TestClient(app)
BASE = {"X-Internal-Secret": "test-secret", "X-DXOS-User": "citizen",
        "X-DXOS-Tenant": "tenant-one", "X-DXOS-Roles": "citizen"}
OPERATOR = {**BASE, "X-DXOS-User": "community-staff", "X-DXOS-Roles": "community_groups_operator"}
BODY = {"title": "Nhóm khu dân cư số một", "description": "Nơi trao đổi các hoạt động trong khu dân cư số một.", "area": "Phường thử nghiệm"}


def test_group_membership_posts_and_tenant_isolation(monkeypatch, tmp_path):
    monkeypatch.setattr(config, "COMMUNITY_DB_PATH", str(tmp_path / "community.db"))
    assert client.get("/community/groups").status_code == 403
    assert client.post("/community/groups", headers=BASE, json=BODY).status_code == 403
    assert client.post("/community/groups", headers={**OPERATOR, "X-DXOS-Roles": "bulletins_operator"}, json=BODY).status_code == 403
    created = client.post("/community/groups", headers=OPERATOR, json=BODY)
    assert created.status_code == 201
    group_id = created.json()["id"]
    assert created.json()["member_count"] == 1
    assert client.get("/community/groups", headers=BASE).json()[0]["joined"] is False
    assert client.get(f"/community/groups/{group_id}/posts", headers=BASE).status_code == 403
    assert client.post(f"/community/groups/{group_id}/posts", headers=BASE, json={"body": "Xin chào"}).status_code == 403
    assert client.post(f"/community/groups/{group_id}/join", headers=BASE).json()["member_count"] == 2
    assert client.post(f"/community/groups/{group_id}/join", headers=BASE).json()["member_count"] == 2
    post = client.post(f"/community/groups/{group_id}/posts", headers=BASE, json={"body": "Xin chào nhóm"})
    assert post.status_code == 201 and post.json()["user_id"] == "citizen"
    assert len(client.get(f"/community/groups/{group_id}/posts", headers=BASE).json()) == 1
    other = {**BASE, "X-DXOS-Tenant": "tenant-two"}
    assert client.get("/community/groups", headers=other).json() == []
    assert client.post(f"/community/groups/{group_id}/join", headers=other).status_code == 404
    assert client.get(f"/community/groups/{group_id}/posts", headers=other).status_code == 404
    assert client.delete(f"/community/groups/{group_id}/join", headers=BASE).json()["member_count"] == 1
    assert client.get(f"/community/groups/{group_id}/posts", headers=BASE).status_code == 403
