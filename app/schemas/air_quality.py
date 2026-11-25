# SPDX-License-Identifier: Apache-2.0
from pydantic import BaseModel, Field


class ReadingInput(BaseModel):
    station_code: str = Field(min_length=2, max_length=64)
    aqi: int = Field(ge=0, le=500)
    pm25: float = Field(ge=0, le=1000)
    pm10: float | None = Field(default=None, ge=0, le=1000)
    temperature: float | None = Field(default=None, ge=-50, le=70)
    humidity: float | None = Field(default=None, ge=0, le=100)
    co: float | None = Field(default=None, ge=0, le=100)
    no2: float | None = Field(default=None, ge=0, le=1000)
    o3: float | None = Field(default=None, ge=0, le=1000)
    so2: float | None = Field(default=None, ge=0, le=1000)
    note: str | None = Field(default=None, max_length=500)


class StationInput(BaseModel):
    code: str = Field(min_length=2, max_length=64)
    name: str = Field(min_length=2, max_length=128)
    address: str = Field(min_length=2, max_length=256)
    area_type: str = Field(default="Dân cư", max_length=64)
    latitude: float = Field(ge=-90, le=90)
    longitude: float = Field(ge=-180, le=180)


class StationStatusInput(BaseModel):
    status: str = Field(pattern="^(active|maintenance|hidden)$")


class BroadcastAlertInput(BaseModel):
    station_code: str = Field(min_length=2, max_length=64)
    title: str = Field(min_length=3, max_length=200)
    summary: str = Field(min_length=5, max_length=500)



class WaqiTokenInput(BaseModel):
    token: str = Field(min_length=1, max_length=256)
