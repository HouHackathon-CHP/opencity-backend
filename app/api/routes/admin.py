# SPDX-License-Identifier: Apache-2.0
"""Admin-only overview of tenant operations."""

from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException

from app.core.security import Caller, caller
from app.services.admin import local_counts
from app.services.reports import report_dashboard, visible_report_views


router = APIRouter()


@router.get("/admin/overview")
async def overview(identity: Caller = Depends(caller)) -> dict:
    if "admin" not in identity.roles:
        raise HTTPException(status_code=403, detail="admin role required")
    now = datetime.now(timezone.utc)
    reports = report_dashboard(await visible_report_views(identity), now)["counts"]
    return {"generated_at": now.isoformat(), "reports": reports,
            **local_counts(identity.tenant)}
