# Architecture

The repository is split into `backend/` and `frontend/` because the two parts have different runtime, dependency, and review concerns. The backend owns persistence, historical rule evaluation, idempotency, and concurrency. The frontend owns user workflows: medicine search, medicine detail, dispense capture, and patient ledger.

`docker-compose.yml` starts PostgreSQL, FastAPI, and Angular. The backend container runs `alembic upgrade head` before serving traffic so a clean clone has the schema ready without manual migration steps.

## Backend

FastAPI routes live in `backend/src/app/routers.py`. They are deliberately thin. Business decisions live in `backend/src/app/services.py`, where a dispense request is evaluated against the rule in force at `dispensed_at`, not the rule in force at request time.

The database model is:

- `medicines`: externally supplied medicine code and product facts.
- `formulary_rules`: versioned medicine rules with `effective_from` and optional `effective_to`.
- `dispenses`: accepted dispense records only.
- `dispense_attempts`: accepted and rejected attempts, including rejection reasons.
- `idempotency_records`: cached outcomes for `POST /dispenses`.

PostgreSQL enforces the non-overlap rule with a GiST exclusion constraint over `medicine_id` and the rule period range. Application validation is still useful for nicer errors, but the database is the final authority under concurrent writes.

For concurrent dispenses, `services.py` takes a PostgreSQL advisory transaction lock scoped to `(patient_ref, medicine)`. The lock is held only while reading the rolling 30-day total and inserting the accepted dispense or rejected attempt. This prevents two simultaneous requests from both seeing the same total and jointly breaching the formulary limit.

All timestamps are stored as UTC. The rolling 30-day window is calculated in `Africa/Johannesburg` in `backend/src/app/timezone.py`, then converted back to UTC for database predicates.

## Frontend

The Angular app is intentionally compact and functional. `frontend/src/main.ts` contains the standalone shell, API client, and four views required by the brief. The UI renders server-side rejection details exactly as returned by the backend so multiple failed rules remain visible to the user.

