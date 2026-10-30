# OpenCity Backend — domain API

Business API for the [OpenCity frontend](https://github.com/HouHackathon-CHP/opencity-frontend) and [citizen mobile app](https://github.com/HouHackathon-CHP/opencity-mobile), deployed **behind** the [DX-OS Core](https://github.com/HouHackathon-CHP/dxos-core) gateway. Each application component lives in its own repository. The core remains headless and reusable.

## Responsibilities

- Validate field report data and image size/type.
- Compose a tenant-scoped data record, optional stored object, and `report-handling` workflow instance.
- Return one domain response to the frontend instead of exposing the data/workflow APIs as its application contract.
- Dispatch reports across units with deadlines, acceptance, progress notes, transfer requests and an audit trail. Enforce tenant, owner and assigned-unit access on every report and attachment request.
- Store report notifications for citizens, assigned units and dispatchers, with per-user read state and idempotent deadline reminders.
- Publish tenant-scoped news and alerts for citizen apps. Only `bulletins_operator` or `admin` can publish; all authenticated members of that tenant can read.
- Run tenant-scoped, single-choice surveys. `surveys_operator` or `admin` can publish and close them; each account can answer once.
- Summarize visible reports for the staff SLA dashboard: state counts, unassigned cases, next-24-hour deadlines, overdue cases, unit workload and a priority queue. The API applies the same report visibility rules before aggregating.

## Local stack

Keep `dxos-core`, `opencity-frontend` and `opencity-backend` as sibling directories. From this directory:

```powershell
docker compose --env-file ..\dxos-core\.env -f ..\dxos-core\compose.yaml -f compose.stack.yaml up --build -d
python ..\dxos-core\scripts\smoke.py
python scripts\smoke_app.py
python scripts\seed_dashboard_demo.py
```

The first command adds an internal `opencity-backend` service and configures the core gateway's optional `opencity` upstream. This backend has no published port. Browser requests use `http://localhost:8000/api/opencity/...` and must carry a valid Keycloak access token. The gateway injects identity headers; direct unauthenticated calls to this backend fail.

Run `python scripts/provision_roles.py` after the core smoke script to create local demo staff accounts: `dxos-dispatcher`, `dxos-reports` (infrastructure), `dxos-reports-environment`, `dxos-bulletins`, and `dxos-surveys`. They share the local `DEMO_OPERATOR_PASSWORD` from `dxos-core/.env`. This script is idempotent and also runs at the start of `scripts/smoke_app.py`. For real staff, assign the `reports_dispatcher` role to intake coordinators, or the `reports_operator` role and an admin-managed `unit_id` attribute to unit handlers. Supported units are `infrastructure`, `environment`, `transport`, and `intake`. Other feature roles need no unit attribute. `admin` grants all three features and all report units. The core's legacy `operator` role grants no OpenCity management permission.

`GET /me/capabilities` returns management features, report unit and dispatcher capability. Citizens see their own reports; dispatchers see all reports in their tenant; unit handlers see only reports explicitly assigned to their unit. The category suggests an initial unit (`Hạ tầng`/`Chiếu sáng` → `infrastructure`; `Môi trường`/`Cây xanh` → `environment`; `Giao thông` → `transport`; `Khác` → `intake`), but does not grant that unit access. Existing reports without a saved assignment appear in the dispatcher inbox until dispatched. The backend checks unit scope again on details, attachments, workflow retry and actions. The web hides unauthorized routes, while API checks remain authoritative.

The coordinator dispatches with `unit_id`, a timezone-aware future `due_at`, and a note. This advances the core workflow to `assigned` and saves the routing decision in `report-routing.sqlite3` on the local persistent volume. The unit accepts, posts progress notes and resolves, or requests transfer to another unit. The coordinator reassigns or rejects the request. Reassignment revokes the old unit's access. Notes and routing events are included in the citizen-visible history, so staff must write public-facing text. The web report inbox can filter overdue cases. SQLite is for the local single-instance prototype; a multi-replica deployment needs a shared transactional database.

`GET /notifications` returns the 100 latest in-app notices visible to the caller. New reports notify dispatchers; dispatch and workflow updates notify the citizen and relevant staff. Unit notices stop being visible when a report moves away from that unit. `POST /notifications/{id}/read` marks a notice read for the current account only. Listing also creates deduplicated reminders for cases due within 24 hours or already overdue. This is an in-app inbox, not an OS push service or a background scheduler; reminders are materialized when a signed-in client polls the API.

### Routes

| Method | Route | Purpose |
| --- | --- | --- |
| `GET` | `/me/capabilities` | List the caller's management features |
| `GET` | `/notifications` | List visible in-app notices and materialize deadline reminders |
| `POST` | `/notifications/{id}/read` | Mark a visible notice read for this account |
| `GET` | `/reports` | List reports visible to the caller |
| `GET` | `/reports/dashboard` | Staff-only scoped SLA summary and priority queue |
| `POST` | `/reports` | Create a report (multipart form, optional photo) |
| `GET` | `/reports/{id}` | Report and workflow history |
| `POST` | `/reports/{id}/dispatch` | Coordinator assigns/reassigns unit and deadline |
| `POST` | `/reports/{id}/accept` | Assigned unit accepts work |
| `POST` | `/reports/{id}/progress` | Accepted unit posts a public progress note |
| `POST` | `/reports/{id}/transfer-request` | Assigned unit requests another unit |
| `POST` | `/reports/{id}/transfer-request/reject` | Coordinator rejects transfer with a reason |
| `POST` | `/reports/{id}/actions/resolve` | Accepted unit completes the report |
| `POST` | `/reports/{id}/retry-workflow` | Recover a saved record without a workflow |
| `GET` | `/reports/{id}/attachments/{object_id}` | Download a report's permitted image |
| `GET` | `/bulletins`, `/bulletins/{id}` | Read tenant-scoped news and alerts |
| `POST` | `/bulletins` | Publish a news item or alert (`bulletins_operator`) |
| `GET` | `/surveys`, `/surveys/{id}` | Read tenant surveys and permitted results |
| `POST` | `/surveys` | Publish a survey with 2–8 options (`surveys_operator`) |
| `POST` | `/surveys/{id}/answers` | Answer once with an option ID |
| `POST` | `/surveys/{id}/close` | Close a survey (`surveys_operator`) |

The gateway prefixes these with `/api/opencity`.

`seed_dashboard_demo.py` inserts five `[DEMO SLA]` reports at different Hanoi coordinates, dispatches four of them with different future deadlines, and leaves one awaiting dispatch. It is idempotent. The short deadlines become overdue naturally if the stack remains running; the script never rewrites existing deadlines.

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
