# SPDX-License-Identifier: Apache-2.0
from typing import Literal

from pydantic import BaseModel, Field


class BulletinInput(BaseModel):
    category: Literal["news", "alert"]
    title: str = Field(min_length=5, max_length=160)
    summary: str = Field(min_length=10, max_length=300)
    body: str = Field(min_length=20, max_length=5000)
    area: str | None = Field(default=None, max_length=120)
    latitude: float | None = Field(default=None, ge=-90, le=90)
    longitude: float | None = Field(default=None, ge=-180, le=180)
