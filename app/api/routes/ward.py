# SPDX-License-Identifier: Apache-2.0
from typing import Any
from fastapi import APIRouter, Depends, HTTPException, Query

from app.core.security import Caller, caller
from app.schemas.ward import DistrictSummary, WardDetail, WardLocateResult, WardSummary, WardUpdateInput
from app.services import ward as service

router = APIRouter(prefix="/wards", tags=["wards"])


@router.get("", response_model=list[WardSummary])
def list_wards(
    keyword: str | None = Query(default=None, description="Tìm theo tên phường/xã, quận, địa chỉ"),
    district: str | None = Query(default=None, description="Lọc theo quận/huyện Hà Nội"),
    ward_type: str | None = Query(default=None, description="Phường | Xã | Thị trấn"),
    lat: float | None = Query(default=None, description="Vĩ độ người dùng"),
    lon: float | None = Query(default=None, description="Kinh độ người dùng"),
    limit: int = Query(default=200, ge=1, le=500),
    offset: int = Query(default=0, ge=0),
) -> list[WardSummary]:
    return service.list_wards(
        keyword=keyword,
        district=district,
        ward_type=ward_type,
        lat=lat,
        lon=lon,
        limit=limit,
        offset=offset,
    )


@router.get("/districts", response_model=list[DistrictSummary])
def list_districts() -> list[DistrictSummary]:
    return service.list_districts()


@router.get("/boundaries")
def get_boundaries() -> dict[str, Any]:
    return service.get_boundaries()


@router.get("/locate", response_model=WardLocateResult)
def locate_ward(
    lat: float = Query(..., description="Vĩ độ hiện tại"),
    lon: float = Query(..., description="Kinh độ hiện tại"),
) -> WardLocateResult:
    result = service.locate_ward(lat, lon)
    if not result:
        raise HTTPException(status_code=404, detail="Không xác định được phường/xã tại toạ độ này")
    return result


@router.get("/{ward_id}", response_model=WardDetail)
def get_ward_detail(ward_id: str) -> WardDetail:
    ward = service.get_ward(ward_id)
    if not ward:
        raise HTTPException(status_code=404, detail="Không tìm thấy phường/xã")
    return ward


@router.put("/{ward_id}", response_model=WardDetail)
def update_ward(
    ward_id: str,
    body: WardUpdateInput,
    identity: Caller = Depends(caller),
) -> WardDetail:
    if "admin" not in identity.roles and "digital_ward_operator" not in identity.roles:
        raise HTTPException(
            status_code=403,
            detail="Chỉ có Quản trị viên (admin) hoặc Cán bộ Xã/Phường mới có quyền cập nhật thông tin",
        )
    updated = service.update_ward(ward_id, body)
    if not updated:
        raise HTTPException(status_code=404, detail="Không tìm thấy phường/xã")
    return updated

