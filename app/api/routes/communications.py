# SPDX-License-Identifier: Apache-2.0
"""Tenant-scoped public communication campaigns."""

from contextlib import closing
from datetime import datetime, timezone
from uuid import uuid4

from fastapi import APIRouter, Depends, HTTPException

from app.core.security import Caller, caller, require_manager
from app.repositories.bulletins import bulletin_db, bulletin_view
from app.schemas.communications import CommunicationInput


router = APIRouter()


@router.get("/communications")
def list_communications(identity: Caller = Depends(caller)) -> list[dict]:
    with closing(bulletin_db()) as connection:
        rows = connection.execute(
            "SELECT * FROM bulletins WHERE tenant = ? AND category = 'campaign' "
            "ORDER BY published_at DESC, rowid DESC LIMIT 100", (identity.tenant,),
        ).fetchall()
    return [bulletin_view(row) for row in rows]


@router.get("/communications/{communication_id}")
def get_communication(communication_id: str, identity: Caller = Depends(caller)) -> dict:
    with closing(bulletin_db()) as connection:
        row = connection.execute(
            "SELECT * FROM bulletins WHERE id = ? AND tenant = ? AND category = 'campaign'",
            (communication_id, identity.tenant),
        ).fetchone()
    if row is None:
        raise HTTPException(status_code=404, detail="Communication not found")
    return bulletin_view(row)


@router.post("/communications", status_code=201)
def publish_communication(body: CommunicationInput, identity: Caller = Depends(caller)) -> dict:
    require_manager(identity, "communications")
    title, summary, text = body.title.strip(), body.summary.strip(), body.body.strip()
    if len(title) < 5 or len(summary) < 10 or len(text) < 20:
        raise HTTPException(status_code=422, detail="Communication text is too short")
    values = (str(uuid4()), identity.tenant, "campaign", title, summary, text,
              body.area.strip() or None if body.area else None,
              datetime.now(timezone.utc).isoformat(), identity.user)
    with closing(bulletin_db()) as connection:
        with connection:
            connection.execute(
                "INSERT INTO bulletins (id, tenant, category, title, summary, body, area, "
                "latitude, longitude, published_at, created_by) "
                "VALUES (?, ?, ?, ?, ?, ?, ?, NULL, NULL, ?, ?)", values,
            )
        row = connection.execute("SELECT * FROM bulletins WHERE id = ?", (values[0],)).fetchone()
    return bulletin_view(row)
