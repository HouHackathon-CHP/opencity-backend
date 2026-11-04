# SPDX-License-Identifier: Apache-2.0
"""Public hotline directory and operator updates."""

from contextlib import closing
from datetime import datetime, timezone
from uuid import uuid4

from fastapi import HTTPException

from app.core.security import Caller, can_manage, require_manager
from app.repositories.hotlines import hotline_db, hotline_for
from app.schemas.hotlines import HotlineInput


def now() -> str:
    return datetime.now(timezone.utc).isoformat()


def view(row) -> dict:
    return {key: row[key] for key in ("id", "name", "unit", "phone", "area", "hours", "description", "updated_at")} | {"active": bool(row["active"])}


def list_hotlines(identity: Caller) -> list[dict]:
    operator = can_manage(identity, "hotlines")
    with closing(hotline_db()) as connection:
        rows = connection.execute(
            "SELECT * FROM hotlines WHERE tenant = ? " + ("" if operator else "AND active = 1 ") +
            "ORDER BY name COLLATE NOCASE, id LIMIT 200", (identity.tenant,),
        ).fetchall()
    return [view(row) for row in rows]


def save_hotline(body: HotlineInput, identity: Caller, hotline_id: str | None = None) -> dict:
    require_manager(identity, "hotlines")
    timestamp = now()
    with closing(hotline_db()) as connection:
        with connection:
            if hotline_id is None:
                hotline_id = str(uuid4())
                connection.execute("""
                    INSERT INTO hotlines
                      (id, tenant, name, unit, phone, area, hours, description,
                       active, created_by, created_at, updated_at)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (hotline_id, identity.tenant, body.name, body.unit, body.phone,
                      body.area, body.hours, body.description, int(body.active),
                      identity.user, timestamp, timestamp))
            else:
                result = connection.execute("""
                    UPDATE hotlines SET name = ?, unit = ?, phone = ?, area = ?,
                        hours = ?, description = ?, active = ?, updated_at = ?
                    WHERE tenant = ? AND id = ?
                """, (body.name, body.unit, body.phone, body.area, body.hours,
                      body.description, int(body.active), timestamp, identity.tenant,
                      hotline_id))
                if result.rowcount == 0:
                    raise HTTPException(status_code=404, detail="Hotline not found")
        return view(hotline_for(connection, identity.tenant, hotline_id))
