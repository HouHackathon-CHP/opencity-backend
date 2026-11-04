# SPDX-License-Identifier: Apache-2.0
"""Digital ward directory managed by a dedicated operator role."""

import sqlite3
from contextlib import closing
from datetime import datetime, timezone
from uuid import uuid4

from fastapi import APIRouter, Depends, HTTPException

from app.core.security import Caller, caller, can_manage, require_manager
from app.repositories.digital_ward import ward_db
from app.schemas.digital_ward import WardInput


router = APIRouter(prefix="/digital-wards")


def view(row) -> dict:
    result = dict(row)
    result.pop("updated_by", None)
    result["active"] = bool(result["active"])
    return result


def validate(body: WardInput) -> tuple:
    values = (body.code.strip(), body.name.strip(), body.address.strip(), body.phone.strip(),
              body.office_hours.strip(), body.description.strip())
    if any(not value for value in values) or len(values[1]) < 3 or len(values[2]) < 5 or len(values[5]) < 20:
        raise HTTPException(status_code=422, detail="Ward information is incomplete")
    if (body.latitude is None) != (body.longitude is None):
        raise HTTPException(status_code=422, detail="Latitude and longitude must be provided together")
    return values + (body.latitude, body.longitude, int(body.active))


@router.get("")
def list_wards(identity: Caller = Depends(caller)) -> list[dict]:
    manager = can_manage(identity, "digital_ward")
    with closing(ward_db()) as connection:
        rows = connection.execute("SELECT * FROM digital_wards WHERE tenant = ? "
                                  + ("" if manager else "AND active = 1 ")
                                  + "ORDER BY name LIMIT 200", (identity.tenant,)).fetchall()
    return [view(row) for row in rows]


@router.get("/{ward_id}")
def get_ward(ward_id: str, identity: Caller = Depends(caller)) -> dict:
    with closing(ward_db()) as connection:
        row = connection.execute("SELECT * FROM digital_wards WHERE id = ? AND tenant = ?",
                                 (ward_id, identity.tenant)).fetchone()
    if row is None or (not row["active"] and not can_manage(identity, "digital_ward")):
        raise HTTPException(status_code=404, detail="Ward not found")
    return view(row)


@router.post("", status_code=201)
def create_ward(body: WardInput, identity: Caller = Depends(caller)) -> dict:
    require_manager(identity, "digital_ward")
    values = validate(body)
    ward_id = str(uuid4())
    with closing(ward_db()) as connection:
        try:
            with connection:
                connection.execute("INSERT INTO digital_wards "
                                   "(id, tenant, code, name, address, phone, office_hours, description, "
                                   "latitude, longitude, active, updated_at, updated_by) "
                                   "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                                   (ward_id, identity.tenant, *values, datetime.now(timezone.utc).isoformat(), identity.user))
        except sqlite3.IntegrityError as error:
            raise HTTPException(status_code=409, detail="Ward code already exists") from error
        row = connection.execute("SELECT * FROM digital_wards WHERE id = ?", (ward_id,)).fetchone()
    return view(row)


@router.put("/{ward_id}")
def update_ward(ward_id: str, body: WardInput, identity: Caller = Depends(caller)) -> dict:
    require_manager(identity, "digital_ward")
    values = validate(body)
    with closing(ward_db()) as connection:
        if connection.execute("SELECT 1 FROM digital_wards WHERE id = ? AND tenant = ?",
                              (ward_id, identity.tenant)).fetchone() is None:
            raise HTTPException(status_code=404, detail="Ward not found")
        try:
            with connection:
                connection.execute("UPDATE digital_wards SET code = ?, name = ?, address = ?, phone = ?, "
                                   "office_hours = ?, description = ?, latitude = ?, longitude = ?, "
                                   "active = ?, updated_at = ?, updated_by = ? WHERE id = ? AND tenant = ?",
                                   (*values, datetime.now(timezone.utc).isoformat(), identity.user,
                                    ward_id, identity.tenant))
        except sqlite3.IntegrityError as error:
            raise HTTPException(status_code=409, detail="Ward code already exists") from error
        row = connection.execute("SELECT * FROM digital_wards WHERE id = ? AND tenant = ?",
                                 (ward_id, identity.tenant)).fetchone()
    return view(row)
