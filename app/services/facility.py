# SPDX-License-Identifier: Apache-2.0
from typing import Any
from fastapi import HTTPException

from app.core.security import Caller, require_manager
from app.repositories import facility as repo
from app.schemas.facility import (
    FacilityCategorySummary,
    FacilityDetail,
    FacilityInput,
    FacilitySummary,
)


def list_facilities(
    identity: Caller,
    keyword: str | None = None,
    category: str | None = None,
    facility_type: str | None = None,
    district: str | None = None,
    lat: float | None = None,
    lon: float | None = None,
    radius_km: float | None = None,
    emergency_only: bool = False,
) -> list[FacilitySummary]:
    items = repo.query_facilities(
        keyword=keyword,
        category=category,
        facility_type=facility_type,
        district=district,
        lat=lat,
        lon=lon,
        radius_km=radius_km,
        emergency_only=emergency_only,
        active_only=True,
    )
    return [FacilitySummary(**item) for item in items]


def get_facility_detail(
    facility_id: str,
    identity: Caller,
    lat: float | None = None,
    lon: float | None = None,
) -> FacilityDetail:
    item = repo.get_facility_by_id(facility_id, lat=lat, lon=lon)
    if not item:
        raise HTTPException(status_code=404, detail="Không tìm thấy cơ sở y tế / trường học")
    return FacilityDetail(**item)


def list_categories() -> list[FacilityCategorySummary]:
    items = repo.get_facility_categories()
    return [FacilityCategorySummary(**item) for item in items]


def list_districts(facility_type: str | None = None) -> list[str]:
    return repo.get_facility_districts(facility_type=facility_type)


def create_facility(body: FacilityInput, identity: Caller) -> FacilityDetail:
    if "admin" not in identity.roles and "facilities_operator" not in identity.roles:
        raise HTTPException(status_code=403, detail="Yêu cầu quyền quản trị viên hoặc cán bộ điều hành y tế/giáo dục")
    created = repo.create_facility(body.model_dump())
    return FacilityDetail(**created)


def update_facility(facility_id: str, body: FacilityInput, identity: Caller) -> FacilityDetail:
    if "admin" not in identity.roles and "facilities_operator" not in identity.roles:
        raise HTTPException(status_code=403, detail="Yêu cầu quyền quản trị viên hoặc cán bộ điều hành y tế/giáo dục")
    updated = repo.update_facility(facility_id, body.model_dump())
    if not updated:
        raise HTTPException(status_code=404, detail="Không tìm thấy cơ sở để cập nhật")
    return FacilityDetail(**updated)


def delete_facility(facility_id: str, identity: Caller) -> dict[str, Any]:
    if "admin" not in identity.roles and "facilities_operator" not in identity.roles:
        raise HTTPException(status_code=403, detail="Yêu cầu quyền quản trị viên hoặc cán bộ điều hành y tế/giáo dục")
    ok = repo.delete_facility(facility_id)
    if not ok:
        raise HTTPException(status_code=404, detail="Không tìm thấy cơ sở để xóa")
    return {"success": True, "id": facility_id}
