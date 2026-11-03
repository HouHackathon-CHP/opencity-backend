# SPDX-License-Identifier: Apache-2.0
import hmac
from dataclasses import dataclass

from fastapi import Header, HTTPException

from app import config


@dataclass(frozen=True)
class Caller:
    user: str
    tenant: str
    roles: frozenset[str]
    unit: str | None = None


def can_manage(identity: Caller, feature: str) -> bool:
    if "admin" in identity.roles:
        return True
    if feature == "reports" and "reports_dispatcher" in identity.roles:
        return True
    if config.MANAGEMENT_ROLES[feature] not in identity.roles:
        return False
    return feature != "reports" or identity.unit in config.VALID_UNITS


def can_dispatch(identity: Caller) -> bool:
    return "admin" in identity.roles or "reports_dispatcher" in identity.roles


def require_manager(identity: Caller, feature: str) -> None:
    if not can_manage(identity, feature):
        raise HTTPException(status_code=403, detail=f"{config.MANAGEMENT_ROLES[feature]} role required")


def caller(
    x_internal_secret: str | None = Header(default=None),
    x_dxos_user: str | None = Header(default=None),
    x_dxos_tenant: str | None = Header(default=None),
    x_dxos_roles: str = Header(default=""),
    x_dxos_unit: str | None = Header(default=None),
) -> Caller:
    if not config.INTERNAL_SECRET or not x_internal_secret or not hmac.compare_digest(
        x_internal_secret, config.INTERNAL_SECRET
    ):
        raise HTTPException(status_code=403, detail="Gateway access required")
    if not x_dxos_user or not x_dxos_tenant:
        raise HTTPException(status_code=403, detail="Identity context required")
    return Caller(x_dxos_user, x_dxos_tenant, frozenset(x_dxos_roles.split(",")), x_dxos_unit or None)
