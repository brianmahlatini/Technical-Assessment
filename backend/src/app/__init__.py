"""Application package for the EMGuidance assessment backend.

Why this file exists:
    Python treats `backend/src/app` as an importable package because this file
    is present. That lets the rest of the project use stable imports such as
    `from app.services import ...` in Docker, tests, Alembic, and local tools.

There is intentionally no runtime code here:
    Package initialisers should stay lightweight. Creating database engines,
    importing routers, or starting application work from this file would make
    imports harder to reason about and could surprise tests or migrations.
"""

