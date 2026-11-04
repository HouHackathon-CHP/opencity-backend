# SPDX-License-Identifier: Apache-2.0
"""Tenant-scoped contact directory persistence."""

import sqlite3
from pathlib import Path

from app.core import config


def hotline_db() -> sqlite3.Connection:
    path = Path(config.HOTLINES_DB_PATH)
    path.parent.mkdir(parents=True, exist_ok=True)
    connection = sqlite3.connect(path, timeout=10)
    connection.row_factory = sqlite3.Row
    connection.executescript("""
        CREATE TABLE IF NOT EXISTS hotlines (
            id TEXT PRIMARY KEY, tenant TEXT NOT NULL, name TEXT NOT NULL,
            unit TEXT NOT NULL, phone TEXT NOT NULL, area TEXT NOT NULL,
            hours TEXT NOT NULL, description TEXT NOT NULL,
            active INTEGER NOT NULL, created_by TEXT NOT NULL,
            created_at TEXT NOT NULL, updated_at TEXT NOT NULL
        );
        CREATE INDEX IF NOT EXISTS hotlines_tenant_active_name
            ON hotlines(tenant, active, name);
    """)
    return connection


def hotline_for(connection: sqlite3.Connection, tenant: str, hotline_id: str) -> sqlite3.Row | None:
    return connection.execute(
        "SELECT * FROM hotlines WHERE tenant = ? AND id = ?", (tenant, hotline_id)
    ).fetchone()
