# SPDX-License-Identifier: Apache-2.0
import os
from datetime import datetime, timedelta, timezone

os.environ["INTERNAL_GATEWAY_SECRET"] = "test-secret"

from fastapi.testclient import TestClient  # noqa: E402
from fastapi import HTTPException  # noqa: E402
from app import main  # noqa: E402


client = TestClient(main.app)
CITIZEN = {"X-Internal-Secret": "test-secret", "X-DXOS-User": "citizen-1", "X-DXOS-Tenant": "tenant-1", "X-DXOS-Roles": "citizen"}
REPORTS_OPERATOR = {**CITIZEN, "X-DXOS-User": "reports-1", "X-DXOS-Roles": "reports_operator",
                    "X-DXOS-Unit": "infrastructure"}
ENVIRONMENT_OPERATOR = {**REPORTS_OPERATOR, "X-DXOS-User": "reports-2", "X-DXOS-Unit": "environment"}
DISPATCHER = {**CITIZEN, "X-DXOS-User": "dispatcher-1", "X-DXOS-Roles": "reports_dispatcher"}
BULLETINS_OPERATOR = {**CITIZEN, "X-DXOS-User": "bulletins-1", "X-DXOS-Roles": "bulletins_operator"}
SURVEYS_OPERATOR = {**CITIZEN, "X-DXOS-User": "surveys-1", "X-DXOS-Roles": "surveys_operator"}
LEGACY_OPERATOR = {**CITIZEN, "X-DXOS-User": "legacy-1", "X-DXOS-Roles": "operator"}
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
    created = client.post("/bulletins", headers=BULLETINS_OPERATOR, json=body)
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
    created = client.post("/surveys", headers=SURVEYS_OPERATOR, json=body)
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
    closed = client.post(f"/surveys/{survey_id}/close", headers=SURVEYS_OPERATOR)
    assert closed.status_code == 200
    assert closed.json()["status"] == "closed"
    assert client.post(f"/surveys/{survey_id}/answers", headers=SURVEYS_OPERATOR,
                       json={"option_id": first_option}).status_code == 409


def test_survey_rejects_duplicate_or_blank_options(monkeypatch, tmp_path):
    monkeypatch.setattr(main, "SURVEY_DB_PATH", str(tmp_path / "surveys.sqlite3"))
    base = {"title": "Khảo sát thử nghiệm", "description": "Nội dung chỉ phục vụ kiểm thử chức năng khảo sát."}
    for options in (["Một", "một"], ["Một", "  "]):
        response = client.post("/surveys", headers=SURVEYS_OPERATOR, json={**base, "options": options})
        assert response.status_code == 422


def test_citizen_cannot_transition_a_report():
    assert client.post("/reports/report-1/actions/triage", headers=CITIZEN).status_code == 403


