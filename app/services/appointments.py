# SPDX-License-Identifier: Apache-2.0
"""Rules and transactions for the local citizen reception appointment module."""

import sqlite3
from contextlib import closing
from datetime import datetime, timedelta, timezone
from uuid import uuid4

from fastapi import HTTPException

from app.core.security import Caller, can_manage
from app.repositories import appointments as repo
from app.schemas.appointments import AppointmentInput, DecisionInput, SlotInput


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _slot_view(row: sqlite3.Row) -> dict:
    result = dict(row)
    result["remaining_capacity"] = result["capacity"] - result["confirmed_count"]
    return result


def list_slots(identity: Caller) -> list[dict]:
    with closing(repo.appointment_db()) as connection:
        rows = repo.upcoming_slots(connection, identity.tenant, _now().isoformat())
    return [_slot_view(row) for row in rows]


def create_slot(body: SlotInput, identity: Caller) -> dict:
    if body.starts_at.tzinfo is None or body.ends_at.tzinfo is None:
        raise HTTPException(status_code=422, detail="Appointment times need a timezone")
    start = body.starts_at.astimezone(timezone.utc)
    end = body.ends_at.astimezone(timezone.utc)
    if start <= _now() or start > _now() + timedelta(days=90) or not timedelta(minutes=15) <= end - start <= timedelta(hours=4):
        raise HTTPException(status_code=422, detail="Choose a future slot within 90 days lasting 15 minutes to 4 hours")
    location = body.location.strip()
    if len(location) < 3:
        raise HTTPException(status_code=422, detail="Location is required")
    slot_id = str(uuid4())
    with closing(repo.appointment_db()) as connection:
        with connection:
            repo.insert_slot(connection,
                (slot_id, identity.tenant, start.isoformat(), end.isoformat(), location,
                 body.capacity, _now().isoformat(), identity.user),
            )
        return _slot_view(repo.slot_for(connection, identity.tenant, slot_id))


def list_appointments(identity: Caller) -> list[dict]:
    with closing(repo.appointment_db()) as connection:
        user_id = None if can_manage(identity, "appointments") else identity.user
        rows = repo.visible_appointments(connection, identity.tenant, user_id)
    return [dict(row) for row in rows]


def request_appointment(body: AppointmentInput, identity: Caller) -> dict:
    reason = body.reason.strip()
    if len(reason) < 10:
        raise HTTPException(status_code=422, detail="Appointment reason is too short")
    appointment_id = str(uuid4())
    with closing(repo.appointment_db()) as connection:
        with connection:
            repo.begin_write(connection)
            slot = repo.slot_for(connection, identity.tenant, body.slot_id)
            if slot is None:
                raise HTTPException(status_code=404, detail="Appointment slot not found")
            if slot["starts_at"] <= _now().isoformat():
                raise HTTPException(status_code=409, detail="Appointment slot has passed")
            if slot["confirmed_count"] >= slot["capacity"]:
                raise HTTPException(status_code=409, detail="Appointment slot is full")
            try:
                repo.insert_appointment(connection,
                    (appointment_id, identity.tenant, body.slot_id, identity.user, reason, _now().isoformat()),
                )
            except sqlite3.IntegrityError as exc:
                raise HTTPException(status_code=409, detail="You already requested this slot") from exc
        return dict(repo.appointment_for(connection, identity.tenant, appointment_id))


def decide_appointment(appointment_id: str, body: DecisionInput, identity: Caller) -> dict:
    note = body.note.strip()
    if body.decision == "rejected" and len(note) < 3:
        raise HTTPException(status_code=422, detail="A rejection reason is required")
    with closing(repo.appointment_db()) as connection:
        with connection:
            repo.begin_write(connection)
            appointment = repo.appointment_for(connection, identity.tenant, appointment_id)
            if appointment is None:
                raise HTTPException(status_code=404, detail="Appointment not found")
            if appointment["status"] != "pending":
                raise HTTPException(status_code=409, detail="Appointment has already been processed")
            if appointment["starts_at"] <= _now().isoformat():
                raise HTTPException(status_code=409, detail="Appointment slot has passed")
            if body.decision == "confirmed":
                slot = repo.slot_for(connection, identity.tenant, appointment["slot_id"])
                if slot["confirmed_count"] >= slot["capacity"]:
                    raise HTTPException(status_code=409, detail="Appointment slot is full")
            repo.save_decision(connection, identity.tenant, appointment_id,
                               body.decision, _now().isoformat(), identity.user, note or None)
        return dict(repo.appointment_for(connection, identity.tenant, appointment_id))


def cancel_appointment(appointment_id: str, identity: Caller) -> dict:
    with closing(repo.appointment_db()) as connection:
        with connection:
            repo.begin_write(connection)
            appointment = repo.appointment_for(connection, identity.tenant, appointment_id)
            if appointment is None or appointment["user_id"] != identity.user:
                raise HTTPException(status_code=404, detail="Appointment not found")
            if appointment["status"] not in {"pending", "confirmed"}:
                raise HTTPException(status_code=409, detail="Appointment cannot be cancelled")
            if appointment["starts_at"] <= _now().isoformat():
                raise HTTPException(status_code=409, detail="Appointment slot has passed")
            repo.save_cancellation(connection, identity.tenant, appointment_id, _now().isoformat())
        return dict(repo.appointment_for(connection, identity.tenant, appointment_id))
