# SPDX-License-Identifier: Apache-2.0
import sqlite3
from datetime import datetime, timedelta, timezone
from uuid import uuid4

from app import config
from app.security import Caller, can_dispatch


def add_notification(connection: sqlite3.Connection, tenant: str, report_id: str,
                     recipient_kind: str, recipient_id: str, kind: str, title: str,
                     body: str, *, dedupe_key: str | None = None) -> None:
    connection.execute("""
        INSERT OR IGNORE INTO notifications
          (id, tenant, report_id, recipient_kind, recipient_id, kind, title,
           body, created_at, dedupe_key)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, (str(uuid4()), tenant, report_id, recipient_kind, recipient_id,
          kind, title, body, datetime.now(timezone.utc).isoformat(), dedupe_key))


def materialize_deadline_notifications(connection: sqlite3.Connection, tenant: str) -> None:
    now = datetime.now(timezone.utc)
    rows = connection.execute("""
        SELECT a.report_id, a.unit_id, a.due_at, a.assigned_at
        FROM report_assignments a
        WHERE a.tenant = ? AND NOT EXISTS (
            SELECT 1 FROM report_events e WHERE e.tenant = a.tenant
              AND e.report_id = a.report_id AND e.action = 'resolved'
        )
    """, (tenant,)).fetchall()
    for row in rows:
        due_at = datetime.fromisoformat(row["due_at"].replace("Z", "+00:00"))
        if due_at.tzinfo is None:
            continue
        remaining = due_at - now
        if remaining > timedelta(days=1):
            continue
        kind = "overdue" if remaining <= timedelta(0) else "due_soon"
        title = "Hồ sơ quá hạn xử lý" if kind == "overdue" else "Hồ sơ sắp đến hạn"
        body = ("Hãy kiểm tra và xử lý hồ sơ quá hạn." if kind == "overdue"
                else "Hồ sơ còn dưới 24 giờ trước hạn xử lý.")
        for recipient_kind, recipient_id in (("unit", row["unit_id"]), ("dispatcher", "reports")):
            add_notification(connection, tenant, row["report_id"], recipient_kind,
                             recipient_id, kind, title, body,
                             dedupe_key=f"{tenant}:{kind}:{row['report_id']}:{row['assigned_at']}:{recipient_kind}")


def notification_scope(identity: "Caller") -> tuple[str, list[str]]:
    clauses = ["(n.recipient_kind = 'user' AND n.recipient_id = ?)"]
    params = [identity.user]
    if "reports_operator" in identity.roles and identity.unit in config.VALID_UNITS:
        clauses.append("""(n.recipient_kind = 'unit' AND n.recipient_id = ?
            AND EXISTS (SELECT 1 FROM report_assignments a
                WHERE a.tenant = n.tenant AND a.report_id = n.report_id
                  AND a.unit_id = n.recipient_id))""")
        params.append(identity.unit)
    if can_dispatch(identity):
        clauses.append("(n.recipient_kind = 'dispatcher' AND n.recipient_id = 'reports')")
    return " OR ".join(clauses), params


def notification_view(row: sqlite3.Row) -> dict:
    return {key: row[key] for key in ("id", "report_id", "kind", "title", "body", "created_at", "read_at")}
