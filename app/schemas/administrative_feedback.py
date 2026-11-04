# SPDX-License-Identifier: Apache-2.0
"""Requests for local administrative-procedure feedback."""

from typing import Literal

from pydantic import BaseModel, Field


class FeedbackInput(BaseModel):
    title: str = Field(min_length=5, max_length=120)
    procedure: str = Field(min_length=3, max_length=120)
    agency: str = Field(min_length=3, max_length=120)
    issue_type: Literal["delay", "instructions", "conduct", "other"]
    description: str = Field(min_length=20, max_length=2000)


class FeedbackNote(BaseModel):
    note: str = Field(min_length=10, max_length=2000)
