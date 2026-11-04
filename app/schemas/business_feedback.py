# SPDX-License-Identifier: Apache-2.0
"""Requests for self-declared business petitions."""

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


class PetitionInput(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)

    company_name: str = Field(min_length=3, max_length=160)
    tax_code: str = Field(pattern=r"^\d{10}(\d{3})?$")
    representative: str = Field(min_length=3, max_length=120)
    sector: Literal["investment", "tax", "land", "labor", "other"]
    title: str = Field(min_length=5, max_length=160)
    description: str = Field(min_length=20, max_length=4000)
    requested_resolution: str = Field(min_length=10, max_length=2000)


class PetitionNote(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)
    note: str = Field(min_length=10, max_length=2000)
