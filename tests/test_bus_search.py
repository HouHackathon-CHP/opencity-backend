# SPDX-License-Identifier: Apache-2.0
import pytest
from pathlib import Path
import shutil
"""Test suite for OpenCity bus search and route lookup endpoints."""

import os

os.environ["INTERNAL_GATEWAY_SECRET"] = "test-secret"

from fastapi.testclient import TestClient  # noqa: E402
from app.core import config  # noqa: E402
from app.main import app  # noqa: E402


client = TestClient(app)
BASE_HEADERS = {
    "X-Internal-Secret": "test-secret",
    "X-DXOS-User": "citizen-1",
    "X-DXOS-Tenant": "hanoi",
    "X-DXOS-Roles": "citizen",
}
OPERATOR_HEADERS = {
    **BASE_HEADERS,
    "X-DXOS-User": "bus-operator",
    "X-DXOS-Roles": "bus_search_operator",
}


@pytest.fixture(autouse=True)
def setup_test_db(tmp_path, monkeypatch):
    test_db = tmp_path / "test_bus.sqlite3"
    candidates = [
        Path("opencity-backend-main/data/bus-search.sqlite3"),
        Path("data/bus-search.sqlite3"),
        Path("../data/bus-search.sqlite3"),
    ]
    for c in candidates:
        if c.exists() and c.stat().st_size > 10000:
            shutil.copy(c, test_db)
            break
    monkeypatch.setattr(config, "BUS_SEARCH_DB_PATH", str(test_db))


def test_bus_routes_list_and_filter(monkeypatch, tmp_path):

    assert client.get("/bus/routes").status_code == 403

    resp = client.get("/bus/routes", headers=BASE_HEADERS)
    assert resp.status_code == 200
    routes = resp.json()
    assert len(routes) >= 7
    numbers = [r["route_number"] for r in routes]
    assert "01" in numbers
    assert "32" in numbers
    assert "BRT01" in numbers
    assert "E01" in numbers

    filter_resp = client.get("/bus/routes?keyword=01", headers=BASE_HEADERS)
    assert filter_resp.status_code == 200
    filtered_numbers = [r["route_number"] for r in filter_resp.json()]
    assert "01" in filtered_numbers

    brt_resp = client.get("/bus/routes?route_type=brt", headers=BASE_HEADERS)
    assert brt_resp.status_code == 200
    assert len(brt_resp.json()) == 1
    assert brt_resp.json()[0]["route_number"] == "BRT01"


def test_bus_route_detail(monkeypatch, tmp_path):

    resp = client.get("/bus/routes/hn-bus-01", headers=BASE_HEADERS)
    assert resp.status_code == 200
    data = resp.json()
    assert data["route_number"] == "01"
    assert len(data["forward_stops"]) > 0
    assert len(data["backward_stops"]) > 0
    assert len(data["forward_path"]) > 0
    assert data["forward_stops"][0]["name"] == "Bến xe Gia Lâm"

    assert client.get("/bus/routes/non-existent-route", headers=BASE_HEADERS).status_code == 404


def test_bus_stops_list_and_detail(monkeypatch, tmp_path):

    resp = client.get("/bus/stops", headers=BASE_HEADERS)
    assert resp.status_code == 200
    stops = resp.json()
    assert len(stops) > 0

    filter_resp = client.get("/bus/stops?keyword=Gia%20L%C3%A2m", headers=BASE_HEADERS)
    assert filter_resp.status_code == 200
    matching = filter_resp.json()
    assert any("Gia Lâm" in s["name"] for s in matching)

    stop_id = stops[0]["id"]
    detail_resp = client.get(f"/bus/stops/{stop_id}", headers=BASE_HEADERS)
    assert detail_resp.status_code == 200
    assert detail_resp.json()["id"] == stop_id
    assert "passing_routes" in detail_resp.json()


def test_bus_find_connection(monkeypatch, tmp_path):

    resp = client.get("/bus/find?from_query=Gia%20L%C3%A2m&to_query=Y%C3%AAn%20Ngh%C4%A9a", headers=BASE_HEADERS)
    assert resp.status_code == 200
    recs = resp.json()
    assert len(recs) > 0
    assert recs[0]["route_number"] == "01"
    assert recs[0]["board_stop"]["name"] == "Bến xe Gia Lâm"
    assert recs[0]["alight_stop"]["name"] == "Bến xe Yên Nghĩa"


