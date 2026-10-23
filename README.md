# OpenCity Backend — domain API

Business API for the [OpenCity frontend](https://github.com/HouHackathon-CHP/opencity-frontend), deployed **behind** the [DX-OS Core](https://github.com/HouHackathon-CHP/dxos-core) gateway. The frontend and backend live in separate repositories. The core remains headless and reusable.

## Responsibilities

- Validate field report data and image size/type.
- Compose a tenant-scoped data record, optional stored object, and `report-handling` workflow instance.
- Return one domain response to the frontend instead of exposing the data/workflow APIs as its application contract.
- Restrict operator actions and image access. DX-OS Core independently enforces its tenant and role policy.

## Local stack

Keep `dxos-core`, `opencity-frontend` and `opencity-backend` as sibling directories. From this directory:

```powershell
docker compose --env-file ..\dxos-core\.env -f ..\dxos-core\compose.yaml -f compose.stack.yaml up --build -d
python ..\dxos-core\scripts\smoke.py
python scripts\smoke_app.py
```

The first command adds an internal `opencity-backend` service and configures the core gateway's optional `opencity` upstream. This backend has no published port. Browser requests use `http://localhost:8000/api/opencity/...` and must carry a valid Keycloak access token. The gateway injects identity headers; direct unauthenticated calls to this backend fail.

### Routes

| Method | Route | Purpose |
| --- | --- | --- |
| `GET` | `/reports` | List reports visible to the caller |
| `POST` | `/reports` | Create a report (multipart form, optional photo) |
| `GET` | `/reports/{id}` | Report and workflow history |
| `POST` | `/reports/{id}/actions/{action}` | Operator transition: triage, assign, resolve |
| `POST` | `/reports/{id}/retry-workflow` | Recover a saved record without a workflow |
| `GET` | `/reports/{id}/attachments/{object_id}` | Download a report's permitted image |

The gateway prefixes these with `/api/opencity`.

## Development

```powershell
python -m venv .venv
.venv\Scripts\python -m pip install -r requirements.txt -r requirements-dev.txt
.venv\Scripts\python scripts\check_direct_licenses.py
.venv\Scripts\python -m pytest -q
```

This is a prototype API. The core still needs server-side anti-malware scanning, rate limiting, migration and production secret management. A record is intentionally retained if photo upload or workflow startup fails; the response contains warnings and the workflow can be retried. The backend does not connect to any official government service.

## License

Apache-2.0. The four direct Python packages are pinned and gated against reviewed OSI-approved licenses. See [`docs/license-audit.md`](docs/license-audit.md) for the limit of that check.
