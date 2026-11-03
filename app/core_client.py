# SPDX-License-Identifier: Apache-2.0
import httpx
from fastapi import HTTPException

from app import config
from app.security import Caller, can_manage


def core_headers(identity: Caller) -> dict[str, str]:
    # Only this business API may delegate report access to the generic core.
    # The gateway denies browser/mobile access to generic core routes.
    core_roles = set(identity.roles) - {"operator"}
    if can_manage(identity, "reports"):
        core_roles.add("operator")
    return {
        "X-Internal-Secret": config.INTERNAL_SECRET,
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
