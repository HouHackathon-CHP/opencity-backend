# SPDX-License-Identifier: Apache-2.0
"""Dispatcher-only insight and human review audit."""

import os
from datetime import datetime, timedelta, timezone

os.environ["INTERNAL_GATEWAY_SECRET"] = "test-secret"

from fastapi import HTTPException  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402
from app.core import config, core_client  # noqa: E402
from app.main import app  # noqa: E402


client = TestClient(app)
DISPATCHER = {"X-Internal-Secret": "test-secret", "X-DXOS-User": "dispatcher-1",
              "X-DXOS-Tenant": "tenant-1", "X-DXOS-Roles": "reports_dispatcher"}
CITIZEN = {**DISPATCHER, "X-DXOS-User": "citizen-1", "X-DXOS-Roles": "citizen"}
OUTSIDER = {**DISPATCHER, "X-DXOS-Tenant": "tenant-2"}


def test_suggestion_is_scoped_and_dispatch_review_is_audited(monkeypatch, tmp_path):
    monkeypatch.setattr(config, "REPORT_DB_PATH", str(tmp_path / "routing.sqlite3"))
    record = {
        "id": "report-1", "kind": "field-report", "created_by": "citizen-1",
        "created_at": "2026-11-01T00:00:00+00:00", "updated_at": "2026-11-01T00:00:00+00:00",
        "payload": {"title": "Đèn đường hỏng", "description": "Đèn đường đã tắt nhiều ngày",
                    "category": "Chiếu sáng", "address": "Phố thử nghiệm"},
    }
    other = {**record, "id": "report-2", "payload": {**record["payload"], "title": "Đèn đường không sáng"}}
    instance = {"id": "workflow-1", "definition_key": "report-handling",
                "reference_id": "report-1", "state": "submitted", "history": []}
    calls = []

    async def fake_core(base, path, identity, method="GET", **kwargs):
        calls.append((base, path, identity.tenant))
        if identity.tenant != "tenant-1":
            raise HTTPException(status_code=404, detail="Report not found")
        if base == config.DATA_URL and path == "/records/report-1":
            return record
        if base == config.DATA_URL and path == "/records":
            return [record, other]
        if base == config.WORKFLOW_URL and path == "/instances":
            return [instance]
        if base == config.WORKFLOW_URL and path.endswith("/actions/triage"):
            return {**instance, "state": "triaged"}
        if base == config.WORKFLOW_URL and path.endswith("/actions/assign"):
            return {**instance, "state": "assigned"}
        if base == config.INSIGHT_URL and path == "/analyze":
            payload = kwargs["json_body"]
            if payload["labels"] == ["high", "normal", "low"]:
                return {"ranked_labels": [{"label": "high", "score": 0.61},
                                          {"label": "normal", "score": 0.3},
                                          {"label": "low", "score": 0.09}]}
            assert payload["labels"] == sorted(config.VALID_UNITS)
            assert any(item["id"] == "report-2" for item in payload["candidates"])
            return {
                "model_version": "multinomial-nb-bow-v1",
                "ranked_labels": [{"label": "infrastructure", "score": 0.78},
                                  {"label": "environment", "score": 0.1}],
                "signals": ["đèn", "đường"],
                "similar": [{"id": "report-2", "similarity": 0.8}],
            }
        raise AssertionError(f"Unexpected core call: {base} {path}")

    monkeypatch.setattr(core_client, "core_json", fake_core)
    route = "/reports/report-1/triage-suggestion"
    assert client.post(route, headers=CITIZEN).status_code == 403
    assert client.get("/reports/triage-metrics", headers=CITIZEN).status_code == 403
    assert client.get(route, headers=DISPATCHER).status_code == 404
    created = client.post(route, headers=DISPATCHER)
    assert created.status_code == 201
    suggestion = created.json()
    assert suggestion["suggested_unit"] == "infrastructure"
    assert suggestion["urgency"] == "high"
    assert suggestion["similar"][0]["id"] == "report-2"
    assert client.get(route, headers=OUTSIDER).status_code == 404
    assert client.get(route, headers=DISPATCHER).json()["stale"] is False
    assert client.get("/reports/triage-metrics", headers=DISPATCHER).json() == {
        "generated": 1, "reviewed": 0, "accepted": 0, "overridden": 0,
    }
    due = (datetime.now(timezone.utc) + timedelta(days=3)).isoformat()
    dispatch = {"unit_id": "environment", "due_at": due, "note": "Cán bộ chọn đơn vị môi trường",
                "suggestion_id": suggestion["id"]}
    assert client.post("/reports/report-1/dispatch", headers=OUTSIDER, json=dispatch).status_code == 404
    assert client.post("/reports/report-1/dispatch", headers=DISPATCHER,
                       json={**dispatch, "suggestion_id": "not-a-valid-suggestion-identifier"}).status_code == 422
    accepted = client.post("/reports/report-1/dispatch", headers=DISPATCHER, json=dispatch)
    assert accepted.status_code == 200
    assert accepted.json()["assigned_unit"] == "environment"
    assert client.get("/reports/triage-metrics", headers=DISPATCHER).json() == {
        "generated": 1, "reviewed": 1, "accepted": 0, "overridden": 1,
    }
    assert client.post("/reports/report-1/dispatch", headers=DISPATCHER, json=dispatch).status_code == 409
    assert any(base == config.INSIGHT_URL for base, _, _ in calls)
