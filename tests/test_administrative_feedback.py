# SPDX-License-Identifier: Apache-2.0
"""Procedure feedback: owner isolation, dedicated role and state transitions."""

import os

os.environ["INTERNAL_GATEWAY_SECRET"] = "test-secret"

from fastapi.testclient import TestClient  # noqa: E402
from app.core import config  # noqa: E402
from app.main import app  # noqa: E402


client = TestClient(app)
CITIZEN = {"X-Internal-Secret": "test-secret", "X-DXOS-User": "citizen-1",
           "X-DXOS-Tenant": "tenant-1", "X-DXOS-Roles": "citizen"}
OTHER = {**CITIZEN, "X-DXOS-User": "citizen-2"}
OUTSIDER = {**CITIZEN, "X-DXOS-Tenant": "tenant-2"}
OPERATOR = {**CITIZEN, "X-DXOS-User": "procedure-1",
            "X-DXOS-Roles": "administrative_feedback_operator"}
UNRELATED_OPERATOR = {**OPERATOR, "X-DXOS-Roles": "appointments_operator"}
BODY = {"title": "Hồ sơ bị chậm xử lý", "procedure": "Đăng ký kinh doanh",
        "agency": "Bộ phận một cửa", "issue_type": "delay",
        "description": "Tôi đã nộp hồ sơ đúng hạn nhưng chưa nhận được kết quả xử lý."}


def test_feedback_lifecycle_and_isolation(monkeypatch, tmp_path):
    monkeypatch.setattr(config, "ADMIN_FEEDBACK_DB_PATH", str(tmp_path / "feedback.sqlite3"))
    assert client.get("/administrative-feedback").status_code == 403
    assert client.post("/administrative-feedback", headers=CITIZEN,
                       json={**BODY, "description": " " * 20}).status_code == 422
    created = client.post("/administrative-feedback", headers=CITIZEN, json=BODY)
    assert created.status_code == 201
    case = created.json()
    feedback_id = case["id"]
    route = f"/administrative-feedback/{feedback_id}"
    assert case["status"] == "submitted"
    assert case["history"][0]["action"] == "submitted"
    assert [item["id"] for item in client.get("/administrative-feedback", headers=CITIZEN).json()] == [feedback_id]
    assert client.get("/administrative-feedback", headers=OTHER).json() == []
    assert client.get(route, headers=OTHER).status_code == 404
    assert client.get(route, headers=OUTSIDER).status_code == 404
    assert client.get(route, headers=UNRELATED_OPERATOR).status_code == 404
    assert client.get(route, headers=OPERATOR).status_code == 200
    assert client.get("/me/capabilities", headers=OPERATOR).json()["management"] == ["administrative_feedback"]
    assert client.post(route + "/review", headers=CITIZEN).status_code == 403
    assert client.post(route + "/review", headers=UNRELATED_OPERATOR).status_code == 403
    assert client.post(route + "/answer", headers=OPERATOR,
                       json={"note": "Đã tiếp nhận và kiểm tra hồ sơ."}).status_code == 409
    assert client.post(route + "/review", headers=OPERATOR).json()["status"] == "in_review"
    assert client.post(route + "/review", headers=OPERATOR).status_code == 409
    assert client.post(route + "/answer", headers=OPERATOR,
                       json={"note": "   " * 10}).status_code == 422
    answered = client.post(route + "/answer", headers=OPERATOR,
                           json={"note": "Hồ sơ đã được kiểm tra, kết quả sẽ trả vào thứ Sáu."})
    assert answered.status_code == 200 and answered.json()["status"] == "answered"
    assert client.post(route + "/close", headers=OTHER).status_code == 404
    assert client.post(route + "/clarification", headers=CITIZEN,
                       json={"note": "Xin giải thích thêm về ngày trả kết quả."}).json()["status"] == "in_review"
    assert client.post(route + "/answer", headers=OPERATOR,
                       json={"note": "Kết quả đã sẵn sàng tại bộ phận một cửa."}).status_code == 200
    closed = client.post(route + "/close", headers=CITIZEN)
    assert closed.status_code == 200 and closed.json()["status"] == "closed"
    assert client.post(route + "/clarification", headers=CITIZEN,
                       json={"note": "Xin phản hồi lại thông tin."}).status_code == 409
    assert [event["action"] for event in closed.json()["history"]] == [
        "submitted", "start_review", "answer", "clarification", "answer", "close"]
