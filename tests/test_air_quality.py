# SPDX-License-Identifier: Apache-2.0
"""Tests for OpenCity Air Quality monitoring domain and API routes."""

import os

os.environ["INTERNAL_GATEWAY_SECRET"] = "test-secret"

from fastapi.testclient import TestClient  # noqa: E402
from app.main import app  # noqa: E402
from app.core import config  # noqa: E402
from app.repositories import air_quality as air_repo  # noqa: E402
from app.services import waqi  # noqa: E402


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


def test_waqi_sync_keeps_all_map_points_and_no_missing_values(monkeypatch, tmp_path):
    monkeypatch.setattr(config, "AIR_QUALITY_DB_PATH", str(tmp_path / "waqi.sqlite3"))
    monkeypatch.setattr(waqi, "get_effective_waqi_token", lambda: "test-token")
    points = [
        {"uid": 13026, "code": "WAQI-P13026", "name": "Real source A",
         "latitude": 21.01525, "longitude": 105.80013, "aqi": 24,
         "recorded_at": "2026-11-25T09:00:00+00:00"},
        {"uid": -477292, "code": "WAQI-N477292", "name": "Real source B",
         "latitude": 21.0031, "longitude": 105.7947, "aqi": 3,
         "recorded_at": "2026-11-25T09:00:00+00:00"},
        {"uid": 8641, "code": "WAQI-P8641", "name": "No AQI source",
         "latitude": 21.0215, "longitude": 105.8188, "aqi": None,
         "recorded_at": "2026-11-25T09:00:00+00:00"},
    ]
    monkeypatch.setattr(waqi, "fetch_waqi_stations", lambda token: points)
    details = {
        13026: {"aqi": 24, "pm25": 24.0, "pm10": None, "temperature": 18.0,
                "humidity": 72.0, "co": None, "no2": None, "o3": None, "so2": None,
                "address": "Actual source address", "recorded_at": "2026-11-25T09:00:00+00:00",
                "note": "Nguồn: WAQI"},
    }
    monkeypatch.setattr(waqi, "fetch_waqi_reading", lambda uid, token: details[uid])
    with air_repo.air_quality_db() as connection:
        air_repo.insert_station(connection, "demo", "HN-HOANKIEM-DEMO", "Demo", "Hà Nội",
                                "Đô thị", 21.0285, 105.8542)
    result = waqi.sync_all_stations("demo")
    assert result["total_stations"] == 3
    assert result["synced_count"] == 2

    public_demo = {**PUBLIC, "X-DXOS-Tenant": "demo"}
    stations = client.get("/air-quality/stations", headers=public_demo).json()
    assert {station["code"] for station in stations} == {point["code"] for point in points}
    station = next(item for item in stations if item["code"] == "WAQI-P13026")
    assert (station["latitude"], station["longitude"]) == (21.01525, 105.80013)
    assert station["latest_reading"]["pm10"] is None
    assert station["latest_reading"]["recorded_at"] == "2026-11-25T09:00:00+00:00"
    missing = next(item for item in stations if item["code"] == "WAQI-P8641")
    assert missing["latest_reading"] is None
    assert missing["classification"]["label"] == "Chưa có dữ liệu"
    assert client.get("/air-quality/summary", headers=public_demo).json()["total_stations"] == 3
