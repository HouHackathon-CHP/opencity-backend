# SPDX-License-Identifier: Apache-2.0
from contextlib import closing
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from fastapi.responses import Response

from app import config, core_client
from app.security import Caller, caller, can_dispatch, require_manager
from app.notifications.service import add_notification
from app.reports.schemas import DispatchInput, TransferInput, NoteInput
from app.reports.storage import report_db, routing_for, add_report_event
from app.reports.service import (
    matches_image_type, report_view, report_view_with_routing, get_report_record,
    find_instance, visible_report_views, report_dashboard,
)

router = APIRouter()


@router.get("/reports")
async def list_reports(identity: Caller = Depends(caller)) -> list[dict]:
    return await visible_report_views(identity)


@router.get("/reports/dashboard")
async def get_reports_dashboard(identity: Caller = Depends(caller)) -> dict:
    require_manager(identity, "reports")
    return report_dashboard(await visible_report_views(identity), datetime.now(timezone.utc))


@router.post("/reports", status_code=201)
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
    if category not in config.REPORT_CATEGORIES:
        raise HTTPException(status_code=422, detail="Unknown report category")
    if (latitude is None) != (longitude is None):
        raise HTTPException(status_code=422, detail="Latitude and longitude must be provided together")
    if latitude is not None and not (-90 <= latitude <= 90 and -180 <= longitude <= 180):
        raise HTTPException(status_code=422, detail="Invalid coordinates")
    if not title.strip() or not description.strip() or not address.strip():
        raise HTTPException(status_code=422, detail="Empty report fields are not allowed")
    photo_bytes = None
    if photo:
        if photo.content_type not in config.PHOTO_TYPES:
            raise HTTPException(status_code=422, detail="Only JPEG, PNG and WebP images are accepted")
        photo_bytes = await photo.read(config.MAX_PHOTO_BYTES + 1)
        if len(photo_bytes) > config.MAX_PHOTO_BYTES:
            raise HTTPException(status_code=413, detail="Maximum image size is 10 MiB")
        if not matches_image_type(photo_bytes, photo.content_type):
            raise HTTPException(status_code=422, detail="Image content does not match its declared type")
    payload = {
        "title": title.strip(), "description": description.strip(),
        "category": category, "address": address.strip(),
    }
    if latitude is not None:
        payload.update(latitude=latitude, longitude=longitude)
    record = await core_client.core_json(config.DATA_URL, "/records", identity, "POST", json_body={"kind": "field-report", "payload": payload})
    warnings = []
    if photo and photo_bytes is not None:
        try:
            uploaded = await core_client.core_json(
                config.DATA_URL, f"/objects?record_id={record['id']}", identity, "POST",
                files={"file": (photo.filename or "photo", photo_bytes, photo.content_type)},
            )
            payload["attachment_ids"] = [uploaded["id"]]
        except HTTPException:
            warnings.append("Ảnh chưa được tải lên.")
    instance = None
    try:
        instance = await core_client.core_json(
            config.WORKFLOW_URL, "/instances", identity, "POST",
            json_body={"definition_key": "report-handling", "reference_id": record["id"]},
        )
        payload["workflow_id"] = instance["id"]
    except HTTPException:
        warnings.append("Quy trình chưa khởi tạo; có thể thử lại trong chi tiết phản ánh.")
    if payload != record["payload"]:
        try:
            record = await core_client.core_json(config.DATA_URL, f"/records/{record['id']}", identity, "PATCH", json_body={"payload": payload})
        except HTTPException:
            warnings.append("Một số thông tin liên kết chưa đồng bộ.")
    with closing(report_db()) as connection:
        with connection:
            add_notification(connection, identity.tenant, record["id"], "dispatcher", "reports",
                             "new_report", "Phản ánh mới cần phân công",
                             f"Hồ sơ #{record['id'][:8]} đang chờ chọn đơn vị xử lý.")
    return {**report_view(record, instance), "warnings": warnings}


@router.get("/reports/{report_id}")
async def get_report(report_id: str, identity: Caller = Depends(caller)) -> dict:
    record = await get_report_record(report_id, identity)
    instance = await find_instance(report_id, identity)
    if instance:
        instance = await core_client.core_json(config.WORKFLOW_URL, f"/instances/{instance['id']}", identity)
    return report_view_with_routing(record, instance, routing_for(report_id, identity.tenant))


