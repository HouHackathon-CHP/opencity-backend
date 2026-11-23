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
