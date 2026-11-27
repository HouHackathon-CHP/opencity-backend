# SPDX-License-Identifier: Apache-2.0
from typing import Any
from fastapi import APIRouter, Depends, Query

from app.core.security import Caller, caller
from app.schemas.parking import (
    ParkingCategorySummary,
    ParkingDetail,
    ParkingInput,
    ParkingSummary,
)
from app.services import parking as service

router = APIRouter(prefix="/parking", tags=["parking"])


@router.get("", response_model=list[ParkingSummary])
def list_parking(
    keyword: str | None = Query(default=None, description="Tìm theo tên bãi đỗ, phố, địa chỉ"),
    category: str | None = Query(default=None, description="car_parking | motorcycle_parking | mixed_parking | street_parking"),
    parking_type: str | None = Query(default=None, description="surface | underground | multi-storey | street_side | rooftop"),
    district: str | None = Query(default=None, description="Lọc theo quận/huyện Hà Nội"),
    fee_type: str | None = Query(default=None, description="all | free | paid"),
    is_24_7: bool = Query(default=False, description="Chỉ điểm đỗ mở cửa 24/7"),
    lat: float | None = Query(default=None, description="Vĩ độ GPS người dùng"),
    lon: float | None = Query(default=None, description="Kinh độ GPS người dùng"),
    radius_km: float | None = Query(default=None, description="Bán kính tìm kiếm (km)"),
    identity: Caller = Depends(caller),
) -> list[ParkingSummary]:
    return service.list_parking(
        identity=identity,
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


@router.get("/categories", response_model=list[ParkingCategorySummary])
def get_categories() -> list[ParkingCategorySummary]:
    return service.list_categories()


@router.get("/districts", response_model=list[str])
def get_districts() -> list[str]:
    return service.list_districts()


@router.get("/footprints")
def get_footprints() -> dict[str, Any]:
    return service.get_footprints()


@router.get("/{parking_id}", response_model=ParkingDetail)
def get_parking_detail(
    parking_id: str,
    lat: float | None = Query(default=None, description="Vĩ độ GPS tính khoảng cách"),
    lon: float | None = Query(default=None, description="Kinh độ GPS tính khoảng cách"),
    identity: Caller = Depends(caller),
) -> ParkingDetail:
    return service.get_parking_detail(
        parking_id=parking_id,
        identity=identity,
        lat=lat,
        lon=lon,
    )


@router.post("", response_model=ParkingDetail)
def create_parking(
    body: ParkingInput,
    identity: Caller = Depends(caller),
) -> ParkingDetail:
    return service.create_parking(body=body, identity=identity)


@router.put("/{parking_id}", response_model=ParkingDetail)
def update_parking(
    parking_id: str,
    body: ParkingInput,
    identity: Caller = Depends(caller),
) -> ParkingDetail:
    return service.update_parking(parking_id=parking_id, body=body, identity=identity)


@router.delete("/{parking_id}")
def delete_parking(
    parking_id: str,
    identity: Caller = Depends(caller),
) -> dict[str, Any]:
    return service.delete_parking(parking_id=parking_id, identity=identity)
