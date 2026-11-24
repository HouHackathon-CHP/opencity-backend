# SPDX-License-Identifier: Apache-2.0
import os
import pytest
from fastapi.testclient import TestClient

os.environ["INTERNAL_GATEWAY_SECRET"] = "test-secret"

from app import main  # noqa: E402
from app.repositories import tourism as repo  # noqa: E402

client = TestClient(main.app)
CITIZEN = {
    "X-Internal-Secret": "test-secret",
    "X-DXOS-User": "citizen-1",
    "X-DXOS-Tenant": "tenant-1",
    "X-DXOS-Roles": "citizen",
}
ADMIN = {
    "X-Internal-Secret": "test-secret",
    "X-DXOS-User": "admin-1",
    "X-DXOS-Tenant": "tenant-1",
    "X-DXOS-Roles": "admin",
}
OPERATOR = {
    "X-Internal-Secret": "test-secret",
    "X-DXOS-User": "operator-1",
    "X-DXOS-Tenant": "tenant-1",
    "X-DXOS-Roles": "tourism_operator",
}


@pytest.fixture(autouse=True)
def setup_test_db(tmp_path, monkeypatch):
    test_db = tmp_path / "test_tourism.sqlite3"
    monkeypatch.setattr(repo, "TOURISM_DB_PATH", str(test_db))
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


def test_citizen_forbidden_to_create_or_modify():
    payload = {
        "name": "Bảo tàng Lịch sử Mới",
        "category": "museum",
        "latitude": 21.03,
        "longitude": 105.85,
    }
    # Citizen cannot create
    res = client.post("/tourism/destinations", json=payload, headers=CITIZEN)
    assert res.status_code == 403

    # Citizen cannot delete
    res = client.delete("/tourism/destinations/any-id", headers=CITIZEN)
    assert res.status_code == 403


def test_admin_crud_destination():
    payload = {
        "name": "Bảo tàng Hà Nội Mở Rộng",
        "category": "museum",
        "address": "Đường Phạm Hùng, Mễ Trì, Nam Từ Liêm, Hà Nội",
        "district": "Nam Từ Liêm",
        "latitude": 21.011,
        "longitude": 105.783,
        "description": "Bảo tàng trưng bày hiện vật thủ đô.",
        "opening_hours": "8:00 - 17:00",
        "admission_fee": "Miễn phí",
        "heritage_level": "Bảo tàng Quốc gia",
        "connecting_bus_routes": ["39", "29"],
        "audio_guide": True,
        "active": True,
    }

    # 1. Create
    res_create = client.post("/tourism/destinations", json=payload, headers=ADMIN)
    assert res_create.status_code == 201
    created = res_create.json()
    dest_id = created["id"]
    assert created["name"] == payload["name"]
    assert created["category"] == "museum"
    assert created["connecting_bus_routes"] == ["39", "29"]

    # 2. Read Detail
    res_get = client.get(f"/tourism/destinations/{dest_id}", headers=CITIZEN)
    assert res_get.status_code == 200
    assert res_get.json()["name"] == payload["name"]

    # 3. Update
    payload["name"] = "Bảo tàng Hà Nội (Cập nhật)"
    payload["admission_fee"] = "30.000 VNĐ"
    res_put = client.put(f"/tourism/destinations/{dest_id}", json=payload, headers=ADMIN)
    assert res_put.status_code == 200
    updated = res_put.json()
    assert updated["name"] == "Bảo tàng Hà Nội (Cập nhật)"
    assert updated["admission_fee"] == "30.000 VNĐ"

    # 4. Delete
    res_del = client.delete(f"/tourism/destinations/{dest_id}", headers=ADMIN)
    assert res_del.status_code == 200
    assert res_del.json()["id"] == dest_id

    # 5. Verify gone
    res_after = client.get(f"/tourism/destinations/{dest_id}", headers=CITIZEN)
    assert res_after.status_code == 404


def test_operator_can_create():
    payload = {
        "name": "Chùa Cổ Hà Nội Mới",
        "category": "religious",
        "address": "Phố Huế, Hai Bà Trưng, Hà Nội",
        "district": "Hai Bà Trưng",
        "latitude": 21.015,
        "longitude": 105.852,
        "description": "Di tích lịch sử tôn giáo lâu đời.",
    }
    res = client.post("/tourism/destinations", json=payload, headers=OPERATOR)
    assert res.status_code == 201
    item = res.json()
    assert item["name"] == payload["name"]