def test_feature_roles_are_isolated():
    expected = {
        "reports": ["reports"], "bulletins": ["bulletins"], "surveys": ["surveys"],
    }
    for feature, headers in (("reports", REPORTS_OPERATOR), ("bulletins", BULLETINS_OPERATOR),
                             ("surveys", SURVEYS_OPERATOR)):
        assert client.get("/me/capabilities", headers=headers).json() == {
            "management": expected[feature],
            "report_unit": "infrastructure" if feature == "reports" else None,
            "report_dispatcher": False,
        }
    assert client.get("/me/capabilities", headers=DISPATCHER).json() == {
        "management": ["reports"], "report_unit": None, "report_dispatcher": True}
    assert client.get("/me/capabilities", headers=LEGACY_OPERATOR).json() == {
        "management": [], "report_unit": None, "report_dispatcher": False}
    assert client.get("/me/capabilities", headers={**CITIZEN, "X-DXOS-Roles": "admin"}).json() == {
        "management": ["reports", "bulletins", "surveys"], "report_unit": None,
        "report_dispatcher": True}
    assert client.get("/me/capabilities", headers={**REPORTS_OPERATOR, "X-DXOS-Unit": ""}).json() == {
        "management": [], "report_unit": None, "report_dispatcher": False}
    assert client.post("/reports/report-1/actions/triage", headers=BULLETINS_OPERATOR).status_code == 403
    assert client.post("/reports/report-1/actions/triage", headers=LEGACY_OPERATOR).status_code == 403
    bulletin = {"category": "news", "title": "Thông báo mẫu", "summary": "Thông báo kiểm thử quyền.",
                "body": "Nội dung kiểm thử phân quyền giữa các nghiệp vụ OpenCity."}
    survey = {"title": "Khảo sát mẫu", "description": "Nội dung kiểm thử phân quyền khảo sát.",
              "options": ["Đồng ý", "Không đồng ý"]}
    assert client.post("/bulletins", headers=REPORTS_OPERATOR, json=bulletin).status_code == 403
    assert client.post("/surveys", headers=BULLETINS_OPERATOR, json=survey).status_code == 403
    assert client.post("/bulletins", headers=SURVEYS_OPERATOR, json=bulletin).status_code == 403
    assert "operator" not in main.core_headers(main.caller(**{
        "x_internal_secret": "test-secret", "x_dxos_user": "legacy-1",
        "x_dxos_tenant": "tenant-1", "x_dxos_roles": "operator", "x_dxos_unit": None,
    }))["X-DXOS-Roles"]
    assert "operator" in main.core_headers(main.caller(**{
        "x_internal_secret": "test-secret", "x_dxos_user": "reports-1",
        "x_dxos_tenant": "tenant-1", "x_dxos_roles": "reports_operator",
        "x_dxos_unit": "infrastructure",
    }))["X-DXOS-Roles"]


def test_report_unit_scopes_lists_details_and_actions(monkeypatch, tmp_path):
    monkeypatch.setattr(main, "REPORT_DB_PATH", str(tmp_path / "routing.sqlite3"))
    records = [
        {"id": "infrastructure-case", "kind": "field-report", "payload": {"category": "Chiếu sáng"},
         "created_by": "citizen-1", "created_at": "2026-10-23T00:00:00Z", "updated_at": "2026-10-23T00:00:00Z"},
        {"id": "environment-case", "kind": "field-report", "payload": {"category": "Môi trường"},
         "created_by": "citizen-2", "created_at": "2026-10-23T00:00:00Z", "updated_at": "2026-10-23T00:00:00Z"},
    ]

    async def fake_core(base, path, identity, method="GET", **kwargs):
        if path == "/records":
            return records
        if path == "/instances":
            return []
        if path.startswith("/records/"):
            return next(item for item in records if item["id"] == path.rsplit("/", 1)[-1])
        raise AssertionError(f"Unexpected core call: {path}")

    monkeypatch.setattr(main, "core_json", fake_core)
    with main.report_db() as connection:
        connection.executemany("""
            INSERT INTO report_assignments
              (report_id, tenant, unit_id, due_at, assigned_at, assigned_by)
            VALUES (?, 'tenant-1', ?, '2026-11-01T00:00:00Z', '2026-10-23T00:00:00Z', 'dispatcher-1')
        """, [("infrastructure-case", "infrastructure"), ("environment-case", "environment")])
    assert [item["id"] for item in client.get("/reports", headers=REPORTS_OPERATOR).json()] == ["infrastructure-case"]
    assert [item["id"] for item in client.get("/reports", headers=ENVIRONMENT_OPERATOR).json()] == ["environment-case"]
    assert [item["id"] for item in client.get("/reports", headers=CITIZEN).json()] == ["infrastructure-case"]
    assert client.get("/reports/environment-case", headers=REPORTS_OPERATOR).status_code == 404
    assert client.post("/reports/environment-case/actions/triage", headers=REPORTS_OPERATOR).status_code == 404
    assert client.post("/reports/environment-case/retry-workflow", headers=REPORTS_OPERATOR).status_code == 404
    assert client.get("/reports/environment-case/attachments/photo-1", headers=REPORTS_OPERATOR).status_code == 404
    assert client.get("/reports/infrastructure-case", headers=REPORTS_OPERATOR).json()["unit_id"] == "infrastructure"


