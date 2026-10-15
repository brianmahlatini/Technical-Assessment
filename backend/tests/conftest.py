"""Pytest database fixtures.

The tests run inside the backend container against PostgreSQL so database
constraints, transactions, and advisory locks are exercised for real.
"""

from datetime import UTC, datetime

import pytest
from sqlalchemy import delete

from app.database import SessionLocal
from app.models import Dispense, DispenseAttempt, FormularyRule, IdempotencyRecord, Medicine


@pytest.fixture(autouse=True)
def clean_database():
    """Start every test from an empty schema while keeping migrations intact."""
    with SessionLocal.begin() as session:
        for table in (DispenseAttempt, Dispense, IdempotencyRecord, FormularyRule, Medicine):
            session.execute(delete(table))
    yield
    with SessionLocal.begin() as session:
        for table in (DispenseAttempt, Dispense, IdempotencyRecord, FormularyRule, Medicine):
            session.execute(delete(table))


def make_medicine_with_rule(code: str = "TEST-001", max_once: int = 20, max_30: int = 100, auth: bool = False) -> None:
    """Insert a single active medicine and open-ended formulary rule for tests."""
    with SessionLocal.begin() as session:
        medicine = Medicine(
            code=code,
            name="Test Medicine",
            form="tablet",
            strength_value=500,
            strength_unit="mg",
            is_active=True,
        )
        session.add(medicine)
        session.flush()
        session.add(
            FormularyRule(
                medicine_id=medicine.id,
                effective_from=datetime(2024, 1, 1, tzinfo=UTC),
                effective_to=None,
                max_quantity_per_dispense=max_once,
                max_quantity_per_30_days=max_30,
                requires_authorisation=auth,
                version_label=f"test-{code.lower()}",
            )
        )

