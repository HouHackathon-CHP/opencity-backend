# SPDX-License-Identifier: Apache-2.0
"""OpenCity domain API behind the DX-OS gateway."""

import hmac
import os
import sqlite3
from contextlib import closing
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Literal
from uuid import uuid4

import httpx
from fastapi import Depends, FastAPI, File, Form, Header, HTTPException, UploadFile
from fastapi.responses import Response
from pydantic import BaseModel, Field


INTERNAL_SECRET = os.getenv("INTERNAL_GATEWAY_SECRET", "")
DATA_URL = os.getenv("DATA_URL", "http://data:8000")
WORKFLOW_URL = os.getenv("WORKFLOW_URL", "http://workflow:8000")
MAX_PHOTO_BYTES = 10 * 1024 * 1024
PHOTO_TYPES = {"image/jpeg", "image/png", "image/webp"}
REPORT_CATEGORIES = {"Hạ tầng", "Môi trường", "Giao thông", "Chiếu sáng", "Cây xanh", "Khác"}
REPORT_UNITS = {
    "Hạ tầng": "infrastructure", "Chiếu sáng": "infrastructure",
    "Môi trường": "environment", "Cây xanh": "environment",
    "Giao thông": "transport", "Khác": "intake",
}
ACTIONS = {"triage", "assign", "resolve"}
MANAGEMENT_ROLES = {
    "reports": "reports_operator",
    "bulletins": "bulletins_operator",
    "surveys": "surveys_operator",
}
NEWS_DB_PATH = os.getenv("NEWS_DB_PATH", "data/bulletins.sqlite3")
SURVEY_DB_PATH = os.getenv("SURVEY_DB_PATH", "data/surveys.sqlite3")


def matches_image_type(content: bytes, claimed_type: str) -> bool:
    return (
        (claimed_type == "image/jpeg" and content.startswith(b"\xff\xd8\xff"))
        or (claimed_type == "image/png" and content.startswith(b"\x89PNG\r\n\x1a\n"))
        or (claimed_type == "image/webp" and content.startswith(b"RIFF") and content[8:12] == b"WEBP")
    )

app = FastAPI(title="OpenCity Domain API", docs_url=None, redoc_url=None)


class BulletinInput(BaseModel):
    category: Literal["news", "alert"]
    title: str = Field(min_length=5, max_length=160)
    summary: str = Field(min_length=10, max_length=300)
    body: str = Field(min_length=20, max_length=5000)
    area: str | None = Field(default=None, max_length=120)
    latitude: float | None = Field(default=None, ge=-90, le=90)
    longitude: float | None = Field(default=None, ge=-180, le=180)


class SurveyInput(BaseModel):
    title: str = Field(min_length=5, max_length=160)
    description: str = Field(min_length=20, max_length=2000)
    options: list[str] = Field(min_length=2, max_length=8)


class SurveyAnswer(BaseModel):
    option_id: str


def bulletin_db() -> sqlite3.Connection:
    path = Path(NEWS_DB_PATH)
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


def survey_db() -> sqlite3.Connection:
    path = Path(SURVEY_DB_PATH)
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


@dataclass(frozen=True)
class Caller:
    user: str
    tenant: str
    roles: frozenset[str]
    unit: str | None = None


def can_manage(identity: Caller, feature: str) -> bool:
    if "admin" in identity.roles:
        return True
    if MANAGEMENT_ROLES[feature] not in identity.roles:
        return False
    return feature != "reports" or identity.unit in REPORT_UNITS.values()


def require_manager(identity: Caller, feature: str) -> None:
    if not can_manage(identity, feature):
        raise HTTPException(status_code=403, detail=f"{MANAGEMENT_ROLES[feature]} role required")


def caller(
    x_internal_secret: str | None = Header(default=None),
    x_dxos_user: str | None = Header(default=None),
    x_dxos_tenant: str | None = Header(default=None),
    x_dxos_roles: str = Header(default=""),
    x_dxos_unit: str | None = Header(default=None),
) -> Caller:
    if not INTERNAL_SECRET or not x_internal_secret or not hmac.compare_digest(
        x_internal_secret, INTERNAL_SECRET
    ):
        raise HTTPException(status_code=403, detail="Gateway access required")
    if not x_dxos_user or not x_dxos_tenant:
        raise HTTPException(status_code=403, detail="Identity context required")
    return Caller(x_dxos_user, x_dxos_tenant, frozenset(x_dxos_roles.split(",")), x_dxos_unit or None)


def core_headers(identity: Caller) -> dict[str, str]:
    # Only this business API may delegate report access to the generic core.
    # The gateway denies browser/mobile access to generic core routes.
    core_roles = set(identity.roles) - {"operator"}
    if can_manage(identity, "reports"):
        core_roles.add("operator")
    return {
        "X-Internal-Secret": INTERNAL_SECRET,
        "X-DXOS-User": identity.user,
        "X-DXOS-Tenant": identity.tenant,
        "X-DXOS-Roles": ",".join(sorted(core_roles)),
    }


