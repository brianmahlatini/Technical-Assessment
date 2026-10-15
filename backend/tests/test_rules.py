"""Formulary rule versioning tests."""

from datetime import UTC, datetime

from fastapi.testclient import TestClient
from sqlalchemy import select

from app.database import SessionLocal
from app.main import app
from app.models import FormularyRule
from app.schemas import RuleCreate
from app.services import introduce_rule
from tests.conftest import make_medicine_with_rule


def test_introducing_rule_truncates_rule_in_force():
    """A new rule starting inside an existing period preserves history by closing the prior period."""
    make_medicine_with_rule()
    start = datetime(2025, 6, 1, tzinfo=UTC)

    with SessionLocal() as session:
        rule = introduce_rule(
            session,
            "TEST-001",
            RuleCreate(effective_from=start, max_quantity_per_dispense=7, max_quantity_per_30_days=30, requires_authorisation=True),
        )

    with SessionLocal() as session:
        rules = session.scalars(select(FormularyRule).order_by(FormularyRule.effective_from.asc())).all()

    assert rule is not None
    assert len(rules) == 2
    assert rules[0].effective_to == start
    assert rules[1].effective_from == start
    assert rules[1].requires_authorisation is True


def test_rule_history_endpoint_serializes_rules_with_cors_header():
    """The Angular detail page depends on rule history being real JSON, not raw ORM objects."""
    make_medicine_with_rule()

    response = TestClient(app).get("/api/v1/medicines/TEST-001/rules", headers={"Origin": "http://localhost:4200"})

    assert response.status_code == 200
    assert response.headers["access-control-allow-origin"] == "http://localhost:4200"
    body = response.json()
    assert body["data"][0]["version_label"] == "test-test-001"
    assert body["data"][0]["max_quantity_per_dispense"] == 20

