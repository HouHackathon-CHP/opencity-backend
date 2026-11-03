# SPDX-License-Identifier: Apache-2.0
import sqlite3
from contextlib import closing
from datetime import datetime, timezone
from uuid import uuid4

from fastapi import APIRouter, Depends, HTTPException

from app.core.security import Caller, caller, require_manager
from app.schemas.surveys import SurveyInput, SurveyAnswer
from app.repositories.surveys import survey_db, survey_row, survey_view


router = APIRouter()


@router.get("/surveys")
def list_surveys(identity: Caller = Depends(caller)) -> list[dict]:
    with closing(survey_db()) as connection:
        rows = connection.execute("""
            SELECT s.id, s.title, s.description, s.status, s.created_at, s.closed_at,
                   a.option_id AS my_option_id
            FROM surveys s LEFT JOIN survey_answers a
              ON a.survey_id = s.id AND a.user_id = ?
            WHERE s.tenant = ? ORDER BY s.created_at DESC, s.rowid DESC LIMIT 100
        """, (identity.user, identity.tenant)).fetchall()
    return [dict(row) for row in rows]


@router.post("/surveys", status_code=201)
def create_survey(body: SurveyInput, identity: Caller = Depends(caller)) -> dict:
    require_manager(identity, "surveys")
    labels = [option.strip() for option in body.options]
    if (not body.title.strip() or not body.description.strip() or
            any(not label or len(label) > 120 for label in labels) or
            len({label.casefold() for label in labels}) != len(labels)):
        raise HTTPException(status_code=422, detail="Survey fields or options are invalid")
    survey_id = str(uuid4())
    now = datetime.now(timezone.utc).isoformat()
    with closing(survey_db()) as connection:
        with connection:
            connection.execute("""
                INSERT INTO surveys (id, tenant, title, description, status, created_at, created_by)
                VALUES (?, ?, ?, ?, 'open', ?, ?)
            """, (survey_id, identity.tenant, body.title.strip(), body.description.strip(), now, identity.user))
            connection.executemany(
                "INSERT INTO survey_options (id, survey_id, label, position) VALUES (?, ?, ?, ?)",
                [(str(uuid4()), survey_id, label, position) for position, label in enumerate(labels)],
            )
        return survey_view(connection, survey_row(connection, survey_id, identity), identity)


@router.get("/surveys/{survey_id}")
def get_survey(survey_id: str, identity: Caller = Depends(caller)) -> dict:
    with closing(survey_db()) as connection:
        return survey_view(connection, survey_row(connection, survey_id, identity), identity)


@router.post("/surveys/{survey_id}/answers")
def answer_survey(survey_id: str, body: SurveyAnswer, identity: Caller = Depends(caller)) -> dict:
    with closing(survey_db()) as connection:
        with connection:
            connection.execute("BEGIN IMMEDIATE")
            row = survey_row(connection, survey_id, identity)
            if row["status"] != "open":
                raise HTTPException(status_code=409, detail="Survey is closed")
            option = connection.execute(
                "SELECT id FROM survey_options WHERE id = ? AND survey_id = ?",
                (body.option_id, survey_id),
            ).fetchone()
            if option is None:
                raise HTTPException(status_code=422, detail="Option does not belong to survey")
            try:
                connection.execute(
                    "INSERT INTO survey_answers (survey_id, user_id, option_id, created_at) VALUES (?, ?, ?, ?)",
                    (survey_id, identity.user, option["id"], datetime.now(timezone.utc).isoformat()),
                )
            except sqlite3.IntegrityError as exc:
                raise HTTPException(status_code=409, detail="Survey already answered") from exc
        return survey_view(connection, row, identity)


@router.post("/surveys/{survey_id}/close")
def close_survey(survey_id: str, identity: Caller = Depends(caller)) -> dict:
    require_manager(identity, "surveys")
    with closing(survey_db()) as connection:
        with connection:
            connection.execute("BEGIN IMMEDIATE")
            row = survey_row(connection, survey_id, identity)
            if row["status"] == "open":
                connection.execute(
                    "UPDATE surveys SET status = 'closed', closed_at = ? WHERE id = ?",
                    (datetime.now(timezone.utc).isoformat(), survey_id),
                )
        return survey_view(connection, survey_row(connection, survey_id, identity), identity)
