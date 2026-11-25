# SPDX-License-Identifier: Apache-2.0
from typing import Any
from app.repositories import ward as repo
from app.schemas.ward import DistrictSummary, WardDetail, WardLocateResult, WardSummary


def list_wards(
    keyword: str | None = None,
    district: str | None = None,
    ward_type: str | None = None,
    lat: float | None = None,
    lon: float | None = None,
    limit: int = 200,
    offset: int = 0,
) -> list[WardSummary]:
    return repo.list_wards(
        keyword=keyword,
        district=district,
        ward_type=ward_type,
        lat=lat,
        lon=lon,
        limit=limit,
        offset=offset,
    )


def list_districts() -> list[DistrictSummary]:
    return repo.list_districts()


def get_ward(ward_id: str) -> WardDetail | None:
    return repo.get_ward_by_id(ward_id)


def locate_ward(lat: float, lon: float) -> WardLocateResult | None:
    return repo.locate_ward(lat, lon)


def get_boundaries() -> dict[str, Any]:
    return repo.get_boundaries()