def test_bus_audit_report(monkeypatch, tmp_path):

    resp = client.get("/bus/audit", headers=BASE_HEADERS)
    assert resp.status_code == 200
    data = resp.json()
    assert data["total_routes"] >= 7
    assert data["total_stops"] >= 15
    assert data["completeness_percentage"] > 0
    assert "OpenStreetMap" in data["osm_data_source"]
    assert "ODbL" in data["license"]
    assert "overpass_query_sample" in data


def test_bus_import_and_sync(monkeypatch, tmp_path):

    sample_geojson = {
        "type": "FeatureCollection",
        "features": [
            {
                "type": "Feature",
                "geometry": {"type": "Point", "coordinates": [105.80, 21.02]},
                "properties": {"name": "Trạm Thử Nghiệm", "shelter": "yes", "ref": "999"}
            }
        ]
    }
    assert client.post(
        "/bus/import",
        headers=BASE_HEADERS,
        json={"source_name": "Test", "data_format": "geojson", "payload": sample_geojson}
    ).status_code == 403

    import_resp = client.post(
        "/bus/import",
        headers=OPERATOR_HEADERS,
        json={"source_name": "Test", "data_format": "geojson", "payload": sample_geojson}
    )
    assert import_resp.status_code == 200
    assert import_resp.json()["success"] is True

    sync_resp = client.post("/bus/sync", headers=OPERATOR_HEADERS, json={})
    assert sync_resp.status_code == 200
    assert "routes_synced" in sync_resp.json()


def test_manual_route_crud(monkeypatch, tmp_path):

    route_payload = {
        "route_number": "999",
        "name": "Tuyến 999: Mỹ Đình - Long Biên",
        "operator": "Transerco",
        "route_type": "standard",
        "from_terminal": "Bến xe Mỹ Đình",
        "to_terminal": "Bến xe Long Biên",
        "operating_hours": "05:00 - 21:00",
        "frequency": "15 phút/chuyến",
        "fare": "8.000 đ/lượt",
        "color": "#16a34a",
    }

    assert client.post("/bus/routes", headers=BASE_HEADERS, json=route_payload).status_code == 403

    create_resp = client.post("/bus/routes", headers=OPERATOR_HEADERS, json=route_payload)
    assert create_resp.status_code == 201
    created = create_resp.json()
    assert created["route_number"] == "999"
    assert created["name"] == "Tuyến 999: Mỹ Đình - Long Biên"
    route_id = created["id"]

    assert client.put(f"/bus/routes/{route_id}", headers=BASE_HEADERS, json={"name": "Tuyến 999 Mới"}).status_code == 403

    update_resp = client.put(f"/bus/routes/{route_id}", headers=OPERATOR_HEADERS, json={"name": "Tuyến 999 Mới"})
    assert update_resp.status_code == 200
    assert update_resp.json()["name"] == "Tuyến 999 Mới"

    delete_resp = client.delete(f"/bus/routes/{route_id}", headers=OPERATOR_HEADERS)
    assert delete_resp.status_code == 200
    assert delete_resp.json()["success"] is True

    assert client.get(f"/bus/routes/{route_id}", headers=BASE_HEADERS).status_code == 404


def test_manual_stop_crud(monkeypatch, tmp_path):

    stop_payload = {
        "name": "Trạm Thử Nghiệm Mới 123",
        "address": "45 Cầu Giấy, Hà Nội",
        "latitude": 21.031,
        "longitude": 105.795,
        "has_shelter": True,
        "routes": ["01", "32"],
    }

    assert client.post("/bus/stops", headers=BASE_HEADERS, json=stop_payload).status_code == 403

    create_resp = client.post("/bus/stops", headers=OPERATOR_HEADERS, json=stop_payload)
    assert create_resp.status_code == 201
    created = create_resp.json()
    assert created["name"] == "Trạm Thử Nghiệm Mới 123"
    assert created["has_shelter"] is True
    stop_id = created["id"]

    update_resp = client.put(f"/bus/stops/{stop_id}", headers=OPERATOR_HEADERS, json={"name": "Trạm Cầu Giấy Cập Nhật"})
    assert update_resp.status_code == 200
    assert update_resp.json()["name"] == "Trạm Cầu Giấy Cập Nhật"

    delete_resp = client.delete(f"/bus/stops/{stop_id}", headers=OPERATOR_HEADERS)
    assert delete_resp.status_code == 200
    assert delete_resp.json()["success"] is True

    assert client.get(f"/bus/stops/{stop_id}", headers=BASE_HEADERS).status_code == 404


