# SPDX-License-Identifier: Apache-2.0
"""Tenant-scoped local petition storage and event history."""

import sqlite3
from pathlib import Path

from app.core import config


def petition_db() -> sqlite3.Connection:
    path = Path(config.BUSINESS_FEEDBACK_DB_PATH)
    path.parent.mkdir(parents=True, exist_ok=True)
    connection = sqlite3.connect(path, timeout=10)
    connection.row_factory = sqlite3.Row
    connection.execute("PRAGMA foreign_keys = ON")
    connection.executescript("""
        CREATE TABLE IF NOT EXISTS business_petitions (
            id TEXT PRIMARY KEY, tenant TEXT NOT NULL, user_id TEXT NOT NULL,
            company_name TEXT NOT NULL, tax_code TEXT NOT NULL,
            representative TEXT NOT NULL, sector TEXT NOT NULL,
            title TEXT NOT NULL, description TEXT NOT NULL,
            requested_resolution TEXT NOT NULL, status TEXT NOT NULL,
            response TEXT, created_at TEXT NOT NULL, updated_at TEXT NOT NULL
        );
        CREATE INDEX IF NOT EXISTS business_petitions_scope
            ON business_petitions(tenant, user_id, created_at DESC);
        CREATE TABLE IF NOT EXISTS business_petition_events (
            id TEXT PRIMARY KEY,
            petition_id TEXT NOT NULL REFERENCES business_petitions(id),
            tenant TEXT NOT NULL, action TEXT NOT NULL,
            actor TEXT NOT NULL, note TEXT, created_at TEXT NOT NULL
        );
        CREATE INDEX IF NOT EXISTS business_petition_events_case
            ON business_petition_events(tenant, petition_id, created_at);
    """)
    return connection


def petition_for(connection: sqlite3.Connection, tenant: str, petition_id: str,
                 owner: str | None) -> sqlite3.Row | None:
    clause = "tenant = ? AND id = ?" + (" AND user_id = ?" if owner is not None else "")
    params = (tenant, petition_id) if owner is None else (tenant, petition_id, owner)
    return connection.execute(f"SELECT * FROM business_petitions WHERE {clause}", params).fetchone()


def visible_petitions(connection: sqlite3.Connection, tenant: str,
                      owner: str | None) -> list[sqlite3.Row]:
    clause = "tenant = ?" + (" AND user_id = ?" if owner is not None else "")
    params = (tenant,) if owner is None else (tenant, owner)
    return connection.execute(
        f"SELECT * FROM business_petitions WHERE {clause} ORDER BY created_at DESC, rowid DESC LIMIT 100",
        params,
    ).fetchall()


def events_for(connection: sqlite3.Connection, tenant: str, petition_id: str) -> list[dict]:
    return [dict(row) for row in connection.execute(
        """SELECT action, actor, note, created_at FROM business_petition_events
           WHERE tenant = ? AND petition_id = ? ORDER BY created_at, rowid""",
        (tenant, petition_id),
    ).fetchall()]
