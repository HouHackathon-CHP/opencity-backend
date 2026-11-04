# SPDX-License-Identifier: Apache-2.0
"""Communications are separated from news and scoped to a tenant and role."""

import os

os.environ["INTERNAL_GATEWAY_SECRET"] = "test-secret"

from fastapi.testclient import TestClient  # noqa: E402
from app.core import config  # noqa: E402
from app.main import app  # noqa: E402


client = TestClient(app)
BASE = {"X-Internal-Secret": "test-secret", "X-DXOS-User": "citizen",
        "X-DXOS-Tenant": "tenant-one", "X-DXOS-Roles": "citizen"}
OPERATOR = {**BASE, "X-DXOS-User": "publisher", "X-DXOS-Roles": "communications_operator"}
BODY = {"title": "Chiến dịch giữ gìn môi trường", "summary": "Cùng giữ sạch khu dân cư mỗi ngày",
        "body": "Đề nghị cư dân cùng tham gia phân loại rác và giữ sạch nơi công cộng.", "area": "Phường thử nghiệm"}


def test_communication_scope_and_news_separation(monkeypatch, tmp_path):
    monkeypatch.setattr(config, "NEWS_DB_PATH", str(tmp_path / "news.db"))
    assert client.get("/communications").status_code == 403
    assert client.post("/communications", headers=BASE, json=BODY).status_code == 403
    assert client.post("/communications", headers={**OPERATOR, "X-DXOS-Roles": "bulletins_operator"}, json=BODY).status_code == 403
    assert client.post("/communications", headers=OPERATOR, json={**BODY, "title": "     "}).status_code == 422
    created = client.post("/communications", headers=OPERATOR, json=BODY)
    assert created.status_code == 201
    item = created.json()
    assert item["category"] == "campaign"
    assert item["created_by"] == "publisher"
    assert [row["id"] for row in client.get("/communications", headers=BASE).json()] == [item["id"]]
    assert client.get(f"/communications/{item['id']}", headers=BASE).status_code == 200
    assert client.get(f"/bulletins/{item['id']}", headers=BASE).status_code == 404
    assert client.get("/bulletins", headers=BASE).json() == []
    other = {**BASE, "X-DXOS-Tenant": "tenant-two"}
    assert client.get("/communications", headers=other).json() == []
    assert client.get(f"/communications/{item['id']}", headers=other).status_code == 404
