# SPDX-License-Identifier: Apache-2.0
"""Tenant-scoped persistence and audit trail for procedure feedback."""

import sqlite3
from pathlib import Path

from app.core import config


def feedback_db() -> sqlite3.Connection:
    path = Path(config.ADMIN_FEEDBACK_DB_PATH)
    path.parent.mkdir(parents=True, exist_ok=True)
    connection = sqlite3.connect(path, timeout=10)
    connection.row_factory = sqlite3.Row
    connection.execute("PRAGMA foreign_keys = ON")
    connection.executescript("""
        CREATE TABLE IF NOT EXISTS administrative_feedback (
            id TEXT PRIMARY KEY, tenant TEXT NOT NULL, user_id TEXT NOT NULL,
            title TEXT NOT NULL, procedure TEXT NOT NULL, agency TEXT NOT NULL,
            issue_type TEXT NOT NULL, description TEXT NOT NULL,
            status TEXT NOT NULL, response TEXT,
            created_at TEXT NOT NULL, updated_at TEXT NOT NULL
        );
        CREATE INDEX IF NOT EXISTS administrative_feedback_scope
            ON administrative_feedback(tenant, user_id, created_at DESC);
        CREATE TABLE IF NOT EXISTS administrative_feedback_events (
            id TEXT PRIMARY KEY, feedback_id TEXT NOT NULL REFERENCES administrative_feedback(id),
            tenant TEXT NOT NULL, action TEXT NOT NULL, actor TEXT NOT NULL,
            note TEXT, created_at TEXT NOT NULL
        );
        CREATE INDEX IF NOT EXISTS administrative_feedback_events_case
            ON administrative_feedback_events(tenant, feedback_id, created_at);
    """)
    return connection


def feedback_for(connection: sqlite3.Connection, tenant: str, feedback_id: str,
                 owner: str | None) -> sqlite3.Row | None:
    clause = "tenant = ? AND id = ?" + (" AND user_id = ?" if owner is not None else "")
    params = (tenant, feedback_id) if owner is None else (tenant, feedback_id, owner)
    return connection.execute(f"SELECT * FROM administrative_feedback WHERE {clause}", params).fetchone()


def visible_feedback(connection: sqlite3.Connection, tenant: str, owner: str | None) -> list[sqlite3.Row]:
    clause = "tenant = ?" + (" AND user_id = ?" if owner is not None else "")
    params = (tenant,) if owner is None else (tenant, owner)
    return connection.execute(
        f"SELECT * FROM administrative_feedback WHERE {clause} ORDER BY created_at DESC, rowid DESC LIMIT 100",
        params,
    ).fetchall()


def events_for(connection: sqlite3.Connection, tenant: str, feedback_id: str) -> list[dict]:
    return [dict(row) for row in connection.execute(
        """SELECT action, actor, note, created_at FROM administrative_feedback_events
           WHERE tenant = ? AND feedback_id = ? ORDER BY created_at, rowid""",
        (tenant, feedback_id),
    ).fetchall()]
