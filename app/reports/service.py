# SPDX-License-Identifier: Apache-2.0
from datetime import datetime, timedelta, timezone

from fastapi import HTTPException

from app import config, core_client
from app.security import Caller, can_dispatch
from app.reports.storage import routing_for, routing_map


def matches_image_type(content: bytes, claimed_type: str) -> bool:
    return (
        (claimed_type == "image/jpeg" and content.startswith(b"\xff\xd8\xff"))
        or (claimed_type == "image/png" and content.startswith(b"\x89PNG\r\n\x1a\n"))
        or (claimed_type == "image/webp" and content.startswith(b"RIFF") and content[8:12] == b"WEBP")
    )


def report_view(record: dict, instance: dict | None = None) -> dict:
    return report_view_with_routing(record, instance, None)


def report_view_with_routing(record: dict, instance: dict | None, routing: dict | None) -> dict:
    workflow_history = instance.get("history", []) if instance else []
    routing_history = [{
        "action": event["action"], "actor": event["actor"],
        "created_at": event["created_at"], "from_state": None, "to_state": None,
        "from_unit": event["from_unit"], "to_unit": event["to_unit"], "note": event["note"],
    } for event in (routing or {}).get("events", [])]
    return {
        "id": record["id"],
        "title": record["payload"].get("title", ""),
        "description": record["payload"].get("description", ""),
        "category": record["payload"].get("category", ""),
        "unit_id": report_unit(record),
        "assigned_unit": routing["unit_id"] if routing else None,
        "due_at": routing["due_at"] if routing else None,
        "accepted_at": routing["accepted_at"] if routing else None,
        "pending_unit": routing["pending_unit"] if routing else None,
        "pending_reason": routing["pending_reason"] if routing else None,
        "address": record["payload"].get("address", ""),
        "latitude": record["payload"].get("latitude"),
        "longitude": record["payload"].get("longitude"),
        "attachment_ids": record["payload"].get("attachment_ids", []),
        "created_by": record["created_by"],
        "created_at": record["created_at"],
        "updated_at": record["updated_at"],
        "workflow_id": instance["id"] if instance else None,
        "state": instance["state"] if instance else None,
        "history": sorted([*workflow_history, *routing_history], key=lambda event: event["created_at"]),
    }


def report_unit(record: dict) -> str:
    # Derive from the category for both new and existing reports.
    return config.REPORT_UNITS.get(record["payload"].get("category"), "intake")


def report_visible(record: dict, identity: Caller, routing: dict | None = None) -> bool:
    if can_dispatch(identity):
        return True
    if "reports_operator" in identity.roles and identity.unit in config.VALID_UNITS:
        return bool(routing and routing["unit_id"] == identity.unit)
    return record["created_by"] == identity.user


async def get_report_record(report_id: str, identity: Caller) -> dict:
    record = await core_client.core_json(config.DATA_URL, f"/records/{report_id}", identity)
    if record.get("kind") != "field-report" or not report_visible(
        record, identity, routing_for(report_id, identity.tenant)
    ):
        raise HTTPException(status_code=404, detail="Report not found")
    return record


async def find_instance(report_id: str, identity: Caller) -> dict | None:
    instances = await core_client.core_json(config.WORKFLOW_URL, "/instances", identity)
    return next((item for item in instances if item["definition_key"] == "report-handling" and item["reference_id"] == report_id), None)


async def visible_report_views(identity: Caller) -> list[dict]:
    records = await core_client.core_json(config.DATA_URL, "/records", identity)
    instances = await core_client.core_json(config.WORKFLOW_URL, "/instances", identity)
    by_record = {item["reference_id"]: item for item in instances if item["definition_key"] == "report-handling"}
    routing = routing_map(identity.tenant)
    return [report_view_with_routing(item, by_record.get(item["id"]), routing.get(item["id"]))
            for item in records if item["kind"] == "field-report"
            and report_visible(item, identity, routing.get(item["id"]))]


def report_deadline_status(report: dict, now: datetime) -> str | None:
    if report["state"] == "resolved" or not report["due_at"]:
        return None
    try:
        due = datetime.fromisoformat(report["due_at"])
    except ValueError:
        return None
    if due.tzinfo is None:
        return None
    if due < now:
        return "overdue"
    if due <= now + timedelta(hours=24):
        return "due_soon"
    return None


def report_dashboard(reports: list[dict], now: datetime) -> dict:
    counts = {key: 0 for key in (
        "total", "new", "triaged", "in_progress", "resolved", "unassigned", "due_soon", "overdue")}
    units: dict[str, dict] = {}
    urgent: list[dict] = []
    for report in reports:
        state = report["state"] or "submitted"
        unit = report["assigned_unit"] or "unassigned"
        deadline = report_deadline_status(report, now)
        counts["total"] += 1
        if state == "submitted":
            counts["new"] += 1
        elif state == "triaged":
            counts["triaged"] += 1
        elif state == "assigned":
            counts["in_progress"] += 1
        elif state == "resolved":
            counts["resolved"] += 1
        if unit == "unassigned" and state != "resolved":
            counts["unassigned"] += 1
        if deadline:
            counts[deadline] += 1
        row = units.setdefault(unit, {"unit_id": unit, "total": 0, "active": 0,
                                      "resolved": 0, "due_soon": 0, "overdue": 0})
        row["total"] += 1
        row["resolved" if state == "resolved" else "active"] += 1
        if deadline:
            row[deadline] += 1
        priority = deadline or ("unassigned" if unit == "unassigned" and state != "resolved" else None)
        if priority:
            urgent.append({key: report[key] for key in (
                "id", "title", "category", "address", "state", "assigned_unit", "due_at")}
                          | {"priority": priority})
    rank = {"overdue": 0, "due_soon": 1, "unassigned": 2}
    urgent.sort(key=lambda item: (rank[item["priority"]], item["due_at"] or "", item["id"]))
    return {"generated_at": now.isoformat(), "counts": counts,
            "units": sorted(units.values(), key=lambda row: row["unit_id"]),
            "urgent": urgent[:10]}
