# SPDX-License-Identifier: Apache-2.0
import sqlite3
from pathlib import Path

from fastapi import HTTPException

from app import config
from app.security import Caller, can_manage


def survey_db() -> sqlite3.Connection:
    path = Path(config.SURVEY_DB_PATH)
    path.parent.mkdir(parents=True, exist_ok=True)
    connection = sqlite3.connect(path, timeout=10)
    connection.row_factory = sqlite3.Row
    connection.execute("PRAGMA foreign_keys = ON")
    connection.executescript("""
        CREATE TABLE IF NOT EXISTS surveys (
            id TEXT PRIMARY KEY, tenant TEXT NOT NULL, title TEXT NOT NULL,
            description TEXT NOT NULL, status TEXT NOT NULL,
            created_at TEXT NOT NULL, closed_at TEXT, created_by TEXT NOT NULL
        );
        CREATE INDEX IF NOT EXISTS surveys_tenant_date ON surveys(tenant, created_at DESC);
        CREATE TABLE IF NOT EXISTS survey_options (
            id TEXT PRIMARY KEY, survey_id TEXT NOT NULL REFERENCES surveys(id),
            label TEXT NOT NULL, position INTEGER NOT NULL,
            UNIQUE(survey_id, position)
        );
        CREATE TABLE IF NOT EXISTS survey_answers (
            survey_id TEXT NOT NULL REFERENCES surveys(id),
            user_id TEXT NOT NULL, option_id TEXT NOT NULL REFERENCES survey_options(id),
            created_at TEXT NOT NULL, PRIMARY KEY(survey_id, user_id)
        );
    """)
    return connection


def survey_row(connection: sqlite3.Connection, survey_id: str, identity: "Caller") -> sqlite3.Row:
    row = connection.execute(
        "SELECT * FROM surveys WHERE id = ? AND tenant = ?", (survey_id, identity.tenant)
    ).fetchone()
    if row is None:
        raise HTTPException(status_code=404, detail="Survey not found")
    return row


def survey_view(connection: sqlite3.Connection, row: sqlite3.Row, identity: "Caller") -> dict:
    answer = connection.execute(
        "SELECT option_id FROM survey_answers WHERE survey_id = ? AND user_id = ?",
        (row["id"], identity.user),
    ).fetchone()
    my_option_id = answer["option_id"] if answer else None
    show_results = bool(my_option_id or row["status"] == "closed" or can_manage(identity, "surveys"))
    options = connection.execute("""
        SELECT o.id, o.label, COUNT(a.user_id) AS votes
        FROM survey_options o LEFT JOIN survey_answers a ON a.option_id = o.id
        WHERE o.survey_id = ? GROUP BY o.id ORDER BY o.position
    """, (row["id"],)).fetchall()
    return {
        **dict(row), "my_option_id": my_option_id,
        "options": [{"id": option["id"], "label": option["label"],
                     "votes": option["votes"] if show_results else None} for option in options],
        "total_responses": sum(option["votes"] for option in options) if show_results else None,
    }
