# SPDX-License-Identifier: Apache-2.0
from pydantic import BaseModel, Field


class GroupInput(BaseModel):
    title: str = Field(min_length=5, max_length=120)
    description: str = Field(min_length=20, max_length=1000)
    area: str | None = Field(default=None, max_length=120)


class PostInput(BaseModel):
    body: str = Field(min_length=3, max_length=2000)
