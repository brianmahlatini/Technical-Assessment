"""Application error helpers.

Why this file exists:
    The API has two different kinds of failures. FastAPI/Pydantic already
    handles syntactic failures, such as a missing required JSON field. The
    application still needs a clear business-error shape for domain failures,
    such as an unknown medicine, a rejected dispense, or a reused idempotency
    key. Keeping that shape in this tiny module means routers and services can
    return errors consistently without rebuilding the same dictionary in many
    places.

How to read this file:
    `api_error` is the single helper used by route handlers when they need to
    stop request processing and return a structured HTTP error response. The
    helper wraps the public Pydantic error schemas, converts them to plain JSON
    data, and gives that data to FastAPI's `HTTPException`.
"""

# FastAPI turns HTTPException into an HTTP response without treating it as an
# unhandled server crash. Routers raise this when a known business condition
# should become a controlled 4xx or 5xx response.
from fastapi import HTTPException

# The error schemas live in `schemas.py` because they are part of the public API
# contract consumed by the Angular frontend. Importing them here keeps the error
# helper aligned with the same response shape documented elsewhere.
from app.schemas import ApiErrorItem, ApiErrorResponse


def api_error(status_code: int, error: str, message: str, details: list[ApiErrorItem] | None = None) -> HTTPException:
    """Build the standard API error response for known business failures.

    Args:
        status_code: HTTP status that should be sent to the client, for example
            `404` for a missing medicine or `409` for an idempotency conflict.
        error: Stable machine-readable category used by clients and tests.
        message: Human-readable summary that can be shown in the UI.
        details: Optional field-level failures. This is where dispense-rule
            rejections can report multiple problems at once.

    Returns:
        A FastAPI `HTTPException` whose `detail` is already JSON-serialisable.
    """
    # Always construct the response through the Pydantic schema so every error
    # has the same keys: `error`, `message`, and `details`.
    payload = ApiErrorResponse(error=error, message=message, details=details or [])

    # `mode="json"` converts nested Pydantic models into built-in Python types
    # that FastAPI can encode directly in the HTTP response body.
    return HTTPException(status_code=status_code, detail=payload.model_dump(mode="json"))

