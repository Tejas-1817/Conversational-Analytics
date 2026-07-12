# API Conventions

- REST, resource-oriented: plural nouns (`/sources`, `/jobs`), actions as sub-resources (`/sources/{id}/test`).
- Pydantic DTOs in `app/schemas.py` for all request/response bodies; never return ORM objects without a response_model.
- Secrets go IN via DTOs, never OUT: no credential field on any response model.
- Async work returns 202 + job resource; clients poll `/jobs/{id}`. Never block a request on long work.
- Errors: 400 validation/user-fixable, 401 auth, 404 missing, 409 conflict (e.g. job already running), 500 only for genuine bugs. Detail messages must tell the caller what to DO.
- Breaking changes to a shipped endpoint require a versioned path (`/v2/...`) and an ADR.