@router.post("/reports/{report_id}/retry-workflow")
async def retry_workflow(report_id: str, identity: Caller = Depends(caller)) -> dict:
    record = await get_report_record(report_id, identity)
    instance = await find_instance(report_id, identity)
    if instance is None:
        instance = await core_client.core_json(config.WORKFLOW_URL, "/instances", identity, "POST", json_body={"definition_key": "report-handling", "reference_id": report_id})
    return report_view_with_routing(record, instance, routing_for(report_id, identity.tenant))


@router.post("/reports/{report_id}/actions/{action}")
async def take_action(report_id: str, action: str, identity: Caller = Depends(caller)) -> dict:
    require_manager(identity, "reports")
    if action != "resolve":
        raise HTTPException(status_code=404, detail="Unknown action")
    record = await get_report_record(report_id, identity)
    routing = routing_for(report_id, identity.tenant)
    if not routing or not routing["accepted_at"] or routing["pending_unit"]:
        raise HTTPException(status_code=409, detail="Report must be accepted by its assigned unit")
    if "admin" not in identity.roles and not (
        "reports_operator" in identity.roles and identity.unit == routing["unit_id"]
    ):
        raise HTTPException(status_code=403, detail="Assigned unit role required")
    instance = await find_instance(report_id, identity)
    if instance is None or instance["state"] != "assigned":
        raise HTTPException(status_code=409, detail="Report is not ready to resolve")
    instance = await core_client.core_json(config.WORKFLOW_URL, f"/instances/{instance['id']}/actions/{action}", identity, "POST")
    with closing(report_db()) as connection:
        with connection:
            add_report_event(connection, report_id, identity, "resolved", to_unit=routing["unit_id"])
            add_notification(connection, identity.tenant, report_id, "user", record["created_by"],
                             "resolved", "Phản ánh đã hoàn tất", "Đơn vị đã hoàn tất xử lý phản ánh của bạn.")
            add_notification(connection, identity.tenant, report_id, "dispatcher", "reports",
                             "resolved", "Hồ sơ đã hoàn tất", "Đơn vị đã hoàn tất xử lý hồ sơ.")
    return report_view_with_routing(record, instance, routing_for(report_id, identity.tenant))


@router.post("/reports/{report_id}/dispatch")
async def dispatch_report(report_id: str, body: DispatchInput, identity: Caller = Depends(caller)) -> dict:
    if not can_dispatch(identity):
        raise HTTPException(status_code=403, detail="reports_dispatcher role required")
    if body.due_at.tzinfo is None or body.due_at <= datetime.now(timezone.utc):
        raise HTTPException(status_code=422, detail="Due date must be in the future with a timezone")
    note = body.note.strip()
    if len(note) < 3:
        raise HTTPException(status_code=422, detail="Dispatch note is required")
    record = await get_report_record(report_id, identity)
    instance = await find_instance(report_id, identity)
    if instance is None:
        raise HTTPException(status_code=409, detail="Report workflow has not started")
    if instance["state"] == "resolved":
        raise HTTPException(status_code=409, detail="Resolved reports cannot be reassigned")
    if instance["state"] == "submitted":
        instance = await core_client.core_json(config.WORKFLOW_URL, f"/instances/{instance['id']}/actions/triage", identity, "POST")
    if instance["state"] == "triaged":
        instance = await core_client.core_json(config.WORKFLOW_URL, f"/instances/{instance['id']}/actions/assign", identity, "POST")
    now = datetime.now(timezone.utc).isoformat()
    with closing(report_db()) as connection:
        with connection:
            connection.execute("BEGIN IMMEDIATE")
            previous = connection.execute(
                "SELECT unit_id FROM report_assignments WHERE report_id = ? AND tenant = ?",
                (report_id, identity.tenant),
            ).fetchone()
            connection.execute("""
                INSERT INTO report_assignments
                  (report_id, tenant, unit_id, due_at, assigned_at, assigned_by)
                VALUES (?, ?, ?, ?, ?, ?)
                ON CONFLICT(report_id) DO UPDATE SET
                  unit_id = excluded.unit_id, due_at = excluded.due_at,
                  assigned_at = excluded.assigned_at, assigned_by = excluded.assigned_by,
                  accepted_at = NULL, accepted_by = NULL, pending_unit = NULL,
                  pending_reason = NULL, requested_at = NULL, requested_by = NULL
            """, (report_id, identity.tenant, body.unit_id, body.due_at.isoformat(), now, identity.user))
            add_report_event(connection, report_id, identity,
                             "reassigned" if previous else "assigned",
                             from_unit=previous["unit_id"] if previous else None,
                             to_unit=body.unit_id, note=note)
            add_notification(connection, identity.tenant, report_id, "unit", body.unit_id,
                             "reassigned" if previous else "assigned", "Hồ sơ được giao xử lý",
                             f"Hồ sơ #{report_id[:8]} đã được giao cho đơn vị của bạn.")
            add_notification(connection, identity.tenant, report_id, "user", record["created_by"],
                             "reassigned" if previous else "assigned", "Phản ánh đã được phân công",
                             "Phản ánh của bạn đã được chuyển đến đơn vị xử lý.")
    return report_view_with_routing(record, instance, routing_for(report_id, identity.tenant))


