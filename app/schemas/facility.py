# SPDX-License-Identifier: Apache-2.0
from typing import Any
from pydantic import BaseModel, Field


class FacilitySummary(BaseModel):
    id: str
    name: str
    category: str  # hospital, clinic, pharmacy, university, high_school, secondary_school, primary_school, kindergarten
    facility_type: str  # healthcare | education
    address: str
    district: str
    latitude: float
    longitude: float
    operator_type: str  # Công lập | Tư nhân | Quốc tế
    opening_hours: str
    phone: str | None = None
    emergency_phone: str | None = None
    level: str | None = None  # Tuyến Trung ương, Chuẩn quốc gia...
    distance_km: float | None = None
    tags: list[str] = Field(default_factory=list)


class FacilityDetail(BaseModel):
    id: str
    name: str
    category: str
    facility_type: str
    address: str
    district: str
    latitude: float
    longitude: float
    operator_type: str
    opening_hours: str
    phone: str | None = None
    emergency_phone: str | None = None
    level: str | None = None
    description: str = ""
    website: str | None = None
    connecting_bus_routes: list[str] = Field(default_factory=list)
    tags: list[str] = Field(default_factory=list)
    distance_km: float | None = None
    active: bool = True
    created_at: str | None = None
    updated_at: str | None = None


class FacilityCategorySummary(BaseModel):
    key: str
    label: str
    count: int
    icon: str
    facility_type: str


class FacilityInput(BaseModel):
    name: str = Field(min_length=1, max_length=250, description="Tên cơ sở y tế / trường học")
    category: str = Field(description="hospital | clinic | pharmacy | university | high_school | secondary_school | primary_school | kindergarten")
    facility_type: str = Field(default="healthcare", description="healthcare | education")
    address: str = Field(min_length=1, max_length=300, description="Địa chỉ cụ thể tại Hà Nội")
    district: str = Field(min_length=1, max_length=100, description="Quận/huyện")
    latitude: float = Field(ge=20.0, le=22.0, description="Vĩ độ GPS Hà Nội")
    longitude: float = Field(ge=105.0, le=107.0, description="Kinh độ GPS Hà Nội")
    operator_type: str = Field(default="Công lập", description="Công lập | Tư nhân | Quốc tế")
    opening_hours: str = Field(default="07:30 - 17:00", description="Giờ hoạt động / Cấp cứu 24/7")
    phone: str | None = None
    emergency_phone: str | None = None
    level: str | None = None
    description: str = Field(default="", max_length=2000)
    website: str | None = None
    connecting_bus_routes: list[str] = Field(default_factory=list)
    tags: list[str] = Field(default_factory=list)
    active: bool = True
