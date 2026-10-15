"""Database engine and session helpers.

The API uses synchronous SQLAlchemy sessions because the assessment's hard
problems are transactional correctness and constraints, not async throughput.
Each request receives one session and explicitly commits only after the service
has produced a durable outcome.
"""

from collections.abc import Generator

from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from app.config import settings

engine = create_engine(settings.database_url, pool_pre_ping=True, future=True)
SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False, expire_on_commit=False, class_=Session)


def get_session() -> Generator[Session, None, None]:
    """Yield a request-scoped SQLAlchemy session for FastAPI dependencies."""
    session = SessionLocal()
    try:
        yield session
    finally:
        session.close()

