# SPDX-License-Identifier: Apache-2.0
"""Validated public support contact data."""

from pydantic import BaseModel, ConfigDict, Field


class HotlineInput(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)

    name: str = Field(min_length=3, max_length=120)
    unit: str = Field(min_length=3, max_length=120)
    phone: str = Field(pattern=r"^\+?[0-9][0-9\s().-]{4,22}$")
    area: str = Field(default="", max_length=120)
    hours: str = Field(default="", max_length=120)
    description: str = Field(default="", max_length=500)
    active: bool = True
