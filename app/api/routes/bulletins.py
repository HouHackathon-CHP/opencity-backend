# SPDX-License-Identifier: Apache-2.0
from contextlib import closing
from datetime import datetime, timezone
from uuid import uuid4

from fastapi import APIRouter, Depends, HTTPException

from app.core.security import Caller, caller, require_manager
from app.schemas.bulletins import BulletinInput
from app.repositories.bulletins import bulletin_db, bulletin_view


router = APIRouter()


@router.get("/bulletins")
def list_bulletins(identity: Caller = Depends(caller)) -> list[dict]:
    with closing(bulletin_db()) as connection:
        rows = connection.execute(
            "SELECT * FROM bulletins WHERE tenant = ? AND category IN ('news', 'alert') ORDER BY published_at DESC, rowid DESC LIMIT 100",
            (identity.tenant,),
        ).fetchall()
    return [bulletin_view(row) for row in rows]


@router.get("/bulletins/{bulletin_id}")
def get_bulletin(bulletin_id: str, identity: Caller = Depends(caller)) -> dict:
    with closing(bulletin_db()) as connection:
        row = connection.execute(
            "SELECT * FROM bulletins WHERE id = ? AND tenant = ? AND category IN ('news', 'alert')", (bulletin_id, identity.tenant)
        ).fetchone()
    if row is None:
        raise HTTPException(status_code=404, detail="Bulletin not found")
    return bulletin_view(row)


@router.post("/bulletins", status_code=201)
def publish_bulletin(body: BulletinInput, identity: Caller = Depends(caller)) -> dict:
    require_manager(identity, "bulletins")
    if (body.latitude is None) != (body.longitude is None):
        raise HTTPException(status_code=422, detail="Latitude and longitude must be provided together")
    if not body.title.strip() or not body.summary.strip() or not body.body.strip():
        raise HTTPException(status_code=422, detail="Bulletin text cannot be empty")
    values = (
        str(uuid4()), identity.tenant, body.category, body.title.strip(), body.summary.strip(),
        body.body.strip(), body.area.strip() if body.area else None, body.latitude, body.longitude,
        datetime.now(timezone.utc).isoformat(), identity.user,
    )
    with closing(bulletin_db()) as connection:
        with connection:
            connection.execute(
                """INSERT INTO bulletins
                   (id, tenant, category, title, summary, body, area, latitude, longitude, published_at, created_by)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                values,
            )
        row = connection.execute("SELECT * FROM bulletins WHERE id = ?", (values[0],)).fetchone()
    return bulletin_view(row)
