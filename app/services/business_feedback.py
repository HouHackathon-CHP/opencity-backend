# SPDX-License-Identifier: Apache-2.0
"""Business-petition lifecycle and role enforcement."""

from contextlib import closing
from datetime import datetime, timezone
from uuid import uuid4

from fastapi import HTTPException

from app.core.security import Caller, can_manage
from app.repositories import business_feedback as repo
from app.schemas.business_feedback import PetitionInput


def now() -> str:
    return datetime.now(timezone.utc).isoformat()


def owner_filter(identity: Caller) -> str | None:
    return None if can_manage(identity, "business_feedback") else identity.user


def view(connection, row) -> dict:
    return {**dict(row), "history": repo.events_for(connection, row["tenant"], row["id"])}


def list_petitions(identity: Caller) -> list[dict]:
    with closing(repo.petition_db()) as connection:
        return [view(connection, row) for row in repo.visible_petitions(
            connection, identity.tenant, owner_filter(identity))]


def get_petition(petition_id: str, identity: Caller) -> dict:
    with closing(repo.petition_db()) as connection:
        row = repo.petition_for(connection, identity.tenant, petition_id, owner_filter(identity))
        if row is None:
            raise HTTPException(status_code=404, detail="Business petition not found")
        return view(connection, row)


def add_event(connection, petition_id: str, identity: Caller, action: str,
              note: str | None, created_at: str) -> None:
    connection.execute("""
        INSERT INTO business_petition_events
          (id, petition_id, tenant, action, actor, note, created_at)
        VALUES (?, ?, ?, ?, ?, ?, ?)
    """, (str(uuid4()), petition_id, identity.tenant, action, identity.user, note, created_at))


def create_petition(body: PetitionInput, identity: Caller) -> dict:
    petition_id, created_at = str(uuid4()), now()
    with closing(repo.petition_db()) as connection:
        with connection:
            connection.execute("""
                INSERT INTO business_petitions
                  (id, tenant, user_id, company_name, tax_code, representative,
                   sector, title, description, requested_resolution, status,
                   created_at, updated_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'submitted', ?, ?)
            """, (petition_id, identity.tenant, identity.user, body.company_name,
                  body.tax_code, body.representative, body.sector, body.title,
                  body.description, body.requested_resolution, created_at, created_at))
            add_event(connection, petition_id, identity, "submitted", None, created_at)
        return view(connection, repo.petition_for(connection, identity.tenant, petition_id, None))


TRANSITIONS = {
    "review": ("submitted", "in_review", True, False),
    "request_info": ("in_review", "needs_info", True, True),
    "provide_info": ("needs_info", "in_review", False, True),
    "resolve": ("in_review", "resolved", True, True),
    "reopen": ("resolved", "in_review", False, True),
    "close": ("resolved", "closed", False, False),
}


def transition(petition_id: str, identity: Caller, action: str, note: str = "") -> dict:
    if action not in TRANSITIONS:
        raise HTTPException(status_code=404, detail="Unknown petition action")
    before, after, staff_action, needs_note = TRANSITIONS[action]
    if staff_action and not can_manage(identity, "business_feedback"):
        raise HTTPException(status_code=403, detail="business_feedback_operator role required")
    note = note.strip()
    if needs_note and len(note) < 10:
        raise HTTPException(status_code=422, detail="A substantive note is required")
    with closing(repo.petition_db()) as connection:
        with connection:
            connection.execute("BEGIN IMMEDIATE")
            owner = None if staff_action else identity.user
            row = repo.petition_for(connection, identity.tenant, petition_id, owner)
            if row is None:
                raise HTTPException(status_code=404, detail="Business petition not found")
            if row["status"] != before:
                raise HTTPException(status_code=409, detail=f"Petition must be {before} for {action}")
            updated_at = now()
            response = note if action == "resolve" else row["response"]
            connection.execute("""
                UPDATE business_petitions SET status = ?, response = ?, updated_at = ?
                WHERE tenant = ? AND id = ?
            """, (after, response, updated_at, identity.tenant, petition_id))
            add_event(connection, petition_id, identity, action, note or None, updated_at)
        return view(connection, repo.petition_for(connection, identity.tenant, petition_id, None))
