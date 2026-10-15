"""Dispense rule tests.

These tests target the service layer directly so the assertions focus on the
brief's hard behaviours: all rejection reasons, idempotency, and concurrency.
"""

from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, datetime

from sqlalchemy import select

from app.database import SessionLocal
from app.models import Dispense, DispenseAttempt
from app.schemas import DispenseCreate
from app.services import create_dispense_idempotently
from tests.conftest import make_medicine_with_rule


def _submit(payload: DispenseCreate):
    """Submit through an independent session, matching concurrent API requests."""
    session = SessionLocal()
    try:
        return create_dispense_idempotently(session, payload)
    finally:
        session.close()


def test_rejection_reports_every_failed_rule_and_only_logs_attempt():
    """A rejected dispense returns all violations and leaves no dispense row."""
    make_medicine_with_rule(max_once=5, max_30=8, auth=True)
    payload = DispenseCreate(
        medicine_code="TEST-001",
        patient_ref="patient-a",
        quantity=10,
        dispensed_at=datetime(2025, 1, 15, 10, tzinfo=UTC),
        idempotency_key="reject-1",
    )

    status, body = _submit(payload)

    assert status == 422
    assert {detail["code"] for detail in body["details"]} == {
        "max_per_dispense_exceeded",
        "max_30_days_exceeded",
        "authorisation_required",
    }
    with SessionLocal() as session:
        assert session.scalar(select(Dispense).where(Dispense.idempotency_key == "reject-1")) is None
        assert session.scalar(select(DispenseAttempt).where(DispenseAttempt.idempotency_key == "reject-1")).accepted is False


def test_idempotency_replays_original_outcome_and_rejects_changed_payload():
    """The same key is safe to retry, but not to reuse for a changed request."""
    make_medicine_with_rule()
    payload = DispenseCreate(
        medicine_code="TEST-001",
        patient_ref="patient-a",
        quantity=2,
        dispensed_at=datetime(2025, 1, 15, 10, tzinfo=UTC),
        idempotency_key="same-key",
    )

    first = _submit(payload)
    second = _submit(payload)
    changed = _submit(payload.model_copy(update={"quantity": 3}))

    assert first == second
    assert changed[0] == 409
    with SessionLocal() as session:
        assert len(session.scalars(select(Dispense)).all()) == 1


def test_concurrent_dispenses_cannot_jointly_breach_rolling_limit():
    """Two simultaneous requests for the same patient/medicine cannot both pass.

    The implementation deliberately serialises this narrow critical section with
    pg_advisory_xact_lock. This test starts two independent sessions at once and
    verifies the second sees the first committed quantity before deciding.
    """
    make_medicine_with_rule(max_once=10, max_30=10)
    base_time = datetime(2025, 1, 15, 10, tzinfo=UTC)
    payloads = [
        DispenseCreate(medicine_code="TEST-001", patient_ref="patient-a", quantity=10, dispensed_at=base_time, idempotency_key="race-1"),
        DispenseCreate(medicine_code="TEST-001", patient_ref="patient-a", quantity=10, dispensed_at=base_time, idempotency_key="race-2"),
    ]

    with ThreadPoolExecutor(max_workers=2) as pool:
        results = list(pool.map(_submit, payloads))

    statuses = sorted(status for status, _ in results)
    assert statuses == [201, 422]
    with SessionLocal() as session:
        assert len(session.scalars(select(Dispense)).all()) == 1
        assert len(session.scalars(select(DispenseAttempt)).all()) == 2

