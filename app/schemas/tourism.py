# SPDX-License-Identifier: Apache-2.0
from typing import Any
from pydantic import BaseModel, Field


class TourismDestinationSummary(BaseModel):
    id: str
    name: str
    category: str
    address: str
    district: str
    latitude: float
    longitude: float
    heritage_level: str
    opening_hours: str
    admission_fee: str
    distance_km: float | None = None
    audio_guide: bool = False
    tags: list[str] = Field(default_factory=list)


class TourismDestinationDetail(BaseModel):
    id: str
    name: str
    category: str
    address: str
    district: str
    latitude: float
    longitude: float
    heritage_level: str
    description: str
    opening_hours: str
    admission_fee: str
    connecting_bus_routes: list[str] = Field(default_factory=list)
    osm_id: str | None = None
    tags: list[str] = Field(default_factory=list)
    audio_guide: bool = False
    active: bool = True
    distance_km: float | None = None


class TourismCategorySummary(BaseModel):
    key: str
    label: str
    count: int
    icon: str


class TourismDestinationInput(BaseModel):
    name: str = Field(min_length=2, max_length=200, description="Tên điểm đến di tích")
    category: str = Field(default="monument", description="monument | museum | religious | cultural | landscape")
    address: str | None = Field(default="", max_length=300)
    district: str | None = Field(default="Hà Nội", max_length=100)
    latitude: float = Field(ge=-90.0, le=90.0)
    longitude: float = Field(ge=-180.0, le=180.0)
    description: str | None = Field(default="", max_length=2000)
    opening_hours: str | None = Field(default="8:00 - 17:00", max_length=120)
    admission_fee: str | None = Field(default="Miễn phí", max_length=120)
    heritage_level: str | None = Field(default="Di tích Lịch sử - Văn hóa", max_length=120)
    connecting_bus_routes: list[str] = Field(default_factory=list)
    tags: list[str] = Field(default_factory=list)
    audio_guide: bool = False
    active: bool = True

