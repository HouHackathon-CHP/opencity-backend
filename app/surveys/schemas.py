# SPDX-License-Identifier: Apache-2.0
from pydantic import BaseModel, Field


class SurveyInput(BaseModel):
    title: str = Field(min_length=5, max_length=160)
    description: str = Field(min_length=20, max_length=2000)
    options: list[str] = Field(min_length=2, max_length=8)


class SurveyAnswer(BaseModel):
    option_id: str
