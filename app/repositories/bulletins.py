# SPDX-License-Identifier: Apache-2.0
import sqlite3
from pathlib import Path

from app.core import config


def bulletin_db() -> sqlite3.Connection:
    path = Path(config.NEWS_DB_PATH)
    path.parent.mkdir(parents=True, exist_ok=True)
    connection = sqlite3.connect(path, timeout=10)
    connection.row_factory = sqlite3.Row
    connection.execute("""
        CREATE TABLE IF NOT EXISTS bulletins (
            id TEXT PRIMARY KEY, tenant TEXT NOT NULL, category TEXT NOT NULL,
            title TEXT NOT NULL, summary TEXT NOT NULL, body TEXT NOT NULL,
            area TEXT, latitude REAL, longitude REAL,
            published_at TEXT NOT NULL, created_by TEXT NOT NULL
        )
    """)
    connection.execute(
        "CREATE INDEX IF NOT EXISTS bulletins_tenant_date ON bulletins(tenant, published_at DESC)"
    )
    return connection


def bulletin_view(row: sqlite3.Row) -> dict:
    return dict(row)
