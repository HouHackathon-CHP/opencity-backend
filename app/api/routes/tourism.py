# SPDX-License-Identifier: Apache-2.0
from typing import Any
from fastapi import APIRouter, Depends, Query

from app.core.security import Caller, caller
from app.schemas.tourism import (
    TourismCategorySummary,
    TourismDestinationDetail,
    TourismDestinationInput,
    TourismDestinationSummary,
)
from app.services import tourism as service

router = APIRouter(prefix="/tourism", tags=["tourism"])


@router.get("/destinations", response_model=list[TourismDestinationSummary])
def list_destinations(
    keyword: str | None = Query(default=None, description="Tìm theo tên di tích, địa chỉ, thẻ tag"),
    category: str | None = Query(default=None, description="monument | museum | religious | cultural | landscape"),
    district: str | None = Query(default=None, description="Lọc theo quận/huyện"),
    heritage_level: str | None = Query(default=None, description="Lọc theo cấp xếp hạng di sản"),
    lat: float | None = Query(default=None, description="Vĩ độ GPS của người dùng"),
    lon: float | None = Query(default=None, description="Kinh độ GPS của người dùng"),
    radius_km: float | None = Query(default=None, description="Bán kính tìm kiếm (km)"),
    audio_guide_only: bool = Query(default=False, description="Chỉ lấy điểm có thuyết minh số"),
    identity: Caller = Depends(caller),
) -> list[TourismDestinationSummary]:
    return service.list_destinations(
        identity=identity,
        keyword=keyword,
        category=category,
        district=district,
        heritage_level=heritage_level,
        lat=lat,
        lon=lon,
        radius_km=radius_km,
        audio_guide_only=audio_guide_only,
    )


@router.get("/destinations/{destination_id}", response_model=TourismDestinationDetail)
def get_destination_detail(
    destination_id: str,
    lat: float | None = Query(default=None, description="Vĩ độ GPS người dùng để tính khoảng cách"),
    lon: float | None = Query(default=None, description="Kinh độ GPS người dùng để tính khoảng cách"),
    identity: Caller = Depends(caller),
) -> TourismDestinationDetail:
    return service.get_destination_detail(
        destination_id=destination_id,
        identity=identity,
        lat=lat,
        lon=lon,
    )


@router.get("/geojson")
def get_tourism_geojson(
    category: str | None = Query(default=None, description="Lọc theo loại hình di sản"),
    identity: Caller = Depends(caller),
) -> dict[str, Any]:
    return service.get_geojson(identity=identity, category=category)


@router.get("/categories", response_model=list[TourismCategorySummary])
def list_categories(
    identity: Caller = Depends(caller),
) -> list[TourismCategorySummary]:
    return service.get_categories(identity=identity)


@router.get("/districts", response_model=list[str])
def list_districts(
    identity: Caller = Depends(caller),
) -> list[str]:
    return service.get_districts(identity=identity)


@router.post("/destinations", response_model=TourismDestinationDetail, status_code=201)
def create_destination(
    body: TourismDestinationInput,
    identity: Caller = Depends(caller),
) -> TourismDestinationDetail:
    return service.create_destination(identity=identity, data=body)


@router.put("/destinations/{destination_id}", response_model=TourismDestinationDetail)
def update_destination(
    destination_id: str,
    body: TourismDestinationInput,
    identity: Caller = Depends(caller),
) -> TourismDestinationDetail:
    return service.update_destination(
        destination_id=destination_id,
        identity=identity,
        data=body,
    )


@router.delete("/destinations/{destination_id}")
def delete_destination(
    destination_id: str,
    identity: Caller = Depends(caller),
) -> dict[str, Any]:
    return service.delete_destination(destination_id=destination_id, identity=identity)