async def core_response(
    base: str, path: str, identity: Caller, method: str = "GET", *,
    json_body: dict | None = None, files: dict | None = None,
) -> httpx.Response:
    try:
        async with httpx.AsyncClient(timeout=30) as client:
            response = await client.request(
                method, f"{base.rstrip('/')}{path}", headers=core_headers(identity),
                json=json_body, files=files,
            )
    except httpx.RequestError as exc:
        raise HTTPException(status_code=503, detail="DX-OS core is unavailable") from exc
    if not response.is_success:
        try:
            detail = response.json().get("detail", "DX-OS core request failed")
        except (ValueError, AttributeError):
            detail = "DX-OS core request failed"
        raise HTTPException(status_code=response.status_code, detail=detail)
    return response


async def core_json(base: str, path: str, identity: Caller, method: str = "GET", **kwargs):
    return (await core_response(base, path, identity, method, **kwargs)).json()


def report_view(record: dict, instance: dict | None = None) -> dict:
    return {
        "id": record["id"],
        "title": record["payload"].get("title", ""),
        "description": record["payload"].get("description", ""),
        "category": record["payload"].get("category", ""),
        "unit_id": report_unit(record),
        "address": record["payload"].get("address", ""),
        "latitude": record["payload"].get("latitude"),
        "longitude": record["payload"].get("longitude"),
        "attachment_ids": record["payload"].get("attachment_ids", []),
        "created_by": record["created_by"],
        "created_at": record["created_at"],
        "updated_at": record["updated_at"],
        "workflow_id": instance["id"] if instance else None,
        "state": instance["state"] if instance else None,
        "history": instance.get("history", []) if instance else [],
    }


def report_unit(record: dict) -> str:
    # Derive from the category for both new and existing reports.
    return REPORT_UNITS.get(record["payload"].get("category"), "intake")


def report_visible(record: dict, identity: Caller) -> bool:
    if "admin" in identity.roles:
        return True
    if can_manage(identity, "reports"):
        return identity.unit == report_unit(record)
    return record["created_by"] == identity.user


async def get_report_record(report_id: str, identity: Caller) -> dict:
    record = await core_json(DATA_URL, f"/records/{report_id}", identity)
    if record.get("kind") != "field-report" or not report_visible(record, identity):
        raise HTTPException(status_code=404, detail="Report not found")
    return record


async def find_instance(report_id: str, identity: Caller) -> dict | None:
    instances = await core_json(WORKFLOW_URL, "/instances", identity)
    return next((item for item in instances if item["definition_key"] == "report-handling" and item["reference_id"] == report_id), None)


@app.get("/health")
def health() -> dict:
    return {"status": "ok", "service": "opencity-backend"}


@app.get("/me/capabilities")
def my_capabilities(identity: Caller = Depends(caller)) -> dict:
    return {
        "management": [feature for feature in MANAGEMENT_ROLES if can_manage(identity, feature)],
        "report_unit": identity.unit if can_manage(identity, "reports") and "admin" not in identity.roles else None,
    }


@app.get("/bulletins")
def list_bulletins(identity: Caller = Depends(caller)) -> list[dict]:
    with closing(bulletin_db()) as connection:
        rows = connection.execute(
            "SELECT * FROM bulletins WHERE tenant = ? ORDER BY published_at DESC, rowid DESC LIMIT 100",
            (identity.tenant,),
        ).fetchall()
    return [bulletin_view(row) for row in rows]


@app.get("/bulletins/{bulletin_id}")
def get_bulletin(bulletin_id: str, identity: Caller = Depends(caller)) -> dict:
    with closing(bulletin_db()) as connection:
        row = connection.execute(
            "SELECT * FROM bulletins WHERE id = ? AND tenant = ?", (bulletin_id, identity.tenant)
        ).fetchone()
    if row is None:
        raise HTTPException(status_code=404, detail="Bulletin not found")
    return bulletin_view(row)


