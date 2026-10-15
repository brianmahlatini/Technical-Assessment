"""Business services for rule versioning and dispense validation.

This module is deliberately the most explicit part of the backend. It owns the
rules from the brief: historical rule lookup, superseding rule periods,
idempotent dispense submission, rejected-attempt logging, and the PostgreSQL
advisory lock that prevents concurrent rolling-window breaches.
"""

from __future__ import annotations

import hashlib
import json
from typing import Any

from sqlalchemy import func, select, text
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.orm import Session

from app.models import Dispense, DispenseAttempt, FormularyRule, IdempotencyRecord
from app.repositories import get_medicine_by_code, get_rule_in_force
from app.schemas import ApiErrorItem, DispenseCreate, RuleCreate
from app.timezone import thirty_day_window_utc, to_utc


def canonical_hash(payload: DispenseCreate) -> str:
    """Hash the request body so reused idempotency keys with changed payloads are detectable."""
    encoded = json.dumps(payload.model_dump(mode="json"), sort_keys=True, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def introduce_rule(session: Session, medicine_code: str, payload: RuleCreate) -> FormularyRule | None:
    """Create a new rule period by truncating the rule currently in force.

    If the new effective date falls inside an existing period, that period is
    closed at the new start date. If a future rule already exists, the new rule
    ends at that future rule's start date. The database exclusion constraint is
    still the final guard against overlap, including concurrent writes.
    """
    medicine = get_medicine_by_code(session, medicine_code)
    if medicine is None:
        return None

    start = to_utc(payload.effective_from)
    current = get_rule_in_force(session, medicine.id, start)
    next_rule = session.scalar(
        select(FormularyRule)
        .where(FormularyRule.medicine_id == medicine.id, FormularyRule.effective_from > start)
        .order_by(FormularyRule.effective_from.asc())
        .limit(1)
    )

    if current and current.effective_from == start:
        current.max_quantity_per_dispense = payload.max_quantity_per_dispense
        current.max_quantity_per_30_days = payload.max_quantity_per_30_days
        current.requires_authorisation = payload.requires_authorisation
        session.commit()
        return current

    if current:
        current.effective_to = start

    rule = FormularyRule(
        medicine_id=medicine.id,
        effective_from=start,
        effective_to=next_rule.effective_from if next_rule else None,
        max_quantity_per_dispense=payload.max_quantity_per_dispense,
        max_quantity_per_30_days=payload.max_quantity_per_30_days,
        requires_authorisation=payload.requires_authorisation,
        version_label=f"rule-new-{int(start.timestamp())}",
    )
    session.add(rule)
    session.commit()
    session.refresh(rule)
    return rule


def create_dispense_idempotently(session: Session, payload: DispenseCreate) -> tuple[int, dict[str, Any]]:
    """Validate and persist a dispense while respecting idempotency and concurrency.

    The idempotency row is inserted first and locked by the transaction. For new
    requests we then take a per-patient/per-medicine advisory transaction lock
    before reading rolling-window totals, so competing requests cannot both see
    the same pre-insert total and jointly exceed the limit.
    """
    payload_hash = canonical_hash(payload)

    with session.begin():
        inserted_key = session.execute(
            pg_insert(IdempotencyRecord)
            .values(idempotency_key=payload.idempotency_key, payload_hash=payload_hash)
            .on_conflict_do_nothing(index_elements=[IdempotencyRecord.idempotency_key])
            .returning(IdempotencyRecord.idempotency_key)
        ).scalar_one_or_none()

        if inserted_key is None:
            existing = session.scalar(
                select(IdempotencyRecord)
                .where(IdempotencyRecord.idempotency_key == payload.idempotency_key)
                .with_for_update()
            )
            if existing is None:
                return 409, _error_body("idempotency_missing", "Idempotency record could not be resolved.", [])
            if existing.payload_hash != payload_hash:
                return 409, _error_body(
                    "idempotency_payload_mismatch",
                    "This idempotency key was already used with a different payload.",
                    [ApiErrorItem(field="idempotency_key", code="payload_mismatch", message="Use a new key for changed payloads.")],
                )
            if existing.status_code is None or existing.response_body is None:
                return 409, _error_body("idempotency_in_progress", "The original request is still being processed.", [])
            return existing.status_code, existing.response_body

        status_code, body = _evaluate_and_persist_dispense(session, payload, payload_hash)
        record = session.get(IdempotencyRecord, payload.idempotency_key)
        if record is None:
            raise RuntimeError("Idempotency record disappeared during dispense processing.")
        record.status_code = status_code
        record.response_body = body
        return status_code, body


def _evaluate_and_persist_dispense(session: Session, payload: DispenseCreate, payload_hash: str) -> tuple[int, dict[str, Any]]:
    """Run every dispense rule, persist the correct audit rows, and return the API body."""
    dispensed_at = to_utc(payload.dispensed_at)
    medicine = get_medicine_by_code(session, payload.medicine_code)
    medicine_id = medicine.id if medicine else None
    lock_key = f"{payload.patient_ref}:{medicine_id or payload.medicine_code.lower()}"
    session.execute(text("SELECT pg_advisory_xact_lock(hashtextextended(:key, 42))"), {"key": lock_key})

    reasons: list[ApiErrorItem] = []
    rule = None
    if medicine is None:
        reasons.append(ApiErrorItem(field="medicine_code", code="medicine_not_found", message="Medicine code does not exist."))
    elif not medicine.is_active:
        reasons.append(ApiErrorItem(field="medicine_code", code="medicine_inactive", message="Inactive medicines may not be dispensed."))
    else:
        rule = get_rule_in_force(session, medicine.id, dispensed_at)
        if rule is None:
            reasons.append(ApiErrorItem(field="dispensed_at", code="no_rule_in_force", message="No formulary rule is in force at this time."))

    if rule is not None:
        assert medicine is not None

        if payload.quantity > rule.max_quantity_per_dispense:
            reasons.append(
                ApiErrorItem(
                    field="quantity",
                    code="max_per_dispense_exceeded",
                    message="Quantity exceeds the single-dispense limit.",
                    meta={"limit": rule.max_quantity_per_dispense, "requested": payload.quantity},
                )
            )

        window_start, window_end = thirty_day_window_utc(dispensed_at)
        existing_total = session.scalar(
            select(func.coalesce(func.sum(Dispense.quantity), 0)).where(
                Dispense.patient_ref == payload.patient_ref,
                Dispense.medicine_id == medicine.id,
                Dispense.dispensed_at >= window_start,
                Dispense.dispensed_at <= window_end,
            )
        )
        projected_total = int(existing_total or 0) + payload.quantity
        if projected_total > rule.max_quantity_per_30_days:
            reasons.append(
                ApiErrorItem(
                    field="quantity",
                    code="max_30_days_exceeded",
                    message="Quantity exceeds the rolling 30-day patient limit.",
                    meta={"limit": rule.max_quantity_per_30_days, "existing": int(existing_total or 0), "projected": projected_total},
                )
            )

        if rule.requires_authorisation and not (payload.authorisation_ref or "").strip():
            reasons.append(
                ApiErrorItem(field="authorisation_ref", code="authorisation_required", message="Authorisation reference is required for this medicine.")
            )

    if reasons:
        session.add(_attempt(payload, payload_hash, medicine_id, False, reasons))
        return 422, _error_body("dispense_rejected", "Dispense rejected by formulary rules.", reasons)

    assert medicine is not None

    dispense = Dispense(
        medicine_id=medicine.id,
        patient_ref=payload.patient_ref,
        quantity=payload.quantity,
        dispensed_at=dispensed_at,
        authorisation_ref=(payload.authorisation_ref or None),
        idempotency_key=payload.idempotency_key,
    )
    session.add(dispense)
    session.flush()
    session.add(_attempt(payload, payload_hash, medicine.id, True, []))
    return 201, {
        "id": dispense.id,
        "medicine_code": medicine.code,
        "medicine_name": medicine.name,
        "patient_ref": dispense.patient_ref,
        "quantity": dispense.quantity,
        "dispensed_at": dispense.dispensed_at.isoformat(),
        "authorisation_ref": dispense.authorisation_ref,
        "idempotency_key": dispense.idempotency_key,
    }


def _attempt(payload: DispenseCreate, payload_hash: str, medicine_id: int | None, accepted: bool, reasons: list[ApiErrorItem]) -> DispenseAttempt:
    """Build the immutable audit row for accepted and rejected attempts."""
    return DispenseAttempt(
        medicine_code=payload.medicine_code,
        medicine_id=medicine_id,
        patient_ref=payload.patient_ref,
        quantity=payload.quantity,
        dispensed_at=to_utc(payload.dispensed_at),
        authorisation_ref=payload.authorisation_ref,
        idempotency_key=payload.idempotency_key,
        payload_hash=payload_hash,
        accepted=accepted,
        reasons=[reason.model_dump(mode="json") for reason in reasons],
    )


def _error_body(error: str, message: str, reasons: list[ApiErrorItem]) -> dict[str, Any]:
    """Create an error body without raising, allowing idempotent replay storage."""
    return {"error": error, "message": message, "details": [reason.model_dump(mode="json") for reason in reasons]}

