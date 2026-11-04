# SPDX-License-Identifier: Apache-2.0
from pydantic import BaseModel, Field


class CommunicationInput(BaseModel):
    title: str = Field(min_length=5, max_length=160)
    summary: str = Field(min_length=10, max_length=300)
    body: str = Field(min_length=20, max_length=5000)
    area: str | None = Field(default=None, max_length=120)