@app.post("/bulletins", status_code=201)
def publish_bulletin(body: BulletinInput, identity: Caller = Depends(caller)) -> dict:
    require_manager(identity, "bulletins")
    if (body.latitude is None) != (body.longitude is None):
        raise HTTPException(status_code=422, detail="Latitude and longitude must be provided together")
    if not body.title.strip() or not body.summary.strip() or not body.body.strip():
        raise HTTPException(status_code=422, detail="Bulletin text cannot be empty")
    values = (
        str(uuid4()), identity.tenant, body.category, body.title.strip(), body.summary.strip(),
        body.body.strip(), body.area.strip() if body.area else None, body.latitude, body.longitude,
        datetime.now(timezone.utc).isoformat(), identity.user,
    )
    with closing(bulletin_db()) as connection:
        with connection:
            connection.execute(
                """INSERT INTO bulletins
                   (id, tenant, category, title, summary, body, area, latitude, longitude, published_at, created_by)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                values,
            )
        row = connection.execute("SELECT * FROM bulletins WHERE id = ?", (values[0],)).fetchone()
    return bulletin_view(row)


@app.get("/surveys")
def list_surveys(identity: Caller = Depends(caller)) -> list[dict]:
    with closing(survey_db()) as connection:
        rows = connection.execute("""
            SELECT s.id, s.title, s.description, s.status, s.created_at, s.closed_at,
                   a.option_id AS my_option_id
            FROM surveys s LEFT JOIN survey_answers a
              ON a.survey_id = s.id AND a.user_id = ?
            WHERE s.tenant = ? ORDER BY s.created_at DESC, s.rowid DESC LIMIT 100
        """, (identity.user, identity.tenant)).fetchall()
    return [dict(row) for row in rows]


@app.post("/surveys", status_code=201)
def create_survey(body: SurveyInput, identity: Caller = Depends(caller)) -> dict:
    require_manager(identity, "surveys")
    labels = [option.strip() for option in body.options]
    if (not body.title.strip() or not body.description.strip() or
            any(not label or len(label) > 120 for label in labels) or
            len({label.casefold() for label in labels}) != len(labels)):
        raise HTTPException(status_code=422, detail="Survey fields or options are invalid")
    survey_id = str(uuid4())
    now = datetime.now(timezone.utc).isoformat()
    with closing(survey_db()) as connection:
        with connection:
            connection.execute("""
                INSERT INTO surveys (id, tenant, title, description, status, created_at, created_by)
                VALUES (?, ?, ?, ?, 'open', ?, ?)
            """, (survey_id, identity.tenant, body.title.strip(), body.description.strip(), now, identity.user))
            connection.executemany(
                "INSERT INTO survey_options (id, survey_id, label, position) VALUES (?, ?, ?, ?)",
                [(str(uuid4()), survey_id, label, position) for position, label in enumerate(labels)],
            )
        return survey_view(connection, survey_row(connection, survey_id, identity), identity)


@app.get("/surveys/{survey_id}")
def get_survey(survey_id: str, identity: Caller = Depends(caller)) -> dict:
    with closing(survey_db()) as connection:
        return survey_view(connection, survey_row(connection, survey_id, identity), identity)


@app.post("/surveys/{survey_id}/answers")
def answer_survey(survey_id: str, body: SurveyAnswer, identity: Caller = Depends(caller)) -> dict:
    with closing(survey_db()) as connection:
        with connection:
            connection.execute("BEGIN IMMEDIATE")
            row = survey_row(connection, survey_id, identity)
            if row["status"] != "open":
                raise HTTPException(status_code=409, detail="Survey is closed")
            option = connection.execute(
                "SELECT id FROM survey_options WHERE id = ? AND survey_id = ?",
                (body.option_id, survey_id),
            ).fetchone()
            if option is None:
                raise HTTPException(status_code=422, detail="Option does not belong to survey")
            try:
                connection.execute(
                    "INSERT INTO survey_answers (survey_id, user_id, option_id, created_at) VALUES (?, ?, ?, ?)",
                    (survey_id, identity.user, option["id"], datetime.now(timezone.utc).isoformat()),
                )
            except sqlite3.IntegrityError as exc:
                raise HTTPException(status_code=409, detail="Survey already answered") from exc
        return survey_view(connection, row, identity)


@app.post("/surveys/{survey_id}/close")
def close_survey(survey_id: str, identity: Caller = Depends(caller)) -> dict:
    require_manager(identity, "surveys")
    with closing(survey_db()) as connection:
        with connection:
            connection.execute("BEGIN IMMEDIATE")
            row = survey_row(connection, survey_id, identity)
            if row["status"] == "open":
                connection.execute(
                    "UPDATE surveys SET status = 'closed', closed_at = ? WHERE id = ?",
                    (datetime.now(timezone.utc).isoformat(), survey_id),
                )
        return survey_view(connection, survey_row(connection, survey_id, identity), identity)


@app.get("/reports")
async def list_reports(identity: Caller = Depends(caller)) -> list[dict]:
    records = await core_json(DATA_URL, "/records", identity)
    instances = await core_json(WORKFLOW_URL, "/instances", identity)
    by_record = {item["reference_id"]: item for item in instances if item["definition_key"] == "report-handling"}
    return [report_view(item, by_record.get(item["id"])) for item in records
            if item["kind"] == "field-report" and report_visible(item, identity)]


@app.post("/reports", status_code=201)
async def create_report(
    title: str = Form(min_length=5, max_length=120),
    description: str = Form(min_length=15, max_length=2000),
    category: str = Form(),
    address: str = Form(min_length=1, max_length=250),
    latitude: float | None = Form(default=None),
    longitude: float | None = Form(default=None),
    photo: UploadFile | None = File(default=None),
    identity: Caller = Depends(caller),
) -> dict:
    if category not in REPORT_CATEGORIES:
        raise HTTPException(status_code=422, detail="Unknown report category")
    if (latitude is None) != (longitude is None):
        raise HTTPException(status_code=422, detail="Latitude and longitude must be provided together")
    if latitude is not None and not (-90 <= latitude <= 90 and -180 <= longitude <= 180):
        raise HTTPException(status_code=422, detail="Invalid coordinates")
    if not title.strip() or not description.strip() or not address.strip():
        raise HTTPException(status_code=422, detail="Empty report fields are not allowed")
    photo_bytes = None
    if photo:
        if photo.content_type not in PHOTO_TYPES:
            raise HTTPException(status_code=422, detail="Only JPEG, PNG and WebP images are accepted")
        photo_bytes = await photo.read(MAX_PHOTO_BYTES + 1)
        if len(photo_bytes) > MAX_PHOTO_BYTES:
            raise HTTPException(status_code=413, detail="Maximum image size is 10 MiB")
        if not matches_image_type(photo_bytes, photo.content_type):
            raise HTTPException(status_code=422, detail="Image content does not match its declared type")
    payload = {
        "title": title.strip(), "description": description.strip(),
        "category": category, "address": address.strip(),
    }
    if latitude is not None:
        payload.update(latitude=latitude, longitude=longitude)
    record = await core_json(DATA_URL, "/records", identity, "POST", json_body={"kind": "field-report", "payload": payload})
    warnings = []
    if photo and photo_bytes is not None:
        try:
            uploaded = await core_json(
                DATA_URL, f"/objects?record_id={record['id']}", identity, "POST",
                files={"file": (photo.filename or "photo", photo_bytes, photo.content_type)},
            )
            payload["attachment_ids"] = [uploaded["id"]]
        except HTTPException:
            warnings.append("Ảnh chưa được tải lên.")
    instance = None
    try:
        instance = await core_json(
            WORKFLOW_URL, "/instances", identity, "POST",
            json_body={"definition_key": "report-handling", "reference_id": record["id"]},
        )
        payload["workflow_id"] = instance["id"]
    except HTTPException:
        warnings.append("Quy trình chưa khởi tạo; có thể thử lại trong chi tiết phản ánh.")
    if payload != record["payload"]:
        try:
            record = await core_json(DATA_URL, f"/records/{record['id']}", identity, "PATCH", json_body={"payload": payload})
        except HTTPException:
            warnings.append("Một số thông tin liên kết chưa đồng bộ.")
    return {**report_view(record, instance), "warnings": warnings}


@app.get("/reports/{report_id}")
async def get_report(report_id: str, identity: Caller = Depends(caller)) -> dict:
    record = await get_report_record(report_id, identity)
    instance = await find_instance(report_id, identity)
    if instance:
        instance = await core_json(WORKFLOW_URL, f"/instances/{instance['id']}", identity)
    return report_view(record, instance)


@app.post("/reports/{report_id}/retry-workflow")
async def retry_workflow(report_id: str, identity: Caller = Depends(caller)) -> dict:
    record = await get_report_record(report_id, identity)
    instance = await find_instance(report_id, identity)
    if instance is None:
        instance = await core_json(WORKFLOW_URL, "/instances", identity, "POST", json_body={"definition_key": "report-handling", "reference_id": report_id})
    return report_view(record, instance)


@app.post("/reports/{report_id}/actions/{action}")
async def take_action(report_id: str, action: str, identity: Caller = Depends(caller)) -> dict:
    require_manager(identity, "reports")
    if action not in ACTIONS:
        raise HTTPException(status_code=404, detail="Unknown action")
    record = await get_report_record(report_id, identity)
    instance = await find_instance(report_id, identity)
    if instance is None:
        raise HTTPException(status_code=409, detail="Report workflow has not started")
    instance = await core_json(WORKFLOW_URL, f"/instances/{instance['id']}/actions/{action}", identity, "POST")
    return report_view(record, instance)


@app.get("/reports/{report_id}/attachments/{object_id}")
async def report_attachment(report_id: str, object_id: str, identity: Caller = Depends(caller)) -> Response:
    record = await get_report_record(report_id, identity)
    if object_id not in record["payload"].get("attachment_ids", []):
        raise HTTPException(status_code=404, detail="Attachment not found")
    response = await core_response(DATA_URL, f"/objects/{object_id}", identity)
    return Response(content=response.content, media_type=response.headers.get("content-type", "application/octet-stream"))
