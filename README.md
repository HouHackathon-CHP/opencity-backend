# OpenCity Backend — domain API

Business API for the [OpenCity frontend](https://github.com/HouHackathon-CHP/opencity-frontend) and [citizen mobile app](https://github.com/HouHackathon-CHP/opencity-mobile), deployed **behind** the [DX-OS Core](https://github.com/HouHackathon-CHP/dxos-core) gateway. Each application component lives in its own repository. The core remains headless and reusable.

## Responsibilities

- Validate field report data and image size/type.
- Compose a tenant-scoped data record, optional stored object, and `report-handling` workflow instance.
- Return one domain response to the frontend instead of exposing the data/workflow APIs as its application contract.
- Restrict management actions by feature role and report/image access by tenant and owner. The backend delegates report management to the generic core only after checking `reports_operator`.
- Publish tenant-scoped news and alerts for citizen apps. Only `bulletins_operator` or `admin` can publish; all authenticated members of that tenant can read.
- Run tenant-scoped, single-choice surveys. `surveys_operator` or `admin` can publish and close them; each account can answer once.

## Local stack

Keep `dxos-core`, `opencity-frontend` and `opencity-backend` as sibling directories. From this directory:

```powershell
docker compose --env-file ..\dxos-core\.env -f ..\dxos-core\compose.yaml -f compose.stack.yaml up --build -d
python ..\dxos-core\scripts\smoke.py
python scripts\smoke_app.py
```

The first command adds an internal `opencity-backend` service and configures the core gateway's optional `opencity` upstream. This backend has no published port. Browser requests use `http://localhost:8000/api/opencity/...` and must carry a valid Keycloak access token. The gateway injects identity headers; direct unauthenticated calls to this backend fail.

Run `python scripts/provision_roles.py` after the core smoke script to create local demo staff accounts: `dxos-reports` (infrastructure), `dxos-reports-environment`, `dxos-bulletins`, and `dxos-surveys`. They share the local `DEMO_OPERATOR_PASSWORD` from `dxos-core/.env`. This script is idempotent and also runs at the start of `scripts/smoke_app.py`. For real report staff, assign the `reports_operator` realm role and an admin-managed `unit_id` attribute. The supported units are `infrastructure`, `environment`, `transport`, and `intake`. Other feature roles need no unit attribute. `admin` grants all three features and all report units. The core's legacy `operator` role grants no OpenCity management permission.

`GET /me/capabilities` returns the authenticated caller's management features and report unit. Public news and surveys remain readable by authenticated citizens. Report lists contain the caller's own cases or, for `reports_operator`, cases routed to that unit in the caller's tenant. Categories route as follows: `Hạ tầng`/`Chiếu sáng` → `infrastructure`; `Môi trường`/`Cây xanh` → `environment`; `Giao thông` → `transport`; `Khác` → `intake`. This deterministic mapping also covers reports created before the unit claim was introduced. The backend checks unit scope again on details, attachments, workflow retry, and actions. The web hides unauthorized staff routes, while API checks remain authoritative.

### Routes

| Method | Route | Purpose |
| --- | --- | --- |
| `GET` | `/me/capabilities` | List the caller's management features |
| `GET` | `/reports` | List reports visible to the caller |
| `POST` | `/reports` | Create a report (multipart form, optional photo) |
| `GET` | `/reports/{id}` | Report and workflow history |
| `POST` | `/reports/{id}/actions/{action}` | `reports_operator` transition: triage, assign, resolve |
| `POST` | `/reports/{id}/retry-workflow` | Recover a saved record without a workflow |
| `GET` | `/reports/{id}/attachments/{object_id}` | Download a report's permitted image |
| `GET` | `/bulletins`, `/bulletins/{id}` | Read tenant-scoped news and alerts |
| `POST` | `/bulletins` | Publish a news item or alert (`bulletins_operator`) |
| `GET` | `/surveys`, `/surveys/{id}` | Read tenant surveys and permitted results |
| `POST` | `/surveys` | Publish a survey with 2–8 options (`surveys_operator`) |
| `POST` | `/surveys/{id}/answers` | Answer once with an option ID |
| `POST` | `/surveys/{id}/close` | Close a survey (`surveys_operator`) |

The gateway prefixes these with `/api/opencity`.

Bulletins use a separate persistent SQLite volume in the local Compose stack. They are entered by an operator; no official news feed is bundled. `POST /bulletins` accepts `category` (`news` or `alert`), `title`, `summary`, `body`, and optional `area`, `latitude`, `longitude`. The smoke script inserts one clearly marked `[DEMO]` alert if it is absent, so the mobile map and feed can be tested.

Surveys use a separate SQLite file in that persistent volume. The API enforces one answer per user and validates that the chosen option belongs to the survey. Citizens see vote totals only after they answer or the survey closes; operators see totals while it is open. `smoke_app.py` seeds one `[DEMO]` survey without submitting an answer for the citizen account.

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
