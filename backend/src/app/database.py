"""Database engine and session helpers.

Why this file exists:
    Database setup is shared by the API, tests, Alembic, and seed script. This
    module creates the SQLAlchemy engine once, configures a session factory, and
    exposes the FastAPI dependency that gives each request its own session.

Design note:
    The backend uses synchronous SQLAlchemy sessions because the assessment's
    hard problem is transactional correctness, especially idempotency and
    rolling-window validation. Keeping the unit of work explicit is easier to
    review than mixing business rules with async session lifecycle code.
"""

from collections.abc import Generator

from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from app.config import settings

# `pool_pre_ping=True` asks SQLAlchemy to check pooled connections before reuse,
# which avoids stale Docker/PostgreSQL connections causing confusing failures.
engine = create_engine(settings.database_url, pool_pre_ping=True, future=True)

# `autoflush=False` keeps writes predictable until the service explicitly needs
# database-generated IDs or constraint checks. `expire_on_commit=False` lets API
# response code read model attributes after commits without forcing reloads.
SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False, expire_on_commit=False, class_=Session)


def get_session() -> Generator[Session, None, None]:
    """Yield a request-scoped SQLAlchemy session for FastAPI dependencies."""
    # Create one session per request so repository/service work shares a single
    # transaction boundary and connection lifecycle.
    session = SessionLocal()
    try:
        yield session
    finally:
        # Always release the connection back to the pool, even when a route or
        # service raises an exception.
        session.close()

