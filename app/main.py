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
ACTIONS = {"triage", "assign", "resolve"}
NEWS_DB_PATH = os.getenv("NEWS_DB_PATH", "data/bulletins.sqlite3")


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


@dataclass(frozen=True)
class Caller:
    user: str
    tenant: str
    roles: frozenset[str]


def caller(
    x_internal_secret: str | None = Header(default=None),
    x_dxos_user: str | None = Header(default=None),
    x_dxos_tenant: str | None = Header(default=None),
    x_dxos_roles: str = Header(default=""),
) -> Caller:
    if not INTERNAL_SECRET or not x_internal_secret or not hmac.compare_digest(
        x_internal_secret, INTERNAL_SECRET
    ):
        raise HTTPException(status_code=403, detail="Gateway access required")
    if not x_dxos_user or not x_dxos_tenant:
        raise HTTPException(status_code=403, detail="Identity context required")
    return Caller(x_dxos_user, x_dxos_tenant, frozenset(x_dxos_roles.split(",")))


def core_headers(identity: Caller) -> dict[str, str]:
    return {
        "X-Internal-Secret": INTERNAL_SECRET,
        "X-DXOS-User": identity.user,
        "X-DXOS-Tenant": identity.tenant,
        "X-DXOS-Roles": ",".join(identity.roles),
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


async def get_report_record(report_id: str, identity: Caller) -> dict:
    record = await core_json(DATA_URL, f"/records/{report_id}", identity)
    if record.get("kind") != "field-report":
        raise HTTPException(status_code=404, detail="Report not found")
    return record


async def find_instance(report_id: str, identity: Caller) -> dict | None:
    instances = await core_json(WORKFLOW_URL, "/instances", identity)
    return next((item for item in instances if item["definition_key"] == "report-handling" and item["reference_id"] == report_id), None)


@app.get("/health")
def health() -> dict:
    return {"status": "ok", "service": "opencity-backend"}


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
    if not identity.roles.intersection({"operator", "admin"}):
        raise HTTPException(status_code=403, detail="Operator role required")
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


@app.get("/reports")
async def list_reports(identity: Caller = Depends(caller)) -> list[dict]:
    records = await core_json(DATA_URL, "/records", identity)
    instances = await core_json(WORKFLOW_URL, "/instances", identity)
    by_record = {item["reference_id"]: item for item in instances if item["definition_key"] == "report-handling"}
    return [report_view(item, by_record.get(item["id"])) for item in records if item["kind"] == "field-report"]


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
    if not identity.roles.intersection({"operator", "admin"}):
        raise HTTPException(status_code=403, detail="Operator role required")
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