@router.post("/reports/{report_id}/accept")
async def accept_report(report_id: str, identity: Caller = Depends(caller)) -> dict:
    require_manager(identity, "reports")
    if can_dispatch(identity) and "reports_operator" not in identity.roles and "admin" not in identity.roles:
        raise HTTPException(status_code=403, detail="Assigned unit role required")
    record = await get_report_record(report_id, identity)
    instance = await find_instance(report_id, identity)
    if instance is None or instance["state"] != "assigned":
        raise HTTPException(status_code=409, detail="Report is not assigned")
    with closing(report_db()) as connection:
        with connection:
            connection.execute("BEGIN IMMEDIATE")
            row = connection.execute(
                "SELECT * FROM report_assignments WHERE report_id = ? AND tenant = ?",
                (report_id, identity.tenant),
            ).fetchone()
            if row is None or ("admin" not in identity.roles and row["unit_id"] != identity.unit):
                raise HTTPException(status_code=404, detail="Report not assigned to this unit")
            if row["accepted_at"]:
                raise HTTPException(status_code=409, detail="Report already accepted")
            connection.execute(
                "UPDATE report_assignments SET accepted_at = ?, accepted_by = ? WHERE report_id = ?",
                (datetime.now(timezone.utc).isoformat(), identity.user, report_id),
            )
            add_report_event(connection, report_id, identity, "accepted", to_unit=row["unit_id"])
            add_notification(connection, identity.tenant, report_id, "user", record["created_by"],
                             "accepted", "Đơn vị đã nhận phản ánh",
                             "Đơn vị được phân công đã nhận xử lý phản ánh của bạn.")
    return report_view_with_routing(record, instance, routing_for(report_id, identity.tenant))


@router.post("/reports/{report_id}/transfer-request")
async def request_transfer(report_id: str, body: TransferInput, identity: Caller = Depends(caller)) -> dict:
    require_manager(identity, "reports")
    if can_dispatch(identity) and "reports_operator" not in identity.roles and "admin" not in identity.roles:
        raise HTTPException(status_code=403, detail="Assigned unit role required")
    record = await get_report_record(report_id, identity)
    instance = await find_instance(report_id, identity)
    if instance is None or instance["state"] != "assigned":
        raise HTTPException(status_code=409, detail="Report is not assigned")
    reason = body.reason.strip()
    if len(reason) < 5:
        raise HTTPException(status_code=422, detail="Transfer reason is required")
    with closing(report_db()) as connection:
        with connection:
            connection.execute("BEGIN IMMEDIATE")
            row = connection.execute(
                "SELECT * FROM report_assignments WHERE report_id = ? AND tenant = ?",
                (report_id, identity.tenant),
            ).fetchone()
            if row is None or ("admin" not in identity.roles and row["unit_id"] != identity.unit):
                raise HTTPException(status_code=404, detail="Report not assigned to this unit")
            if body.unit_id == row["unit_id"]:
                raise HTTPException(status_code=422, detail="Choose another unit")
            if row["pending_unit"]:
                raise HTTPException(status_code=409, detail="Transfer request already pending")
            connection.execute("""
                UPDATE report_assignments SET pending_unit = ?, pending_reason = ?,
                  requested_at = ?, requested_by = ? WHERE report_id = ?
            """, (body.unit_id, reason, datetime.now(timezone.utc).isoformat(), identity.user, report_id))
            add_report_event(connection, report_id, identity, "transfer_requested",
                             from_unit=row["unit_id"], to_unit=body.unit_id, note=reason)
            add_notification(connection, identity.tenant, report_id, "dispatcher", "reports",
                             "transfer_requested", "Đề nghị chuyển đơn vị",
                             f"Đơn vị hiện tại đề nghị chuyển hồ sơ #{report_id[:8]}.")
            add_notification(connection, identity.tenant, report_id, "user", record["created_by"],
                             "transfer_requested", "Phản ánh đang được xem xét chuyển đơn vị",
                             "Đơn vị xử lý đã đề nghị chuyển phản ánh của bạn.")
    return report_view_with_routing(record, instance, routing_for(report_id, identity.tenant))


