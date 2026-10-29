# SPDX-License-Identifier: Apache-2.0
"""Create local OpenCity demo roles and accounts in an existing Keycloak realm."""

import json
from pathlib import Path
from urllib.error import HTTPError
from urllib.parse import urlencode
from urllib.request import Request, urlopen


ROOT = Path(__file__).resolve().parents[2]
IDENTITY = "http://localhost:8081"
ROLES = {
    "dxos-reports": "reports_operator",
    "dxos-bulletins": "bulletins_operator",
    "dxos-surveys": "surveys_operator",
}


def request(method: str, url: str, *, token: str | None = None, body: dict | list | None = None):
    payload = json.dumps(body).encode() if body is not None else None
    headers = {"Content-Type": "application/json"} if payload is not None else {}
    if token:
        headers["Authorization"] = f"Bearer {token}"
    try:
        with urlopen(Request(url, data=payload, headers=headers, method=method), timeout=20) as response:
            data = response.read()
            return response.status, json.loads(data) if data else None
    except HTTPError as error:
        data = error.read()
        try:
            detail = json.loads(data) if data else None
        except ValueError:
            detail = data.decode(errors="replace")
        return error.code, detail


def require(status: int, expected: int, detail: object) -> None:
    if status != expected:
        raise RuntimeError(f"Keycloak returned {status}, expected {expected}: {detail}")


def env_values() -> dict[str, str]:
    values = {}
    for line in (ROOT / "dxos-core" / ".env").read_text(encoding="utf-8").splitlines():
        if line.strip() and not line.lstrip().startswith("#"):
            key, value = line.split("=", 1)
            values[key] = value
    return values


def admin_token(password: str) -> str:
    form = urlencode({"grant_type": "password", "client_id": "admin-cli",
                      "username": "admin", "password": password}).encode()
    with urlopen(Request(f"{IDENTITY}/realms/master/protocol/openid-connect/token",
                         data=form, headers={"Content-Type": "application/x-www-form-urlencoded"}), timeout=20) as response:
        return json.load(response)["access_token"]


def provision() -> None:
    values = env_values()
    password = values["DEMO_OPERATOR_PASSWORD"]
    admin_password = values["KEYCLOAK_ADMIN_PASSWORD"]
    admin = admin_token(admin_password)

    def authorized(method: str, url: str, *, body: dict | list | None = None):
        nonlocal admin
        status, result = request(method, url, token=admin, body=body)
        if status == 401:
            admin = admin_token(admin_password)
            return request(method, url, token=admin, body=body)
        return status, result

    base = f"{IDENTITY}/admin/realms/dxos"
    for username, role in ROLES.items():
        status, existing = authorized("GET", f"{base}/roles/{role}")
        if status == 404:
            status, detail = authorized("POST", f"{base}/roles",
                                        body={"name": role, "description": "OpenCity feature management"})
            require(status, 201, detail)
        else:
            require(status, 200, existing)
        status, role_data = authorized("GET", f"{base}/roles/{role}")
        require(status, 200, role_data)
        url = f"{base}/users?{urlencode({'username': username, 'exact': 'true'})}"
        status, users = authorized("GET", url)
        require(status, 200, users)
        if not users:
            status, detail = authorized("POST", f"{base}/users", body={
                "username": username, "enabled": True, "firstName": "OpenCity",
                "lastName": role, "email": f"{username}@example.invalid", "emailVerified": True,
                "attributes": {"tenant_id": ["demo"]},
            })
            require(status, 201, detail)
            status, users = authorized("GET", url)
            require(status, 200, users)
        user_id = users[0]["id"]
        status, detail = authorized("PUT", f"{base}/users/{user_id}", body={
            "username": username, "enabled": True, "firstName": "OpenCity",
            "lastName": role, "email": f"{username}@example.invalid", "emailVerified": True,
            "requiredActions": [], "attributes": {"tenant_id": ["demo"]},
        })
        require(status, 204, detail)
        status, detail = authorized("PUT", f"{base}/users/{user_id}/reset-password", body={
            "type": "password", "value": password, "temporary": False,
        })
        require(status, 204, detail)
        status, current_roles = authorized("GET", f"{base}/users/{user_id}/role-mappings/realm")
        require(status, 200, current_roles)
        stale = [item for item in current_roles if item["name"] in set(ROLES.values()) | {"operator", "admin"} and item["name"] != role]
        if stale:
            status, detail = authorized("DELETE", f"{base}/users/{user_id}/role-mappings/realm", body=stale)
            require(status, 204, detail)
        if role not in {item["name"] for item in current_roles}:
            status, detail = authorized("POST", f"{base}/users/{user_id}/role-mappings/realm", body=[role_data])
            require(status, 204, detail)
    print("OpenCity role accounts are ready: " + ", ".join(ROLES))


if __name__ == "__main__":
    provision()
