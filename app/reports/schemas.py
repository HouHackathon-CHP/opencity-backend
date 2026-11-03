# SPDX-License-Identifier: Apache-2.0
from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field


class DispatchInput(BaseModel):
    unit_id: Literal["infrastructure", "environment", "transport", "intake"]
    due_at: datetime
    note: str = Field(min_length=3, max_length=500)


class TransferInput(BaseModel):
    unit_id: Literal["infrastructure", "environment", "transport", "intake"]
    reason: str = Field(min_length=5, max_length=500)


class NoteInput(BaseModel):
    note: str = Field(min_length=3, max_length=500)
