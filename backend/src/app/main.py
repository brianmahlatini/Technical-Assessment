"""FastAPI application assembly.

This file wires middleware and routers only. Keeping the composition small makes
it obvious what runs for every request and prevents business logic from leaking
into framework setup.
"""

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.config import settings
from app.routers import router

app = FastAPI(title="EMGuidance Formulary API", version="0.1.0")

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
    return JSONResponse(status_code=500, content={"error": "internal_error", "message": str(exc), "details": []})


app.include_router(router, prefix=settings.api_prefix)

