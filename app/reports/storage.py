# SPDX-License-Identifier: Apache-2.0
import sqlite3
from contextlib import closing
from datetime import datetime, timezone
from pathlib import Path
from uuid import uuid4

from app import config
from app.security import Caller


def report_db() -> sqlite3.Connection:
    path = Path(config.REPORT_DB_PATH)
    path.parent.mkdir(parents=True, exist_ok=True)
    connection = sqlite3.connect(path, timeout=10)
    connection.row_factory = sqlite3.Row
    connection.executescript("""
        CREATE TABLE IF NOT EXISTS report_assignments (
            report_id TEXT PRIMARY KEY, tenant TEXT NOT NULL, unit_id TEXT NOT NULL,
            due_at TEXT NOT NULL, assigned_at TEXT NOT NULL, assigned_by TEXT NOT NULL,
            accepted_at TEXT, accepted_by TEXT, pending_unit TEXT,
            pending_reason TEXT, requested_at TEXT, requested_by TEXT
        );
        CREATE INDEX IF NOT EXISTS report_assignments_tenant_unit
            ON report_assignments(tenant, unit_id);
        CREATE TABLE IF NOT EXISTS report_events (
            id TEXT PRIMARY KEY, report_id TEXT NOT NULL, tenant TEXT NOT NULL,
            action TEXT NOT NULL, actor TEXT NOT NULL, from_unit TEXT,
            to_unit TEXT, note TEXT, created_at TEXT NOT NULL
        );
        CREATE INDEX IF NOT EXISTS report_events_tenant_report
            ON report_events(tenant, report_id, created_at);
        CREATE TABLE IF NOT EXISTS notifications (
            id TEXT PRIMARY KEY, tenant TEXT NOT NULL, report_id TEXT NOT NULL,
            recipient_kind TEXT NOT NULL, recipient_id TEXT NOT NULL,
            kind TEXT NOT NULL, title TEXT NOT NULL, body TEXT NOT NULL,
            created_at TEXT NOT NULL, dedupe_key TEXT UNIQUE
        );
        CREATE INDEX IF NOT EXISTS notifications_recipient
            ON notifications(tenant, recipient_kind, recipient_id, created_at DESC);
        CREATE TABLE IF NOT EXISTS notification_reads (
            notification_id TEXT NOT NULL REFERENCES notifications(id),
            user_id TEXT NOT NULL, read_at TEXT NOT NULL,
            PRIMARY KEY(notification_id, user_id)
        );
    """)
    return connection


def routing_map(tenant: str) -> dict[str, dict]:
    with closing(report_db()) as connection:
        rows = connection.execute(
            "SELECT * FROM report_assignments WHERE tenant = ?", (tenant,)
        ).fetchall()
        events = connection.execute(
            "SELECT * FROM report_events WHERE tenant = ? ORDER BY created_at, rowid", (tenant,)
        ).fetchall()
    result = {row["report_id"]: {**dict(row), "events": []} for row in rows}
    for event in events:
        if event["report_id"] in result:
            result[event["report_id"]]["events"].append(dict(event))
    return result


def routing_for(report_id: str, tenant: str) -> dict | None:
    return routing_map(tenant).get(report_id)


def add_report_event(connection: sqlite3.Connection, report_id: str, identity: "Caller",
                     action: str, *, from_unit: str | None = None,
                     to_unit: str | None = None, note: str | None = None) -> None:
    connection.execute(
        """INSERT INTO report_events
           (id, report_id, tenant, action, actor, from_unit, to_unit, note, created_at)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
        (str(uuid4()), report_id, identity.tenant, action, identity.user,
         from_unit, to_unit, note, datetime.now(timezone.utc).isoformat()),
    )
