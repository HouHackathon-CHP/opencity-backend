# SPDX-License-Identifier: Apache-2.0
from typing import Any
from fastapi import APIRouter, Depends, Query

from app.core.security import Caller, caller
from app.schemas.facility import (
    FacilityCategorySummary,
    FacilityDetail,
    FacilityInput,
    FacilitySummary,
)
from app.services import facility as service

router = APIRouter(prefix="/facilities", tags=["facilities"])


@router.get("", response_model=list[FacilitySummary])
def list_facilities(
    keyword: str | None = Query(default=None, description="Tìm theo tên bệnh viện, trường học, địa chỉ"),
    category: str | None = Query(default=None, description="hospital | clinic | pharmacy | university | high_school..."),
    facility_type: str | None = Query(default=None, description="healthcare | education"),
    district: str | None = Query(default=None, description="Lọc theo quận/huyện Hà Nội"),
    lat: float | None = Query(default=None, description="Vĩ độ GPS người dùng"),
    lon: float | None = Query(default=None, description="Kinh độ GPS người dùng"),
    radius_km: float | None = Query(default=None, description="Bán kính tìm kiếm (km)"),
    emergency_only: bool = Query(default=False, description="Chỉ cơ sở có cấp cứu 24/7"),
    identity: Caller = Depends(caller),
) -> list[FacilitySummary]:
    return service.list_facilities(
        identity=identity,
        keyword=keyword,
        category=category,
        facility_type=facility_type,
        district=district,
        lat=lat,
        lon=lon,
        radius_km=radius_km,
        emergency_only=emergency_only,
    )


@router.get("/categories", response_model=list[FacilityCategorySummary])
def get_categories() -> list[FacilityCategorySummary]:
    return service.list_categories()


@router.get("/districts", response_model=list[str])
def get_districts(
    facility_type: str | None = Query(default=None, description="healthcare | education"),
) -> list[str]:
    return service.list_districts(facility_type=facility_type)


@router.get("/{facility_id}", response_model=FacilityDetail)
def get_facility_detail(
    facility_id: str,
    lat: float | None = Query(default=None, description="Vĩ độ GPS tính khoảng cách"),
    lon: float | None = Query(default=None, description="Kinh độ GPS tính khoảng cách"),
    identity: Caller = Depends(caller),
) -> FacilityDetail:
    return service.get_facility_detail(
        facility_id=facility_id,
        identity=identity,
        lat=lat,
        lon=lon,
    )


@router.post("", response_model=FacilityDetail)
def create_facility(
    body: FacilityInput,
    identity: Caller = Depends(caller),
) -> FacilityDetail:
    return service.create_facility(body=body, identity=identity)


@router.put("/{facility_id}", response_model=FacilityDetail)
def update_facility(
    facility_id: str,
    body: FacilityInput,
    identity: Caller = Depends(caller),
) -> FacilityDetail:
    return service.update_facility(facility_id=facility_id, body=body, identity=identity)


@router.delete("/{facility_id}")
def delete_facility(
    facility_id: str,
    identity: Caller = Depends(caller),
) -> dict[str, Any]:
    return service.delete_facility(facility_id=facility_id, identity=identity)
