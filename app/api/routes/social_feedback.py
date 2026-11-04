# SPDX-License-Identifier: Apache-2.0
"""Operator-led public consultations with one editable opinion per citizen."""

from contextlib import closing
from datetime import datetime, timezone
from uuid import uuid4

from fastapi import APIRouter, Depends, HTTPException

from app.core.security import Caller, caller, require_manager
from app.repositories.social_feedback import social_feedback_db
from app.schemas.social_feedback import OpinionInput, TopicInput


router = APIRouter(prefix="/social-feedback/topics")


def now() -> str:
    return datetime.now(timezone.utc).isoformat()


def topic_for(connection, tenant: str, topic_id: str):
    row = connection.execute("SELECT * FROM consultation_topics WHERE id = ? AND tenant = ?",
                             (topic_id, tenant)).fetchone()
    if row is None:
        raise HTTPException(status_code=404, detail="Topic not found")
    return row


def view(connection, row, identity: Caller) -> dict:
    count = connection.execute("SELECT COUNT(*) FROM consultation_opinions WHERE tenant = ? AND topic_id = ?",
                               (identity.tenant, row["id"])).fetchone()[0]
    mine = connection.execute("SELECT body, updated_at FROM consultation_opinions "
                              "WHERE tenant = ? AND topic_id = ? AND user_id = ?",
                              (identity.tenant, row["id"], identity.user)).fetchone()
    return {**dict(row), "opinion_count": count,
            "my_opinion": dict(mine) if mine is not None else None}


@router.get("")
def list_topics(identity: Caller = Depends(caller)) -> list[dict]:
    with closing(social_feedback_db()) as connection:
        rows = connection.execute("SELECT * FROM consultation_topics WHERE tenant = ? "
                                  "ORDER BY created_at DESC, rowid DESC LIMIT 100",
                                  (identity.tenant,)).fetchall()
        return [view(connection, row, identity) for row in rows]


@router.post("", status_code=201)
def create_topic(body: TopicInput, identity: Caller = Depends(caller)) -> dict:
    require_manager(identity, "social_feedback")
    title, description = body.title.strip(), body.description.strip()
    if len(title) < 5 or len(description) < 20:
        raise HTTPException(status_code=422, detail="Topic text is too short")
    values = (str(uuid4()), identity.tenant, title, description,
              body.area.strip() or None if body.area else None, "open", identity.user, now())
    with closing(social_feedback_db()) as connection:
        with connection:
            connection.execute("INSERT INTO consultation_topics "
                               "(id, tenant, title, description, area, status, created_by, created_at, closed_at) "
                               "VALUES (?, ?, ?, ?, ?, ?, ?, ?, NULL)", values)
        return view(connection, topic_for(connection, identity.tenant, values[0]), identity)


@router.post("/{topic_id}/close")
def close_topic(topic_id: str, identity: Caller = Depends(caller)) -> dict:
    require_manager(identity, "social_feedback")
    with closing(social_feedback_db()) as connection:
        with connection:
            topic_for(connection, identity.tenant, topic_id)
            connection.execute("UPDATE consultation_topics SET status = 'closed', closed_at = ? "
                               "WHERE id = ? AND tenant = ? AND status = 'open'", (now(), topic_id, identity.tenant))
        return view(connection, topic_for(connection, identity.tenant, topic_id), identity)


@router.put("/{topic_id}/opinion")
def save_opinion(topic_id: str, body: OpinionInput, identity: Caller = Depends(caller)) -> dict:
    content = body.body.strip()
    if len(content) < 10:
        raise HTTPException(status_code=422, detail="Opinion text is too short")
    with closing(social_feedback_db()) as connection:
        with connection:
            topic = topic_for(connection, identity.tenant, topic_id)
            if topic["status"] != "open":
                raise HTTPException(status_code=409, detail="Topic is closed")
            timestamp = now()
            connection.execute("INSERT INTO consultation_opinions "
                               "(id, topic_id, tenant, user_id, body, created_at, updated_at) "
                               "VALUES (?, ?, ?, ?, ?, ?, ?) "
                               "ON CONFLICT(topic_id, user_id) DO UPDATE SET body = excluded.body, "
                               "updated_at = excluded.updated_at",
                               (str(uuid4()), topic_id, identity.tenant, identity.user, content, timestamp, timestamp))
        row = connection.execute("SELECT id, topic_id, user_id, body, created_at, updated_at "
                                 "FROM consultation_opinions WHERE tenant = ? AND topic_id = ? AND user_id = ?",
                                 (identity.tenant, topic_id, identity.user)).fetchone()
        return dict(row)


@router.get("/{topic_id}/opinions")
def list_opinions(topic_id: str, identity: Caller = Depends(caller)) -> list[dict]:
    require_manager(identity, "social_feedback")
    with closing(social_feedback_db()) as connection:
        topic_for(connection, identity.tenant, topic_id)
        rows = connection.execute("SELECT id, topic_id, user_id, body, created_at, updated_at "
                                  "FROM consultation_opinions WHERE tenant = ? AND topic_id = ? "
                                  "ORDER BY created_at DESC, rowid DESC LIMIT 200",
                                  (identity.tenant, topic_id)).fetchall()
        return [dict(row) for row in rows]
