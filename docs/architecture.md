# Backend architecture

OpenCity Backend is a FastAPI application organized by **layer**. This is the
project convention for this repository. FastAPI provides `APIRouter` for larger
applications but does not prescribe one mandatory directory tree. The layout is
similar to GreenMap Backend's `api`, `core`, `schemas`, `services` and persistence
layers, adapted to OpenCity's DX-OS Core integration and local SQLite storage.

```text
app/
  main.py                   Construct FastAPI and register the API router
  api/
    router.py               Register all route modules in one place
    routes/
      system.py             Health and caller capabilities
      reports.py            Report HTTP endpoints
      notifications.py      Inbox HTTP endpoints
      bulletins.py          News and alert HTTP endpoints
      surveys.py            Survey HTTP endpoints
  core/
    config.py               Environment settings and shared constants
    security.py             Gateway identity and feature permissions
    core_client.py          HTTP calls to DX-OS data and workflow services
  schemas/
    reports.py              Dispatch, transfer and note request models
    bulletins.py            Publication request model
    surveys.py              Publication and answer request models
  services/
    reports.py              Report visibility, views and SLA aggregation
    notifications.py        Recipients, read views and deadline reminders
  repositories/
    reports.py              Local routing, audit and inbox SQLite tables
    bulletins.py            Bulletin SQLite table and view
    surveys.py              Survey SQLite tables, lookup and result view
tests/
  test_api.py               API behavior, permissions and tenant isolation
scripts/                    Demo provisioning, smoke and license checks
```

Dependency direction: routes use schemas, services, repositories and core;
services use repositories and core; repositories use core configuration. Keep
HTTP path registration in `api/router.py`. Add a route module for each new area,
and add a schema, service or repository module only when that area needs it.
The gateway authenticates tokens; `core/security.py` verifies its injected
internal secret and applies tenant, unit and feature permissions.

This prototype still has some SQL transactions and workflow orchestration inside
the route handlers, particularly for report transitions. New persistence code
should go in `repositories/`, with business decisions in `services/`. The
current layout change only moves Python modules; it does not change public URL
paths, request or response bodies, or the SQLite files.

There is no SQLAlchemy ORM in this service, so `models/`, `crud/` and
`db/session.py` are intentionally absent. Add those layers if a shared database
session and ORM entities are introduced. DX-OS Core remains a separate headless
service, not a Python package inside this backend. Deployment-time feature
discovery remains in the frontend catalog; this backend does not load arbitrary
plugin code at runtime.
