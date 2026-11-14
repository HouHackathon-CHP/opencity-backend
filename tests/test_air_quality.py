# SPDX-License-Identifier: Apache-2.0
"""Tests for OpenCity Air Quality monitoring domain and API routes."""

import os

os.environ["INTERNAL_GATEWAY_SECRET"] = "test-secret"

from fastapi.testclient import TestClient  # noqa: E402
from app.main import app  # noqa: E402
from app.core import config  # noqa: E402


client = TestClient(app)
CITIZEN = {
    "X-Internal-Secret": "test-secret",
    "X-DXOS-User": "citizen-1",
    "X-DXOS-Tenant": "tenant-1",
    "X-DXOS-Roles": "citizen",
}
OPERATOR = {
    "X-Internal-Secret": "test-secret",
    "X-DXOS-User": "dxos-air-quality",
    "X-DXOS-Tenant": "tenant-1",
    "X-DXOS-Roles": "air_quality_operator",
}
PUBLIC = {**CITIZEN, "X-DXOS-User": "anonymous", "X-DXOS-Roles": "public"}


def test_air_quality_public_and_operator_flow(monkeypatch, tmp_path):
    monkeypatch.setattr(config, "AIR_QUALITY_DB_PATH", str(tmp_path / "air-quality.sqlite3"))
    assert client.get("/air-quality/waqi-status", headers=CITIZEN).status_code == 403
    assert client.get("/air-quality/waqi-status", headers=OPERATOR).status_code == 200

    summary_resp = client.get("/air-quality/summary", headers=CITIZEN)
    assert summary_resp.status_code == 200
    summary = summary_resp.json()
    assert "average_aqi" in summary
    assert "classification" in summary
    assert summary["total_stations"] == 0

    stations_resp = client.get("/air-quality/stations", headers=CITIZEN)
    assert stations_resp.status_code == 200
    assert stations_resp.json() == []

    missing_resp = client.get("/air-quality/stations/HN-HOANKIEM", headers=CITIZEN)
    assert missing_resp.status_code == 404

    station_payload = {
        "code": "HN-HOANKIEM",
        "name": "Trạm Hoàn Kiếm",
        "address": "Phố Hàng Đậu, Hoàn Kiếm, Hà Nội",
        "area_type": "Giao thông",
        "latitude": 21.0398,
        "longitude": 105.8458,
    }
    citizen_create = client.post("/air-quality/stations", headers=CITIZEN, json=station_payload)
    assert citizen_create.status_code == 403

    operator_create = client.post("/air-quality/stations", headers=OPERATOR, json=station_payload)
    assert operator_create.status_code == 201
    assert operator_create.json()["code"] == "HN-HOANKIEM"

    stations_resp = client.get("/air-quality/stations", headers=CITIZEN)
    assert stations_resp.status_code == 200
    stations = stations_resp.json()
    assert len(stations) == 1
    assert stations[0]["code"] == "HN-HOANKIEM"

    reading_payload = {
        "station_code": "HN-HOANKIEM",
        "aqi": 185,
        "pm25": 115.0,
        "pm10": 160.0,
        "temperature": 27.5,
        "humidity": 78.0,
    }
    citizen_post = client.post("/air-quality/readings", headers=CITIZEN, json=reading_payload)
    assert citizen_post.status_code == 403

    operator_post = client.post("/air-quality/readings", headers=OPERATOR, json=reading_payload)
    assert operator_post.status_code == 201
    created_reading = operator_post.json()
    assert created_reading["latest_reading"]["aqi"] == 185
    assert created_reading["classification"]["label"] == "Xấu"

    updated_detail = client.get("/air-quality/stations/HN-HOANKIEM", headers=CITIZEN).json()
    assert updated_detail["latest_reading"]["aqi"] == 185
    assert updated_detail["classification"]["label"] == "Xấu"


def test_public_air_quality_excludes_hidden_stations(monkeypatch, tmp_path):
    monkeypatch.setattr(config, "AIR_QUALITY_DB_PATH", str(tmp_path / "public-air-quality.sqlite3"))
    station = {
        "code": "HN-HIDDEN", "name": "Trạm nội bộ", "address": "Hà Nội",
        "area_type": "Đô thị", "latitude": 21.03, "longitude": 105.85,
    }
    assert client.post("/air-quality/stations", headers=OPERATOR, json=station).status_code == 201
    assert client.patch(
        "/air-quality/stations/HN-HIDDEN/status", headers=OPERATOR, json={"status": "hidden"}
    ).status_code == 200
    assert client.get("/air-quality/stations", headers=PUBLIC).json() == []
    assert client.get("/air-quality/stations/HN-HIDDEN", headers=PUBLIC).status_code == 404
    assert client.get("/air-quality/summary", headers=PUBLIC).json()["total_stations"] == 0
    assert client.get("/air-quality/stations/HN-HIDDEN", headers=OPERATOR).status_code == 200
