"""FastAPI application assembly.

Why this file exists:
    This is the composition root for the backend. It creates the FastAPI app,
    attaches cross-cutting middleware, registers global exception handling, and
    mounts the API router. Business rules deliberately live in `services.py` so
    this file stays focused on application wiring.

Review guide:
    If a change affects every request, it belongs here. If a change affects one
    endpoint, it belongs in `routers.py`. If a change affects pharmacy logic, it
    belongs in `services.py`.
"""

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.config import settings
from app.routers import router

# The app metadata appears in `/docs`, helping reviewers quickly identify which
# service is running when Docker starts the stack.
app = FastAPI(title="EMGuidance Formulary API", version="0.1.0")

# CORS is configured here because it applies to every browser request before any
# route handler runs. The duplicated localhost value keeps the local Angular
# dev server working even if `FRONTEND_ORIGIN` is not provided.
app.add_middleware(
    CORSMiddleware,
    allow_origins=[settings.frontend_origin, "http://localhost:4200"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.exception_handler(Exception)
async def unhandled_exception_handler(_: Request, exc: Exception) -> JSONResponse:
    """Return a stable error envelope for unexpected failures."""
    # A final fallback prevents raw tracebacks from leaking to the frontend while
    # still returning enough text during local assessment to diagnose failures.
    return JSONResponse(status_code=500, content={"error": "internal_error", "message": str(exc), "details": []})


# Mount every route under the versioned API prefix from configuration. This
# keeps frontend URLs and future API versioning in one place.
app.include_router(router, prefix=settings.api_prefix)

