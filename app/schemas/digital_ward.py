# SPDX-License-Identifier: Apache-2.0
from pydantic import BaseModel, Field


class WardInput(BaseModel):
    code: str = Field(pattern=r"^[A-Za-z0-9_-]{2,24}$")
    name: str = Field(min_length=3, max_length=120)
    address: str = Field(min_length=5, max_length=200)
    phone: str = Field(pattern=r"^\+?[0-9][0-9\s().-]{4,22}$")
    office_hours: str = Field(min_length=3, max_length=160)
    description: str = Field(min_length=20, max_length=2000)
    latitude: float | None = Field(default=None, ge=-90, le=90)
    longitude: float | None = Field(default=None, ge=-180, le=180)
    active: bool = True
