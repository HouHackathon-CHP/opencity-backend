# SPDX-License-Identifier: Apache-2.0
"""Citizen and operator endpoints for administrative-procedure feedback."""

from fastapi import APIRouter, Depends

from app.core.security import Caller, caller
from app.schemas.administrative_feedback import FeedbackInput, FeedbackNote
from app.services import administrative_feedback as service


router = APIRouter()


@router.get("/administrative-feedback")
def list_feedback(identity: Caller = Depends(caller)) -> list[dict]:
    return service.list_feedback(identity)


@router.post("/administrative-feedback", status_code=201)
def create_feedback(body: FeedbackInput, identity: Caller = Depends(caller)) -> dict:
    return service.create_feedback(body, identity)


@router.get("/administrative-feedback/{feedback_id}")
def get_feedback(feedback_id: str, identity: Caller = Depends(caller)) -> dict:
    return service.get_feedback(feedback_id, identity)


@router.post("/administrative-feedback/{feedback_id}/review")
def start_review(feedback_id: str, identity: Caller = Depends(caller)) -> dict:
    return service.transition(feedback_id, identity, "start_review")


@router.post("/administrative-feedback/{feedback_id}/answer")
def answer(feedback_id: str, body: FeedbackNote, identity: Caller = Depends(caller)) -> dict:
    return service.transition(feedback_id, identity, "answer", body.note)


@router.post("/administrative-feedback/{feedback_id}/clarification")
def ask_clarification(feedback_id: str, body: FeedbackNote, identity: Caller = Depends(caller)) -> dict:
    return service.transition(feedback_id, identity, "clarification", body.note)


@router.post("/administrative-feedback/{feedback_id}/close")
def close_feedback(feedback_id: str, identity: Caller = Depends(caller)) -> dict:
    return service.transition(feedback_id, identity, "close")
