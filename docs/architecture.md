# Backend code layout

The OpenCity API uses a feature-first FastAPI layout. A feature owns its HTTP
routes, request schemas and persistence code. Cross-feature infrastructure stays
at the root of `app/`.

```text
app/
  main.py              FastAPI construction, health, router registration
  config.py            Environment-backed settings and shared constants
  security.py          Gateway identity context and feature permissions
  core_client.py       Calls to the headless DX-OS data/workflow services
  reports/
    router.py          Report HTTP routes and orchestration
    schemas.py         Dispatch, transfer and note request models
    service.py         Report visibility, views and SLA aggregation
    storage.py         Local routing and audit tables
  notifications/
    router.py          Inbox HTTP routes
    service.py         Recipients, read views and deadline reminders
  bulletins/
    router.py          Bulletin HTTP routes
    schemas.py         Publication request model
    storage.py         Bulletin table and view
  surveys/
    router.py          Survey HTTP routes
    schemas.py         Publication and answer request models
    storage.py         Survey tables, lookup and result visibility
tests/
  test_api.py          API behavior, permissions and tenant isolation
scripts/               Demo provisioning, smoke and license checks
```

`main.py` registers routers but contains no feature rules. Routers validate HTTP
inputs, enforce permissions and coordinate the feature's service/storage calls.
Services contain reusable domain decisions; storage owns SQL and connection
setup. `security.py` remains the only source of gateway identity and feature-role
rules. The gateway authenticates tokens; this backend verifies the injected
internal secret and applies tenant/unit permissions to every feature operation.

For a new feature, add an `app/<feature>/` package with `router.py`,
`schemas.py` and `storage.py`; add `service.py` when domain decisions are shared
by more than one route. Register its router in `main.py`, add its role to
`config.MANAGEMENT_ROLES` if it has staff actions, document its API contract and
test both permitted and denied access. Keep deployment-time service discovery in
the frontend's catalog manifest; the backend does not load arbitrary plugin code
at runtime.

This refactor changes Python module locations only. Public URL paths and JSON
responses remain the same, so web and Android clients need no change.
