# SPDX-License-Identifier: Apache-2.0
from contextlib import closing
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException

from app.security import Caller, caller
from app.reports.storage import report_db
from app.notifications.service import (
    materialize_deadline_notifications, notification_scope, notification_view,
)

router = APIRouter()


@router.get("/notifications")
def list_notifications(identity: Caller = Depends(caller)) -> list[dict]:
    scope, params = notification_scope(identity)
    with closing(report_db()) as connection:
        with connection:
            materialize_deadline_notifications(connection, identity.tenant)
        rows = connection.execute(f"""
            SELECT n.*, r.read_at FROM notifications n
            LEFT JOIN notification_reads r ON r.notification_id = n.id AND r.user_id = ?
            WHERE n.tenant = ? AND ({scope})
            ORDER BY n.created_at DESC, n.rowid DESC LIMIT 100
        """, (identity.user, identity.tenant, *params)).fetchall()
    return [notification_view(row) for row in rows]


@router.post("/notifications/{notification_id}/read")
def read_notification(notification_id: str, identity: Caller = Depends(caller)) -> dict:
    scope, params = notification_scope(identity)
    with closing(report_db()) as connection:
        with connection:
            connection.execute("BEGIN IMMEDIATE")
            row = connection.execute(f"""
                SELECT n.id FROM notifications n
                WHERE n.id = ? AND n.tenant = ? AND ({scope})
            """, (notification_id, identity.tenant, *params)).fetchone()
            if row is None:
                raise HTTPException(status_code=404, detail="Notification not found")
            connection.execute("""
                INSERT OR IGNORE INTO notification_reads (notification_id, user_id, read_at)
                VALUES (?, ?, ?)
            """, (notification_id, identity.user, datetime.now(timezone.utc).isoformat()))
        read_at = connection.execute("""
            SELECT read_at FROM notification_reads WHERE notification_id = ? AND user_id = ?
        """, (notification_id, identity.user)).fetchone()["read_at"]
    return {"id": notification_id, "read_at": read_at}
