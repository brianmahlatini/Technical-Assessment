"""Application error helpers.

FastAPI already handles syntactic request validation. This module provides a
small business-error contract so rejected dispenses, idempotency conflicts, and
missing resources all look the same to the Angular frontend.
"""

from fastapi import HTTPException

from app.schemas import ApiErrorItem, ApiErrorResponse


def api_error(status_code: int, error: str, message: str, details: list[ApiErrorItem] | None = None) -> HTTPException:
    """Build a structured HTTPException with JSON-serialisable content."""
    payload = ApiErrorResponse(error=error, message=message, details=details or [])
    return HTTPException(status_code=status_code, detail=payload.model_dump(mode="json"))

