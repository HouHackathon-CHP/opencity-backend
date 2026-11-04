# SPDX-License-Identifier: Apache-2.0
"""Procedure-feedback workflow with a separate operator role."""

from contextlib import closing
from datetime import datetime, timezone
from uuid import uuid4

from fastapi import HTTPException

from app.core.security import Caller, can_manage
from app.repositories import administrative_feedback as repo
from app.schemas.administrative_feedback import FeedbackInput


def now() -> str:
    return datetime.now(timezone.utc).isoformat()


def owner_filter(identity: Caller) -> str | None:
    return None if can_manage(identity, "administrative_feedback") else identity.user


def view(connection, row) -> dict:
    return {**dict(row), "history": repo.events_for(connection, row["tenant"], row["id"])}


def list_feedback(identity: Caller) -> list[dict]:
    with closing(repo.feedback_db()) as connection:
        return [view(connection, row) for row in repo.visible_feedback(
            connection, identity.tenant, owner_filter(identity))]


def get_feedback(feedback_id: str, identity: Caller) -> dict:
    with closing(repo.feedback_db()) as connection:
        row = repo.feedback_for(connection, identity.tenant, feedback_id, owner_filter(identity))
        if row is None:
            raise HTTPException(status_code=404, detail="Administrative feedback not found")
        return view(connection, row)


def create_feedback(body: FeedbackInput, identity: Caller) -> dict:
    values = {name: getattr(body, name).strip() for name in
              ("title", "procedure", "agency", "description")}
    if any(len(values[name]) < minimum for name, minimum in
           (("title", 5), ("procedure", 3), ("agency", 3), ("description", 20))):
        raise HTTPException(status_code=422, detail="Feedback fields cannot be blank")
    feedback_id, created_at = str(uuid4()), now()
    with closing(repo.feedback_db()) as connection:
        with connection:
            connection.execute("""
                INSERT INTO administrative_feedback
                  (id, tenant, user_id, title, procedure, agency, issue_type,
                   description, status, created_at, updated_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, 'submitted', ?, ?)
            """, (feedback_id, identity.tenant, identity.user, values["title"],
                  values["procedure"], values["agency"], body.issue_type,
                  values["description"], created_at, created_at))
            event(connection, feedback_id, identity, "submitted", None, created_at)
        return view(connection, repo.feedback_for(connection, identity.tenant, feedback_id, None))


def event(connection, feedback_id: str, identity: Caller, action: str,
          note: str | None, created_at: str) -> None:
    connection.execute("""
        INSERT INTO administrative_feedback_events
          (id, feedback_id, tenant, action, actor, note, created_at)
        VALUES (?, ?, ?, ?, ?, ?, ?)
    """, (str(uuid4()), feedback_id, identity.tenant, action, identity.user, note, created_at))


def transition(feedback_id: str, identity: Caller, action: str, note: str = "") -> dict:
    operator = can_manage(identity, "administrative_feedback")
    if action in {"start_review", "answer"} and not operator:
        raise HTTPException(status_code=403, detail="administrative_feedback_operator role required")
    note = note.strip()
    if action in {"answer", "clarification"} and len(note) < 10:
        raise HTTPException(status_code=422, detail="A substantive note is required")
    allowed = {
        "start_review": ("submitted", "in_review"),
        "answer": ("in_review", "answered"),
        "clarification": ("answered", "in_review"),
        "close": ("answered", "closed"),
    }
    if action not in allowed:
        raise HTTPException(status_code=404, detail="Unknown feedback action")
    with closing(repo.feedback_db()) as connection:
        with connection:
            connection.execute("BEGIN IMMEDIATE")
            # Citizens may clarify or close their own case; staff may only review and answer.
            owner = None if action in {"start_review", "answer"} else identity.user
            row = repo.feedback_for(connection, identity.tenant, feedback_id, owner)
            if row is None:
                raise HTTPException(status_code=404, detail="Administrative feedback not found")
            before, after = allowed[action]
            if row["status"] != before:
                raise HTTPException(status_code=409, detail=f"Feedback must be {before} for {action}")
            updated_at = now()
            response = note if action == "answer" else row["response"]
            connection.execute("""
                UPDATE administrative_feedback SET status = ?, response = ?, updated_at = ?
                WHERE tenant = ? AND id = ?
            """, (after, response, updated_at, identity.tenant, feedback_id))
            event(connection, feedback_id, identity, action, note or None, updated_at)
        return view(connection, repo.feedback_for(connection, identity.tenant, feedback_id, None))
