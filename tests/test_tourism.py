# SPDX-License-Identifier: Apache-2.0
import os
import pytest
from fastapi.testclient import TestClient

os.environ["INTERNAL_GATEWAY_SECRET"] = "test-secret"

from app import main  # noqa: E402
from app.core import config  # noqa: E402
from app.repositories import tourism as repo  # noqa: E402

client = TestClient(main.app)
CITIZEN = {
    "X-Internal-Secret": "test-secret",
    "X-DXOS-User": "citizen-1",
    "X-DXOS-Tenant": "tenant-1",
    "X-DXOS-Roles": "citizen",
}


@pytest.fixture(autouse=True)
def setup_test_db(tmp_path, monkeypatch):
    test_db = tmp_path / "test_tourism.sqlite3"
    monkeypatch.setattr(config, "TOURISM_DB_PATH", str(test_db))
    repo.init_db()


def test_tourism_rejected_without_gateway_secret():
    response = client.get("/tourism/destinations")
    assert response.status_code == 403


def test_list_tourism_destinations():
    response = client.get("/tourism/destinations", headers=CITIZEN)
    assert response.status_code == 200
    data = response.json()
    assert len(data) >= 15
    first = data[0]
    assert "id" in first
    assert "name" in first
    assert "category" in first
    assert "latitude" in first
    assert "longitude" in first


def test_search_tourism_by_keyword_unaccent():
    response = client.get("/tourism/destinations", headers=CITIZEN, params={"keyword": "thap rua"})
    assert response.status_code == 200
    data = response.json()
    assert len(data) >= 1
    names = [item["name"] for item in data]
    assert any("Tháp Rùa" in name for name in names)


def test_filter_tourism_by_category():
    response = client.get("/tourism/destinations", headers=CITIZEN, params={"category": "museum"})
    assert response.status_code == 200
    data = response.json()
    assert len(data) >= 2
    for item in data:
        assert item["category"] == "museum"


def test_filter_tourism_by_district():
    response = client.get("/tourism/destinations", headers=CITIZEN, params={"district": "Hoàn Kiếm"})
    assert response.status_code == 200
    data = response.json()
    assert len(data) >= 4
    for item in data:
        assert "Hoàn Kiếm" in item["district"]


def test_nearby_search_with_haversine_distance():
    response = client.get(
        "/tourism/destinations",
        headers=CITIZEN,
        params={"lat": 21.0358, "lon": 105.8340, "radius_km": 3.0},
    )
    assert response.status_code == 200
    data = response.json()
    assert len(data) >= 3
    distances = [item["distance_km"] for item in data if item["distance_km"] is not None]
    assert distances == sorted(distances)
    assert data[0]["distance_km"] < 0.5


def test_destination_detail_by_id():
    list_res = client.get("/tourism/destinations", headers=CITIZEN)
    first_id = list_res.json()[0]["id"]
    response = client.get(f"/tourism/destinations/{first_id}", headers=CITIZEN)
    assert response.status_code == 200
    detail = response.json()
    assert detail["id"] == first_id
    assert "name" in detail
    assert "heritage_level" in detail
    assert "latitude" in detail


def test_destination_detail_not_found():
    response = client.get("/tourism/destinations/dia-diem-khong-ton-tai", headers=CITIZEN)
    assert response.status_code == 404


def test_get_geojson_feature_collection():
    response = client.get("/tourism/geojson", headers=CITIZEN)
    assert response.status_code == 200
    geojson = response.json()
    assert geojson["type"] == "FeatureCollection"
    assert "features" in geojson
    assert len(geojson["features"]) >= 15
    feat = geojson["features"][0]
    assert feat["type"] == "Feature"
    assert feat["geometry"]["type"] == "Point"
    assert len(feat["geometry"]["coordinates"]) == 2
    assert "id" in feat["properties"]
    assert "connecting_bus_routes" in feat["properties"]


def test_get_categories():
    response = client.get("/tourism/categories", headers=CITIZEN)
    assert response.status_code == 200
    categories = response.json()
    assert len(categories) >= 4
    keys = [c["key"] for c in categories]
    assert "monument" in keys
    assert "museum" in keys
    assert "religious" in keys


def test_get_districts():
    response = client.get("/tourism/districts", headers=CITIZEN)
    assert response.status_code == 200
    districts = response.json()
    assert isinstance(districts, list)
    assert len(districts) >= 1
    assert "Hà Nội" not in districts