def test_dispatch_accept_transfer_and_resolve(monkeypatch, tmp_path):
    monkeypatch.setattr(main, "REPORT_DB_PATH", str(tmp_path / "routing.sqlite3"))
    record = {"id": "report-1", "kind": "field-report", "payload": {"category": "Chiếu sáng"},
              "created_by": "citizen-1", "created_at": "2026-10-23T00:00:00Z",
              "updated_at": "2026-10-23T00:00:00Z"}
    state = {"value": "submitted"}

    def instance():
        return {"id": "workflow-1", "definition_key": "report-handling",
                "reference_id": "report-1", "state": state["value"], "history": []}

    async def fake_core(base, path, identity, method="GET", **kwargs):
        if identity.tenant != "tenant-1":
            raise HTTPException(status_code=404, detail="Not found")
        if path == "/records":
            return [record]
        if path == "/records/report-1":
            return record
        if path == "/instances":
            return [instance()]
        if path == "/instances/workflow-1":
            return instance()
        if path.startswith("/instances/workflow-1/actions/"):
            action = path.rsplit("/", 1)[-1]
            assert (state["value"], action) in {
                ("submitted", "triage"), ("triaged", "assign"), ("assigned", "resolve")}
            state["value"] = {"triage": "triaged", "assign": "assigned", "resolve": "resolved"}[action]
            return instance()
        raise AssertionError(f"Unexpected core call: {path}")

    monkeypatch.setattr(main, "core_json", fake_core)
    route = "/reports/report-1"
    due_at = (datetime.now(timezone.utc) + timedelta(days=2)).isoformat()
    dispatch = {"unit_id": "environment", "due_at": due_at, "note": "Chuyển đơn vị môi trường kiểm tra"}
    assert client.get("/reports", headers=REPORTS_OPERATOR).json() == []
    assert len(client.get("/reports", headers=DISPATCHER).json()) == 1
    assert client.post(f"{route}/dispatch", headers=REPORTS_OPERATOR, json=dispatch).status_code == 403
    assert client.post(f"{route}/dispatch", headers=CITIZEN, json=dispatch).status_code == 403
    assigned = client.post(f"{route}/dispatch", headers=DISPATCHER, json=dispatch)
    assert assigned.status_code == 200
    assert assigned.json()["state"] == "assigned"
    assert assigned.json()["assigned_unit"] == "environment"
    env_notifications = client.get("/notifications", headers=ENVIRONMENT_OPERATOR).json()
    assert any(item["kind"] == "assigned" for item in env_notifications)
    assert client.get("/notifications", headers=REPORTS_OPERATOR).json() == []
    citizen_notifications = client.get("/notifications", headers=CITIZEN).json()
    assert citizen_notifications[0]["kind"] == "assigned" and citizen_notifications[0]["read_at"] is None
    notification_id = citizen_notifications[0]["id"]
    assert client.post(f"/notifications/{notification_id}/read", headers=OUTSIDER).status_code == 404
    assert client.post(f"/notifications/{notification_id}/read", headers=CITIZEN).status_code == 200
    assert client.get("/notifications", headers=CITIZEN).json()[0]["read_at"]
    assert client.get(route, headers=REPORTS_OPERATOR).status_code == 404
    assert client.get(route, headers=ENVIRONMENT_OPERATOR).status_code == 200
    assert client.post(f"{route}/actions/resolve", headers=ENVIRONMENT_OPERATOR).status_code == 409
    assert client.post(f"{route}/progress", headers=ENVIRONMENT_OPERATOR,
                       json={"note": "Đang kiểm tra hiện trường"}).status_code == 409
    accepted = client.post(f"{route}/accept", headers=ENVIRONMENT_OPERATOR)
    assert accepted.status_code == 200 and accepted.json()["accepted_at"]
    progress = client.post(f"{route}/progress", headers=ENVIRONMENT_OPERATOR,
                           json={"note": "Đã kiểm tra hiện trường, cần đội chiếu sáng"})
    assert progress.status_code == 200 and progress.json()["history"][-1]["action"] == "progress"
    transfer = {"unit_id": "infrastructure", "reason": "Cần đội chiếu sáng xử lý"}
    assert client.post(f"{route}/transfer-request", headers=REPORTS_OPERATOR, json=transfer).status_code == 404
    requested = client.post(f"{route}/transfer-request", headers=ENVIRONMENT_OPERATOR, json=transfer)
    assert requested.status_code == 200 and requested.json()["pending_unit"] == "infrastructure"
    assert client.post(f"{route}/actions/resolve", headers=ENVIRONMENT_OPERATOR).status_code == 409
    rejected = client.post(f"{route}/transfer-request/reject", headers=DISPATCHER,
                           json={"note": "Tiếp tục kiểm tra tại đơn vị hiện tại"})
    assert rejected.status_code == 200 and rejected.json()["pending_unit"] is None
    assert client.post(f"{route}/transfer-request", headers=ENVIRONMENT_OPERATOR, json=transfer).status_code == 200
    reassigned = client.post(f"{route}/dispatch", headers=DISPATCHER,
                             json={**dispatch, "unit_id": "infrastructure", "note": "Duyệt chuyển đơn vị"})
    assert reassigned.status_code == 200 and reassigned.json()["assigned_unit"] == "infrastructure"
    assert client.get(route, headers=ENVIRONMENT_OPERATOR).status_code == 404
    assert client.get("/notifications", headers=ENVIRONMENT_OPERATOR).json() == []
    assert any(item["kind"] == "reassigned" for item in client.get("/notifications", headers=REPORTS_OPERATOR).json())
    assert client.post(f"{route}/accept", headers=REPORTS_OPERATOR).status_code == 200
    resolved = client.post(f"{route}/actions/resolve", headers=REPORTS_OPERATOR)
    assert resolved.status_code == 200 and resolved.json()["state"] == "resolved"
    actions = {event["action"] for event in client.get(route, headers=CITIZEN).json()["history"]}
    assert {"assigned", "accepted", "progress", "transfer_requested", "transfer_rejected", "reassigned", "resolved"} <= actions
    assert client.get(route, headers=OUTSIDER).status_code == 404


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


