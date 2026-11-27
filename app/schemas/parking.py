# SPDX-License-Identifier: Apache-2.0
from typing import Any
from pydantic import BaseModel, Field


class ParkingSummary(BaseModel):
    id: str
    name: str
    category: str  # car_parking | motorcycle_parking | mixed_parking | street_parking
    parking_type: str  # surface | underground | multi-storey | street_side | rooftop
    address: str
    district: str
    latitude: float
    longitude: float
    fee: str  # Có phí | Miễn phí | Theo giờ
    fee_details: str | None = None
    capacity: int | None = None
    access: str  # Công cộng | Khách hàng | Nội bộ
    supervised: bool = True
    opening_hours: str = "24/7"
    operator: str | None = None
    distance_km: float | None = None
    tags: list[str] = Field(default_factory=list)


class ParkingDetail(BaseModel):
    id: str
    name: str
    category: str
    parking_type: str
    address: str
    district: str
    latitude: float
    longitude: float
    fee: str
    fee_details: str | None = None
    capacity: int | None = None
    access: str
    supervised: bool = True
    opening_hours: str = "24/7"
    operator: str | None = None
    description: str = ""
    contact: str | None = None
    distance_km: float | None = None
    tags: list[str] = Field(default_factory=list)
    active: bool = True
    created_at: str | None = None
    updated_at: str | None = None


class ParkingCategorySummary(BaseModel):
    key: str
    label: str
    count: int
    icon: str


class ParkingInput(BaseModel):
    name: str = Field(min_length=1, max_length=250, description="Tên điểm đỗ / Bãi đỗ xe")
    category: str = Field(default="car_parking", description="car_parking | motorcycle_parking | mixed_parking | street_parking")
    parking_type: str = Field(default="surface", description="surface | underground | multi-storey | street_side | rooftop")
    address: str = Field(min_length=1, max_length=300, description="Địa chỉ cụ thể tại Hà Nội")
    district: str = Field(min_length=1, max_length=100, description="Quận / Huyện")
    latitude: float = Field(ge=20.0, le=22.0, description="Vĩ độ GPS Hà Nội")
    longitude: float = Field(ge=105.0, le=107.0, description="Kinh độ GPS Hà Nội")
    fee: str = Field(default="Có phí", description="Có phí | Miễn phí | Theo giờ")
    fee_details: str | None = None
    capacity: int | None = Field(default=None, ge=1, le=10000, description="Sức chứa / số chỗ đỗ")
    access: str = Field(default="Công cộng", description="Công cộng | Khách hàng | Nội bộ")
    supervised: bool = True
    opening_hours: str = Field(default="24/7", description="Giờ hoạt động / Mở cửa")
    operator: str | None = None
    description: str = Field(default="", max_length=2000)
    contact: str | None = None
    tags: list[str] = Field(default_factory=list)
    active: bool = True
