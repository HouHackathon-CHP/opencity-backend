# SPDX-License-Identifier: Apache-2.0
"""OpenCity domain API behind the DX-OS gateway."""

from fastapi import Depends, FastAPI

from app import config
from app.security import Caller, caller, can_manage, can_dispatch
from app.reports.router import router as reports_router
from app.notifications.router import router as notifications_router
from app.bulletins.router import router as bulletins_router
from app.surveys.router import router as surveys_router


app = FastAPI(title="OpenCity Domain API", docs_url=None, redoc_url=None)


@app.get("/health")
def health() -> dict:
    return {"status": "ok", "service": "opencity-backend"}


@app.get("/me/capabilities")
def my_capabilities(identity: Caller = Depends(caller)) -> dict:
    return {
        "management": [feature for feature in config.MANAGEMENT_ROLES if can_manage(identity, feature)],
        "report_unit": identity.unit if can_manage(identity, "reports") and "admin" not in identity.roles else None,
        "report_dispatcher": can_dispatch(identity),
    }


app.include_router(notifications_router)
app.include_router(bulletins_router)
app.include_router(surveys_router)
app.include_router(reports_router)
