# SPDX-License-Identifier: Apache-2.0
"""SQLite storage for tenant-local community groups and membership."""

import sqlite3
from pathlib import Path

from app.core import config


def community_db() -> sqlite3.Connection:
    path = Path(config.COMMUNITY_DB_PATH)
    path.parent.mkdir(parents=True, exist_ok=True)
    connection = sqlite3.connect(path, timeout=10)
    connection.row_factory = sqlite3.Row
    connection.execute("PRAGMA foreign_keys = ON")
    connection.executescript("""
        CREATE TABLE IF NOT EXISTS community_groups (
            id TEXT PRIMARY KEY, tenant TEXT NOT NULL, title TEXT NOT NULL,
            description TEXT NOT NULL, area TEXT, created_by TEXT NOT NULL,
            created_at TEXT NOT NULL
        );
        CREATE INDEX IF NOT EXISTS community_groups_scope ON community_groups(tenant, created_at DESC);
        CREATE TABLE IF NOT EXISTS community_members (
            group_id TEXT NOT NULL REFERENCES community_groups(id), tenant TEXT NOT NULL,
            user_id TEXT NOT NULL, joined_at TEXT NOT NULL,
            PRIMARY KEY(group_id, user_id)
        );
        CREATE TABLE IF NOT EXISTS community_posts (
            id TEXT PRIMARY KEY, group_id TEXT NOT NULL REFERENCES community_groups(id),
            tenant TEXT NOT NULL, user_id TEXT NOT NULL, body TEXT NOT NULL,
            created_at TEXT NOT NULL
        );
        CREATE INDEX IF NOT EXISTS community_posts_group ON community_posts(tenant, group_id, created_at DESC);
    """)
    return connection
