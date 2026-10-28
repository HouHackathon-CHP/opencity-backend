# SPDX-License-Identifier: Apache-2.0
import os

os.environ["INTERNAL_GATEWAY_SECRET"] = "test-secret"

from fastapi.testclient import TestClient  # noqa: E402
from app import main  # noqa: E402


client = TestClient(main.app)
CITIZEN = {"X-Internal-Secret": "test-secret", "X-DXOS-User": "citizen-1", "X-DXOS-Tenant": "tenant-1", "X-DXOS-Roles": "citizen"}
OPERATOR = {**CITIZEN, "X-DXOS-User": "operator-1", "X-DXOS-Roles": "operator"}
OUTSIDER = {**CITIZEN, "X-DXOS-Tenant": "tenant-2"}


def test_direct_request_is_rejected():
    assert client.get("/reports").status_code == 403
    assert client.get("/bulletins").status_code == 403
    assert client.get("/surveys").status_code == 403


def test_bulletins_are_operator_published_and_tenant_scoped(monkeypatch, tmp_path):
    monkeypatch.setattr(main, "NEWS_DB_PATH", str(tmp_path / "bulletins.sqlite3"))
    body = {
        "category": "alert", "title": "Diễn tập cảnh báo",
        "summary": "Thông báo chỉ dùng để kiểm thử ứng dụng.",
        "body": "Đây là nội dung diễn tập trong môi trường thử nghiệm, không phải cảnh báo chính thức.",
        "area": "Khu vực thử nghiệm", "latitude": 21.03, "longitude": 105.85,
    }
    assert client.post("/bulletins", headers=CITIZEN, json=body).status_code == 403
    created = client.post("/bulletins", headers=OPERATOR, json=body)
    assert created.status_code == 201
    bulletin_id = created.json()["id"]
    assert created.json()["tenant"] == "tenant-1"
    assert [item["id"] for item in client.get("/bulletins", headers=CITIZEN).json()] == [bulletin_id]
    assert client.get("/bulletins", headers=OUTSIDER).json() == []
    assert client.get(f"/bulletins/{bulletin_id}", headers=OUTSIDER).status_code == 404


def test_survey_lifecycle_is_tenant_scoped_and_one_answer_per_user(monkeypatch, tmp_path):
    monkeypatch.setattr(main, "SURVEY_DB_PATH", str(tmp_path / "surveys.sqlite3"))
    body = {"title": "Khảo sát tuyến phố", "description": "Chọn ưu tiên cải thiện tuyến phố trong tháng tới.",
            "options": ["Thêm cây xanh", "Cải thiện chiếu sáng"]}
    assert client.post("/surveys", headers=CITIZEN, json=body).status_code == 403
    created = client.post("/surveys", headers=OPERATOR, json=body)
    assert created.status_code == 201
    survey = created.json()
    survey_id = survey["id"]
    first_option = survey["options"][0]["id"]
    assert survey["status"] == "open"
    assert survey["total_responses"] == 0
    listing = client.get("/surveys", headers=CITIZEN).json()
    assert listing[0]["id"] == survey_id
    assert listing[0]["my_option_id"] is None
    detail = client.get(f"/surveys/{survey_id}", headers=CITIZEN).json()
    assert detail["total_responses"] is None
    assert all(option["votes"] is None for option in detail["options"])
    assert client.get("/surveys", headers=OUTSIDER).json() == []
    assert client.get(f"/surveys/{survey_id}", headers=OUTSIDER).status_code == 404
    assert client.post(f"/surveys/{survey_id}/answers", headers=OUTSIDER,
                       json={"option_id": first_option}).status_code == 404
    assert client.post(f"/surveys/{survey_id}/answers", headers=CITIZEN,
                       json={"option_id": "unknown"}).status_code == 422
    answered = client.post(f"/surveys/{survey_id}/answers", headers=CITIZEN,
                           json={"option_id": first_option})
    assert answered.status_code == 200
    assert answered.json()["my_option_id"] == first_option
    assert answered.json()["total_responses"] == 1
    assert answered.json()["options"][0]["votes"] == 1
    assert client.post(f"/surveys/{survey_id}/answers", headers=CITIZEN,
                       json={"option_id": first_option}).status_code == 409
    assert client.post(f"/surveys/{survey_id}/close", headers=CITIZEN).status_code == 403
    assert client.post(f"/surveys/{survey_id}/close", headers=OUTSIDER).status_code == 403
    closed = client.post(f"/surveys/{survey_id}/close", headers=OPERATOR)
    assert closed.status_code == 200
    assert closed.json()["status"] == "closed"
    assert client.post(f"/surveys/{survey_id}/answers", headers=OPERATOR,
                       json={"option_id": first_option}).status_code == 409


def test_survey_rejects_duplicate_or_blank_options(monkeypatch, tmp_path):
    monkeypatch.setattr(main, "SURVEY_DB_PATH", str(tmp_path / "surveys.sqlite3"))
    base = {"title": "Khảo sát thử nghiệm", "description": "Nội dung chỉ phục vụ kiểm thử chức năng khảo sát."}
    for options in (["Một", "một"], ["Một", "  "]):
        response = client.post("/surveys", headers=OPERATOR, json={**base, "options": options})
        assert response.status_code == 422


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
