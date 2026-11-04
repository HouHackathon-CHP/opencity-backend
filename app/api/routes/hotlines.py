# SPDX-License-Identifier: Apache-2.0
"""Hotline directory endpoints."""

from fastapi import APIRouter, Depends

from app.core.security import Caller, caller
from app.schemas.hotlines import HotlineInput
from app.services import hotlines


router = APIRouter()


@router.get("/hotlines")
def list_hotlines(identity: Caller = Depends(caller)) -> list[dict]:
    return hotlines.list_hotlines(identity)


@router.post("/hotlines", status_code=201)
def create_hotline(body: HotlineInput, identity: Caller = Depends(caller)) -> dict:
    return hotlines.save_hotline(body, identity)


@router.put("/hotlines/{hotline_id}")
def update_hotline(hotline_id: str, body: HotlineInput, identity: Caller = Depends(caller)) -> dict:
    return hotlines.save_hotline(body, identity, hotline_id)
