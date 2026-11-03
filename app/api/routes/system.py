# SPDX-License-Identifier: Apache-2.0
"""Health and current-caller capabilities endpoints."""

from fastapi import APIRouter, Depends

from app.core import config
from app.core.security import Caller, caller, can_dispatch, can_manage


router = APIRouter()


@router.get("/health")
def health() -> dict:
    return {"status": "ok", "service": "opencity-backend"}


@router.get("/me/capabilities")
def my_capabilities(identity: Caller = Depends(caller)) -> dict:
    return {
        "management": [feature for feature in config.MANAGEMENT_ROLES if can_manage(identity, feature)],
        "report_unit": identity.unit if can_manage(identity, "reports") and "admin" not in identity.roles else None,
        "report_dispatcher": can_dispatch(identity),
    }
