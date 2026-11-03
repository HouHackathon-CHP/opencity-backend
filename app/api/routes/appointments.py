# SPDX-License-Identifier: Apache-2.0
"""HTTP endpoints for local citizen reception appointments."""

from fastapi import APIRouter, Depends

from app.core.security import Caller, caller, require_manager
from app.schemas.appointments import AppointmentInput, DecisionInput, SlotInput
from app.services import appointments


router = APIRouter()


@router.get("/appointments/slots")
def list_slots(identity: Caller = Depends(caller)) -> list[dict]:
    return appointments.list_slots(identity)


@router.post("/appointments/slots", status_code=201)
def create_slot(body: SlotInput, identity: Caller = Depends(caller)) -> dict:
    require_manager(identity, "appointments")
    return appointments.create_slot(body, identity)


@router.get("/appointments")
def list_appointments(identity: Caller = Depends(caller)) -> list[dict]:
    return appointments.list_appointments(identity)


@router.post("/appointments", status_code=201)
def request_appointment(body: AppointmentInput, identity: Caller = Depends(caller)) -> dict:
    return appointments.request_appointment(body, identity)


@router.post("/appointments/{appointment_id}/decision")
def decide_appointment(appointment_id: str, body: DecisionInput, identity: Caller = Depends(caller)) -> dict:
    require_manager(identity, "appointments")
    return appointments.decide_appointment(appointment_id, body, identity)


@router.post("/appointments/{appointment_id}/cancel")
def cancel_appointment(appointment_id: str, identity: Caller = Depends(caller)) -> dict:
    return appointments.cancel_appointment(appointment_id, identity)
