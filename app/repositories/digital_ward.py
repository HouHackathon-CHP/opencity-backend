# SPDX-License-Identifier: Apache-2.0
"""Tenant-scoped ward service profiles."""

import sqlite3
from pathlib import Path

from app.core import config


def ward_db() -> sqlite3.Connection:
    path = Path(config.DIGITAL_WARD_DB_PATH)
    path.parent.mkdir(parents=True, exist_ok=True)
    connection = sqlite3.connect(path, timeout=10)
    connection.row_factory = sqlite3.Row
    connection.execute("""
        CREATE TABLE IF NOT EXISTS digital_wards (
            id TEXT PRIMARY KEY, tenant TEXT NOT NULL, code TEXT NOT NULL,
            name TEXT NOT NULL, address TEXT NOT NULL, phone TEXT NOT NULL,
            office_hours TEXT NOT NULL, description TEXT NOT NULL,
            latitude REAL, longitude REAL, active INTEGER NOT NULL,
            updated_at TEXT NOT NULL, updated_by TEXT NOT NULL,
            UNIQUE(tenant, code)
        )
    """)
    connection.execute("CREATE INDEX IF NOT EXISTS digital_wards_scope ON digital_wards(tenant, name)")
    return connection
