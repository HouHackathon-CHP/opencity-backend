# SPDX-License-Identifier: Apache-2.0
"""Requests for the local citizen reception appointment module."""

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field


class SlotInput(BaseModel):
    starts_at: datetime
    ends_at: datetime
    location: str = Field(min_length=3, max_length=200)
    capacity: int = Field(ge=1, le=20)


class AppointmentInput(BaseModel):
    slot_id: str
    reason: str = Field(min_length=10, max_length=1000)


class DecisionInput(BaseModel):
    decision: Literal["confirmed", "rejected"]
    note: str = Field(default="", max_length=500)