def test_create_report_uses_data_and_workflow(monkeypatch, tmp_path):
    monkeypatch.setattr(main, "REPORT_DB_PATH", str(tmp_path / "routing.sqlite3"))
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
    assert client.get("/notifications", headers=DISPATCHER).json()[0]["kind"] == "new_report"
    assert [entry[1] for entry in calls] == ["/records", "/instances", "/records/record-1"]
    assert all(entry[3] == "tenant-1" for entry in calls)


def test_deadline_reminders_are_scoped_and_idempotent(monkeypatch, tmp_path):
    monkeypatch.setattr(main, "REPORT_DB_PATH", str(tmp_path / "routing.sqlite3"))
    due = (datetime.now(timezone.utc) + timedelta(hours=12)).isoformat()
    with main.report_db() as connection:
        connection.execute("""
            INSERT INTO report_assignments
              (report_id, tenant, unit_id, due_at, assigned_at, assigned_by)
            VALUES ('reminder-case', 'tenant-1', 'environment', ?, '2026-10-30T00:00:00+00:00', 'dispatcher-1')
        """, (due,))
    first = client.get("/notifications", headers=ENVIRONMENT_OPERATOR).json()
    second = client.get("/notifications", headers=ENVIRONMENT_OPERATOR).json()
    assert len(first) == len(second) == 1 and first[0]["kind"] == "due_soon"
    assert client.get("/notifications", headers=REPORTS_OPERATOR).json() == []
    assert client.get("/notifications", headers=OUTSIDER).json() == []
    assert len(client.get("/notifications", headers=DISPATCHER).json()) == 1
    with main.report_db() as connection:
        connection.execute("UPDATE report_assignments SET due_at = ? WHERE report_id = 'reminder-case'",
                           ((datetime.now(timezone.utc) - timedelta(hours=1)).isoformat(),))
    overdue = client.get("/notifications", headers=ENVIRONMENT_OPERATOR).json()
    assert [item["kind"] for item in overdue] == ["overdue", "due_soon"]
