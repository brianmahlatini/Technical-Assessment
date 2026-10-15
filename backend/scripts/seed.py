"""Seed the development database with assessment-scale data.

This script exists so reviewers can load a predictable catalogue without using
the API. It creates 500 medicines, 3-5 rule periods per medicine, and 2,000
historical dispenses spread across 2,000 opaque patient references.
"""

from __future__ import annotations

import random
from datetime import UTC, datetime, timedelta
from decimal import Decimal

from sqlalchemy import delete

from app.database import SessionLocal
from app.models import Dispense, DispenseAttempt, FormularyRule, IdempotencyRecord, Medicine

FORMS = ["tablet", "capsule", "suspension", "injection"]
UNITS = ["mg", "mcg", "ml"]


def main() -> None:
    """Replace any existing demo data with deterministic assessment data."""
    rng = random.Random(42)
    now = datetime.now(UTC)
    start = now - timedelta(days=730)

    with SessionLocal.begin() as session:
        for table in (DispenseAttempt, Dispense, IdempotencyRecord, FormularyRule, Medicine):
            session.execute(delete(table))

        medicines: list[Medicine] = []
        for i in range(1, 501):
            medicine = Medicine(
                code=f"MED-{i:04d}",
                name=f"Generated Medicine {i:04d}",
                form=FORMS[i % len(FORMS)],
                strength_value=Decimal(str(25 + (i % 20) * 25)),
                strength_unit=UNITS[i % len(UNITS)],
                is_active=(i % 37 != 0),
            )
            session.add(medicine)
            medicines.append(medicine)

        session.flush()

        for medicine in medicines:
            periods = 3 + (medicine.id % 3)
            period_start = start
            for version in range(periods):
                period_end = period_start + timedelta(days=180)
                is_last = version == periods - 1
                session.add(
                    FormularyRule(
                        medicine_id=medicine.id,
                        effective_from=period_start,
                        effective_to=None if is_last else period_end,
                        max_quantity_per_dispense=20 + (medicine.id % 30),
                        max_quantity_per_30_days=80 + (medicine.id % 60),
                        requires_authorisation=((medicine.id + version) % 9 == 0),
                        version_label=f"seed-v{version + 1}-{medicine.code.lower()}",
                    )
                )
                period_start = period_end

        session.flush()

        active_medicines = [medicine for medicine in medicines if medicine.is_active]
        for i in range(1, 2001):
            medicine = active_medicines[i % len(active_medicines)]
            dispensed_at = start + timedelta(days=rng.randint(0, 729), hours=rng.randint(0, 23))
            session.add(
                Dispense(
                    medicine_id=medicine.id,
                    patient_ref=f"patient-{i:04d}",
                    quantity=1 + (i % 10),
                    dispensed_at=dispensed_at,
                    authorisation_ref=f"AUTH-{i:04d}" if i % 11 == 0 else None,
                    idempotency_key=f"seed-{i:04d}",
                )
            )

    print("Seeded 500 medicines, historical rules, and 2,000 dispenses.")


if __name__ == "__main__":
    main()

