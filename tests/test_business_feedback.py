# SPDX-License-Identifier: Apache-2.0
"""Business petition lifecycle, role separation and tenant isolation."""

import os

os.environ["INTERNAL_GATEWAY_SECRET"] = "test-secret"

from fastapi.testclient import TestClient  # noqa: E402
from app.core import config  # noqa: E402
from app.main import app  # noqa: E402


client = TestClient(app)
OWNER = {"X-Internal-Secret": "test-secret", "X-DXOS-User": "business-user-1",
         "X-DXOS-Tenant": "tenant-1", "X-DXOS-Roles": "citizen"}
OTHER = {**OWNER, "X-DXOS-User": "business-user-2"}
OTHER_TENANT = {**OWNER, "X-DXOS-Tenant": "tenant-2"}
OPERATOR = {**OWNER, "X-DXOS-User": "business-operator",
            "X-DXOS-Roles": "business_feedback_operator"}
OTHER_ROLE = {**OPERATOR, "X-DXOS-Roles": "administrative_feedback_operator"}
BODY = {
    "company_name": "Công ty Minh Châu", "tax_code": "0123456789",
    "representative": "Nguyễn Minh", "sector": "investment",
    "title": "Kiến nghị hỗ trợ thủ tục đầu tư",
    "description": "Doanh nghiệp cần được hướng dẫn cụ thể về các bước nộp hồ sơ đầu tư.",
    "requested_resolution": "Đề nghị cơ quan phụ trách công bố danh mục giấy tờ cần nộp.",
}


def test_business_petition_lifecycle_and_isolation(monkeypatch, tmp_path):
    monkeypatch.setattr(config, "BUSINESS_FEEDBACK_DB_PATH", str(tmp_path / "petitions.sqlite3"))
    assert client.get("/business-feedback").status_code == 403
    assert client.post("/business-feedback", headers=OWNER,
                       json={**BODY, "tax_code": "123"}).status_code == 422
    assert client.post("/business-feedback", headers=OWNER,
                       json={**BODY, "description": "   "}).status_code == 422

    created = client.post("/business-feedback", headers=OWNER, json=BODY)
    assert created.status_code == 201
    petition = created.json()
    petition_id = petition["id"]
    route = f"/business-feedback/{petition_id}"
    assert petition["status"] == "submitted"
    assert petition["tax_code"] == BODY["tax_code"]
    assert [item["id"] for item in client.get("/business-feedback", headers=OWNER).json()] == [petition_id]
    assert client.get("/business-feedback", headers=OTHER).json() == []
    assert client.get(route, headers=OTHER).status_code == 404
    assert client.get(route, headers=OTHER_TENANT).status_code == 404
    assert client.get(route, headers=OTHER_ROLE).status_code == 404
    assert client.get(route, headers=OPERATOR).status_code == 200
    assert client.get("/me/capabilities", headers=OPERATOR).json()["management"] == ["business_feedback"]
    assert client.post(route + "/review", headers=OWNER).status_code == 403
    assert client.post(route + "/review", headers=OTHER_ROLE).status_code == 403
    assert client.post(route + "/resolve", headers=OPERATOR,
                       json={"note": "Chúng tôi đã tiếp nhận kiến nghị."}).status_code == 409

    assert client.post(route + "/review", headers=OPERATOR).json()["status"] == "in_review"
    assert client.post(route + "/request-info", headers=OPERATOR,
                       json={"note": "   "}).status_code == 422
    assert client.post(route + "/request-info", headers=OPERATOR,
                       json={"note": "Vui lòng bổ sung mã hồ sơ đã nộp."}).json()["status"] == "needs_info"
    assert client.post(route + "/provide-info", headers=OTHER,
                       json={"note": "Mã hồ sơ là 12345."}).status_code == 404
    assert client.post(route + "/provide-info", headers=OWNER,
                       json={"note": "Mã hồ sơ đã nộp là ABC-12345."}).json()["status"] == "in_review"
    assert client.post(route + "/resolve", headers=OPERATOR,
                       json={"note": "Đơn vị đã gửi danh mục giấy tờ qua cổng thông tin."}).json()["status"] == "resolved"
    assert client.post(route + "/close", headers=OTHER).status_code == 404
    assert client.post(route + "/reopen", headers=OWNER,
                       json={"note": "Danh mục còn thiếu biểu mẫu số ba."}).json()["status"] == "in_review"
    assert client.post(route + "/resolve", headers=OPERATOR,
                       json={"note": "Đã bổ sung biểu mẫu số ba vào danh mục."}).json()["status"] == "resolved"
    closed = client.post(route + "/close", headers=OWNER)
    assert closed.status_code == 200 and closed.json()["status"] == "closed"
    assert client.post(route + "/reopen", headers=OWNER,
                       json={"note": "Xin xem xét thêm nội dung."}).status_code == 409
    assert [event["action"] for event in closed.json()["history"]] == [
        "submitted", "review", "request_info", "provide_info", "resolve", "reopen", "resolve", "close"]
