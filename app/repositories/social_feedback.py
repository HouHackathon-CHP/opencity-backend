# SPDX-License-Identifier: Apache-2.0
"""Consultation topics and tenant-private citizen opinions."""

import sqlite3
from pathlib import Path

from app.core import config


def social_feedback_db() -> sqlite3.Connection:
    path = Path(config.SOCIAL_FEEDBACK_DB_PATH)
    path.parent.mkdir(parents=True, exist_ok=True)
    connection = sqlite3.connect(path, timeout=10)
    connection.row_factory = sqlite3.Row
    connection.execute("PRAGMA foreign_keys = ON")
    connection.executescript("""
        CREATE TABLE IF NOT EXISTS consultation_topics (
            id TEXT PRIMARY KEY, tenant TEXT NOT NULL, title TEXT NOT NULL,
            description TEXT NOT NULL, area TEXT, status TEXT NOT NULL,
            created_by TEXT NOT NULL, created_at TEXT NOT NULL, closed_at TEXT
        );
        CREATE INDEX IF NOT EXISTS consultation_scope ON consultation_topics(tenant, created_at DESC);
        CREATE TABLE IF NOT EXISTS consultation_opinions (
            id TEXT PRIMARY KEY, topic_id TEXT NOT NULL REFERENCES consultation_topics(id),
            tenant TEXT NOT NULL, user_id TEXT NOT NULL, body TEXT NOT NULL,
            created_at TEXT NOT NULL, updated_at TEXT NOT NULL,
            UNIQUE(topic_id, user_id)
        );
        CREATE INDEX IF NOT EXISTS consultation_opinions_scope ON consultation_opinions(tenant, topic_id);
    """)
    return connection
