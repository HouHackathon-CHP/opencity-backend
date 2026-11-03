# SPDX-License-Identifier: Apache-2.0
import sqlite3
import json
from contextlib import closing
from datetime import datetime, timezone
from pathlib import Path
from uuid import uuid4

from app.core import config
from app.core.security import Caller


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
        CREATE TABLE IF NOT EXISTS triage_suggestions (
            id TEXT PRIMARY KEY, tenant TEXT NOT NULL, report_id TEXT NOT NULL,
            generated_by TEXT NOT NULL, created_at TEXT NOT NULL,
            source_updated_at TEXT NOT NULL, model_version TEXT NOT NULL,
            suggested_unit TEXT NOT NULL, ranked_labels TEXT NOT NULL,
            signals TEXT NOT NULL, similar TEXT NOT NULL,
            urgency TEXT NOT NULL, urgency_ranked TEXT NOT NULL
        );
        CREATE INDEX IF NOT EXISTS triage_suggestions_report
            ON triage_suggestions(tenant, report_id, created_at DESC);
        CREATE TABLE IF NOT EXISTS triage_reviews (
            suggestion_id TEXT PRIMARY KEY REFERENCES triage_suggestions(id),
            tenant TEXT NOT NULL, report_id TEXT NOT NULL,
            chosen_unit TEXT NOT NULL, matched INTEGER NOT NULL,
            reviewed_by TEXT NOT NULL, reviewed_at TEXT NOT NULL
        );
        CREATE INDEX IF NOT EXISTS triage_reviews_tenant ON triage_reviews(tenant);
    """)
    return connection


def save_triage_suggestion(identity: Caller, report_id: str, source_updated_at: str,
                           analysis: dict) -> dict:
    suggestion_id = str(uuid4())
    now = datetime.now(timezone.utc).isoformat()
    suggested_unit = analysis.get("suggested_unit", analysis["ranked_labels"][0]["label"])
    with closing(report_db()) as connection:
        with connection:
            connection.execute(
                """INSERT INTO triage_suggestions
                   (id, tenant, report_id, generated_by, created_at, source_updated_at,
                    model_version, suggested_unit, ranked_labels, signals, similar,
                    urgency, urgency_ranked)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (suggestion_id, identity.tenant, report_id, identity.user, now, source_updated_at,
                 analysis["model_version"], suggested_unit,
                 json.dumps(analysis["ranked_labels"]), json.dumps(analysis["signals"]),
                 json.dumps(analysis["similar"]), analysis["urgency"],
                 json.dumps(analysis["urgency_ranked"])),
            )
    return triage_suggestion_for(identity.tenant, report_id, suggestion_id)


def _triage_view(row: sqlite3.Row) -> dict:
    result = dict(row)
    for field in ("ranked_labels", "signals", "similar", "urgency_ranked"):
        result[field] = json.loads(result[field])
    result["reviewed_unit"] = result.pop("chosen_unit")
    result["matched"] = bool(result["matched"]) if result["matched"] is not None else None
    return result


def triage_suggestion_for(tenant: str, report_id: str, suggestion_id: str | None = None) -> dict | None:
    with closing(report_db()) as connection:
        if suggestion_id:
            condition = "s.tenant = ? AND s.report_id = ? AND s.id = ?"
            params = (tenant, report_id, suggestion_id)
        else:
            condition = "s.tenant = ? AND s.report_id = ?"
            params = (tenant, report_id)
        row = connection.execute(
            """SELECT s.*, r.chosen_unit, r.matched FROM triage_suggestions s
               LEFT JOIN triage_reviews r ON r.suggestion_id = s.id
               WHERE """ + condition + " ORDER BY s.created_at DESC, s.rowid DESC LIMIT 1", params,
        ).fetchone()
    return _triage_view(row) if row else None


def save_triage_review(connection: sqlite3.Connection, suggestion: dict,
                       chosen_unit: str, identity: Caller) -> None:
    connection.execute(
        """INSERT INTO triage_reviews
           (suggestion_id, tenant, report_id, chosen_unit, matched, reviewed_by, reviewed_at)
           VALUES (?, ?, ?, ?, ?, ?, ?)""",
        (suggestion["id"], identity.tenant, suggestion["report_id"], chosen_unit,
         int(chosen_unit == suggestion["suggested_unit"]), identity.user,
         datetime.now(timezone.utc).isoformat()),
    )


def triage_metrics(tenant: str) -> dict:
    with closing(report_db()) as connection:
        row = connection.execute("""
            SELECT
              (SELECT COUNT(*) FROM triage_suggestions WHERE tenant = ?) AS generated,
              COUNT(r.suggestion_id) AS reviewed,
              COALESCE(SUM(CASE WHEN r.matched = 1 THEN 1 ELSE 0 END), 0) AS accepted,
              COALESCE(SUM(CASE WHEN r.matched = 0 THEN 1 ELSE 0 END), 0) AS overridden
            FROM triage_reviews r WHERE r.tenant = ?
        """, (tenant, tenant)).fetchone()
    return dict(row)


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
