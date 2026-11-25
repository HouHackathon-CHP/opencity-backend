# SPDX-License-Identifier: Apache-2.0
from typing import Any
from pydantic import BaseModel, Field


class WardSummary(BaseModel):
    id: str
    code: str
    name: str
    full_name: str
    district: str
    type: str  # Phường | Xã | Thị trấn
    area_km2: float = 0.0
    postal_code: str = ""
    center_lat: float
    center_lon: float
    office_address: str = ""
    phone: str = ""
    office_hours: str = ""
    population: int = 0
    distance_km: float | None = None


class WardDetail(WardSummary):
    bbox: list[float] = Field(default_factory=list)
    services_list: list[str] = Field(
        default_factory=lambda: [
            "Cấp đổi CCCD / Định danh điện tử VNeID",
            "Chứng thực bản sao điện tử & chữ ký",
            "Đăng ký khai sinh, kết hôn, khai tử",
            "Tiếp nhận phản ánh hiện trường & an ninh trật tự",
            "Đăng ký thường trú, tạm trú trực tuyến",
            "Thủ tục bảo trợ xã hội và người có công",
        ]
    )
    hotlines: list[dict[str, str]] = Field(
        default_factory=lambda: [
            {"label": "Công an phường/xã", "phone": "113"},
            {"label": "Cứu hoả & Cứu hộ", "phone": "114"},
            {"label": "Cấp cứu y tế", "phone": "115"},
            {"label": "Tổng đài dịch vụ công Hà Nội", "phone": "024 1022"},
        ]
    )
    active: bool = True


class DistrictSummary(BaseModel):
    district: str
    ward_count: int
    total_area_km2: float
    total_population: int
    types_count: dict[str, int] = Field(default_factory=dict)


class WardLocateResult(BaseModel):
    ward: WardDetail
    distance_km: float
    located_inside: bool = True
