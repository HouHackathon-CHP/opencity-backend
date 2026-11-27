# SPDX-License-Identifier: Apache-2.0
from typing import Any
from fastapi import HTTPException

from app.core.security import Caller
from app.repositories import parking as repo
from app.schemas.parking import (
    ParkingCategorySummary,
    ParkingDetail,
    ParkingInput,
    ParkingSummary,
)


def list_parking(
    identity: Caller,
    keyword: str | None = None,
    category: str | None = None,
    parking_type: str | None = None,
    district: str | None = None,
    fee_type: str | None = None,
    is_24_7: bool = False,
    lat: float | None = None,
    lon: float | None = None,
    radius_km: float | None = None,
) -> list[ParkingSummary]:
    results = repo.query_parking(
        keyword=keyword,
        category=category,
        parking_type=parking_type,
        district=district,
        fee_type=fee_type,
        is_24_7=is_24_7,
        lat=lat,
        lon=lon,
        radius_km=radius_km,
    )
    return [ParkingSummary(**r) for r in results]


def get_parking_detail(
    parking_id: str,
    identity: Caller,
    lat: float | None = None,
    lon: float | None = None,
) -> ParkingDetail:
    item = repo.get_parking_by_id(parking_id, lat=lat, lon=lon)
    if not item:
        raise HTTPException(status_code=404, detail="Không tìm thấy điểm đỗ xe yêu cầu")
    return ParkingDetail(**item)


def list_categories() -> list[ParkingCategorySummary]:
    cats = repo.get_parking_categories()
    return [ParkingCategorySummary(**c) for c in cats]


def list_districts() -> list[str]:
    return repo.get_parking_districts()


def create_parking(body: ParkingInput, identity: Caller) -> ParkingDetail:
    if "admin" not in identity.roles and "parking_operator" not in identity.roles:
        raise HTTPException(status_code=403, detail="Yêu cầu quyền quản trị viên hoặc cán bộ quản lý điểm đỗ xe")
    created = repo.create_parking(body.model_dump())
    return ParkingDetail(**created)


def update_parking(parking_id: str, body: ParkingInput, identity: Caller) -> ParkingDetail:
    if "admin" not in identity.roles and "parking_operator" not in identity.roles:
        raise HTTPException(status_code=403, detail="Yêu cầu quyền quản trị viên hoặc cán bộ quản lý điểm đỗ xe")
    updated = repo.update_parking(parking_id, body.model_dump())
    if not updated:
        raise HTTPException(status_code=404, detail="Không tìm thấy điểm đỗ xe để cập nhật")
    return ParkingDetail(**updated)


def delete_parking(parking_id: str, identity: Caller) -> dict[str, Any]:
    if "admin" not in identity.roles and "parking_operator" not in identity.roles:
        raise HTTPException(status_code=403, detail="Yêu cầu quyền quản trị viên hoặc cán bộ quản lý điểm đỗ xe")
    ok = repo.delete_parking(parking_id)
    if not ok:
        raise HTTPException(status_code=404, detail="Không tìm thấy điểm đỗ xe để xóa")
    return {"success": True, "id": parking_id}


def get_footprints() -> dict[str, Any]:
    return repo.get_footprints()