@router.post("/reports/{report_id}/progress")
async def update_report_progress(report_id: str, body: NoteInput, identity: Caller = Depends(caller)) -> dict:
    require_manager(identity, "reports")
    record = await get_report_record(report_id, identity)
    instance = await find_instance(report_id, identity)
    if instance is None or instance["state"] != "assigned":
        raise HTTPException(status_code=409, detail="Report is not being handled")
    note = body.note.strip()
    if len(note) < 3:
        raise HTTPException(status_code=422, detail="Progress note is required")
    with closing(report_db()) as connection:
        with connection:
            connection.execute("BEGIN IMMEDIATE")
            row = connection.execute(
                "SELECT * FROM report_assignments WHERE report_id = ? AND tenant = ?",
                (report_id, identity.tenant),
            ).fetchone()
            if row is None or ("admin" not in identity.roles and (
                "reports_operator" not in identity.roles or row["unit_id"] != identity.unit
            )):
                raise HTTPException(status_code=404, detail="Report not assigned to this unit")
            if not row["accepted_at"] or row["pending_unit"]:
                raise HTTPException(status_code=409, detail="Accept the report before posting progress")
            add_report_event(connection, report_id, identity, "progress", to_unit=row["unit_id"], note=note)
            add_notification(connection, identity.tenant, report_id, "user", record["created_by"],
                             "progress", "Phản ánh có tiến độ mới", note)
    return report_view_with_routing(record, instance, routing_for(report_id, identity.tenant))


@router.post("/reports/{report_id}/transfer-request/reject")
async def reject_transfer(report_id: str, body: NoteInput, identity: Caller = Depends(caller)) -> dict:
    if not can_dispatch(identity):
        raise HTTPException(status_code=403, detail="reports_dispatcher role required")
    record = await get_report_record(report_id, identity)
    note = body.note.strip()
    if len(note) < 3:
        raise HTTPException(status_code=422, detail="Reason is required")
    with closing(report_db()) as connection:
        with connection:
            connection.execute("BEGIN IMMEDIATE")
            row = connection.execute(
                "SELECT * FROM report_assignments WHERE report_id = ? AND tenant = ?",
                (report_id, identity.tenant),
            ).fetchone()
            if row is None or not row["pending_unit"]:
                raise HTTPException(status_code=409, detail="No transfer request pending")
            connection.execute("""
                UPDATE report_assignments SET pending_unit = NULL, pending_reason = NULL,
                  requested_at = NULL, requested_by = NULL WHERE report_id = ?
            """, (report_id,))
            add_report_event(connection, report_id, identity, "transfer_rejected",
                             from_unit=row["unit_id"], to_unit=row["pending_unit"], note=note)
            add_notification(connection, identity.tenant, report_id, "unit", row["unit_id"],
                             "transfer_rejected", "Đề nghị chuyển đã bị từ chối", note)
            add_notification(connection, identity.tenant, report_id, "user", record["created_by"],
                             "transfer_rejected", "Phản ánh tiếp tục do đơn vị hiện tại xử lý",
                             "Đề nghị chuyển đơn vị đã được xem xét và từ chối.")
    instance = await find_instance(report_id, identity)
    return report_view_with_routing(record, instance, routing_for(report_id, identity.tenant))


@router.get("/reports/{report_id}/attachments/{object_id}")
async def report_attachment(report_id: str, object_id: str, identity: Caller = Depends(caller)) -> Response:
    record = await get_report_record(report_id, identity)
    if object_id not in record["payload"].get("attachment_ids", []):
        raise HTTPException(status_code=404, detail="Attachment not found")
    response = await core_client.core_response(config.DATA_URL, f"/objects/{object_id}", identity)
    return Response(content=response.content, media_type=response.headers.get("content-type", "application/octet-stream"))
