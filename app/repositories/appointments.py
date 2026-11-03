# SPDX-License-Identifier: Apache-2.0
"""Tenant-scoped SQLite persistence for citizen reception appointments."""

import sqlite3
from pathlib import Path

from app.core import config


def appointment_db() -> sqlite3.Connection:
    path = Path(config.APPOINTMENT_DB_PATH)
    path.parent.mkdir(parents=True, exist_ok=True)
    connection = sqlite3.connect(path, timeout=10)
    connection.row_factory = sqlite3.Row
    connection.execute("PRAGMA foreign_keys = ON")
    connection.executescript("""
        CREATE TABLE IF NOT EXISTS appointment_slots (
            id TEXT PRIMARY KEY, tenant TEXT NOT NULL, starts_at TEXT NOT NULL,
            ends_at TEXT NOT NULL, location TEXT NOT NULL, capacity INTEGER NOT NULL,
            created_at TEXT NOT NULL, created_by TEXT NOT NULL
        );
        CREATE INDEX IF NOT EXISTS appointment_slots_tenant_start
            ON appointment_slots(tenant, starts_at);
        CREATE TABLE IF NOT EXISTS appointments (
            id TEXT PRIMARY KEY, tenant TEXT NOT NULL,
            slot_id TEXT NOT NULL REFERENCES appointment_slots(id),
            user_id TEXT NOT NULL, reason TEXT NOT NULL,
            status TEXT NOT NULL, created_at TEXT NOT NULL,
            reviewed_at TEXT, reviewed_by TEXT, review_note TEXT,
            cancelled_at TEXT
        );
        CREATE INDEX IF NOT EXISTS appointments_tenant_slot
            ON appointments(tenant, slot_id, status);
        CREATE UNIQUE INDEX IF NOT EXISTS appointments_active_user_slot
            ON appointments(tenant, slot_id, user_id)
            WHERE status IN ('pending', 'confirmed');
    """)
    return connection


SLOT_VIEW = """
    SELECT s.*, (SELECT COUNT(*) FROM appointments a
        WHERE a.tenant = s.tenant AND a.slot_id = s.id AND a.status = 'confirmed')
        AS confirmed_count
    FROM appointment_slots s
"""


APPOINTMENT_VIEW = """
    SELECT a.*, s.starts_at, s.ends_at, s.location
    FROM appointments a JOIN appointment_slots s ON s.id = a.slot_id
"""


def slot_for(connection: sqlite3.Connection, tenant: str, slot_id: str) -> sqlite3.Row | None:
    return connection.execute(SLOT_VIEW + " WHERE s.tenant = ? AND s.id = ?", (tenant, slot_id)).fetchone()


def appointment_for(connection: sqlite3.Connection, tenant: str, appointment_id: str) -> sqlite3.Row | None:
    return connection.execute(
        APPOINTMENT_VIEW + " WHERE a.tenant = ? AND a.id = ?", (tenant, appointment_id)
    ).fetchone()


def begin_write(connection: sqlite3.Connection) -> None:
    connection.execute("BEGIN IMMEDIATE")


def upcoming_slots(connection: sqlite3.Connection, tenant: str, now: str) -> list[sqlite3.Row]:
    return connection.execute(
        SLOT_VIEW + " WHERE s.tenant = ? AND s.starts_at > ? ORDER BY s.starts_at LIMIT 100",
        (tenant, now),
    ).fetchall()


def insert_slot(connection: sqlite3.Connection, values: tuple) -> None:
    connection.execute(
        """INSERT INTO appointment_slots
           (id, tenant, starts_at, ends_at, location, capacity, created_at, created_by)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
        values,
    )


def visible_appointments(connection: sqlite3.Connection, tenant: str, user_id: str | None) -> list[sqlite3.Row]:
    clause = "a.tenant = ?" if user_id is None else "a.tenant = ? AND a.user_id = ?"
    params = (tenant,) if user_id is None else (tenant, user_id)
    return connection.execute(
        APPOINTMENT_VIEW + f" WHERE {clause} ORDER BY a.created_at DESC, a.rowid DESC LIMIT 100",
        params,
    ).fetchall()


def insert_appointment(connection: sqlite3.Connection, values: tuple) -> None:
    connection.execute(
        """INSERT INTO appointments (id, tenant, slot_id, user_id, reason, status, created_at)
           VALUES (?, ?, ?, ?, ?, 'pending', ?)""",
        values,
    )


def save_decision(connection: sqlite3.Connection, tenant: str, appointment_id: str,
                  decision: str, reviewed_at: str, reviewed_by: str, note: str | None) -> None:
    connection.execute(
        """UPDATE appointments SET status = ?, reviewed_at = ?, reviewed_by = ?, review_note = ?
           WHERE id = ? AND tenant = ?""",
        (decision, reviewed_at, reviewed_by, note, appointment_id, tenant),
    )


def save_cancellation(connection: sqlite3.Connection, tenant: str,
                      appointment_id: str, cancelled_at: str) -> None:
    connection.execute(
        "UPDATE appointments SET status = 'cancelled', cancelled_at = ? WHERE id = ? AND tenant = ?",
        (cancelled_at, appointment_id, tenant),
    )
