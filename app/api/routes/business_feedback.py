# SPDX-License-Identifier: Apache-2.0
"""Business petition API."""

from fastapi import APIRouter, Depends

from app.core.security import Caller, caller
from app.schemas.business_feedback import PetitionInput, PetitionNote
from app.services import business_feedback as service


router = APIRouter()


@router.get("/business-feedback")
def list_petitions(identity: Caller = Depends(caller)) -> list[dict]:
    return service.list_petitions(identity)


@router.post("/business-feedback", status_code=201)
def create_petition(body: PetitionInput, identity: Caller = Depends(caller)) -> dict:
    return service.create_petition(body, identity)


@router.get("/business-feedback/{petition_id}")
def get_petition(petition_id: str, identity: Caller = Depends(caller)) -> dict:
    return service.get_petition(petition_id, identity)


@router.post("/business-feedback/{petition_id}/review")
def review(petition_id: str, identity: Caller = Depends(caller)) -> dict:
    return service.transition(petition_id, identity, "review")


@router.post("/business-feedback/{petition_id}/request-info")
def request_info(petition_id: str, body: PetitionNote, identity: Caller = Depends(caller)) -> dict:
    return service.transition(petition_id, identity, "request_info", body.note)


@router.post("/business-feedback/{petition_id}/provide-info")
def provide_info(petition_id: str, body: PetitionNote, identity: Caller = Depends(caller)) -> dict:
    return service.transition(petition_id, identity, "provide_info", body.note)


@router.post("/business-feedback/{petition_id}/resolve")
def resolve(petition_id: str, body: PetitionNote, identity: Caller = Depends(caller)) -> dict:
    return service.transition(petition_id, identity, "resolve", body.note)


@router.post("/business-feedback/{petition_id}/reopen")
def reopen(petition_id: str, body: PetitionNote, identity: Caller = Depends(caller)) -> dict:
    return service.transition(petition_id, identity, "reopen", body.note)


@router.post("/business-feedback/{petition_id}/close")
def close(petition_id: str, identity: Caller = Depends(caller)) -> dict:
    return service.transition(petition_id, identity, "close")
