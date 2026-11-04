# SPDX-License-Identifier: Apache-2.0
"""Admin overview authorization and tenant isolation."""

import os

os.environ["INTERNAL_GATEWAY_SECRET"] = "test-secret"

from fastapi.testclient import TestClient  # noqa: E402
from app.api.routes import admin as admin_routes  # noqa: E402
from app.core import config  # noqa: E402
from app.main import app  # noqa: E402


client = TestClient(app)
HEADERS = {"X-Internal-Secret": "test-secret", "X-DXOS-User": "test-user",
           "X-DXOS-Tenant": "tenant-one", "X-DXOS-Roles": "citizen"}
PETITION = {"company_name": "Công ty Minh Châu", "tax_code": "0123456789",
            "representative": "Nguyễn Minh", "sector": "investment",
            "title": "Kiến nghị quy trình đầu tư",
            "description": "Doanh nghiệp cần hướng dẫn chi tiết về hồ sơ đầu tư.",
            "requested_resolution": "Đề nghị công bố danh mục giấy tờ cần nộp."}


def test_admin_overview_requires_role_and_scopes_tenant(monkeypatch, tmp_path):
    for key, filename in (
        ("APPOINTMENT_DB_PATH", "appointments.db"),
        ("ADMIN_FEEDBACK_DB_PATH", "administrative.db"),
        ("BUSINESS_FEEDBACK_DB_PATH", "business.db"),
        ("NEWS_DB_PATH", "news.db"),
        ("SURVEY_DB_PATH", "surveys.db"),
        ("HOTLINES_DB_PATH", "hotlines.db"),
        ("COMMUNITY_DB_PATH", "community.db"),
        ("SOCIAL_FEEDBACK_DB_PATH", "social-feedback.db"),
    ):
        monkeypatch.setattr(config, key, str(tmp_path / filename))

    async def no_reports(identity):
        assert identity.tenant in {"tenant-one", "tenant-two"}
        return []

    monkeypatch.setattr(admin_routes, "visible_report_views", no_reports)
    assert client.post("/business-feedback", headers=HEADERS, json=PETITION).status_code == 201
    assert client.get("/admin/overview", headers=HEADERS).status_code == 403
    admin = {**HEADERS, "X-DXOS-Roles": "admin"}
    assert client.post("/hotlines", headers=admin, json={
        "name": "Hỗ trợ thử nghiệm", "unit": "Trung tâm tiếp nhận",
        "phone": "0000000000", "active": True,
    }).status_code == 201
    result = client.get("/admin/overview", headers=admin)
    assert result.status_code == 200
    assert result.json()["business_feedback"] == {
        "total": 1, "breakdown": {"submitted": 1}}
    assert result.json()["reports"]["total"] == 0
    assert result.json()["appointments"]["total"] == 0
    assert result.json()["hotlines"] == {"total": 1, "breakdown": {"1": 1}}
    assert result.json()["community_groups"]["total"] == 0
    assert result.json()["social_feedback"]["total"] == 0
    other = client.get("/admin/overview", headers={**admin, "X-DXOS-Tenant": "tenant-two"})
    assert other.status_code == 200
    assert other.json()["business_feedback"]["total"] == 0
    assert other.json()["hotlines"]["total"] == 0
