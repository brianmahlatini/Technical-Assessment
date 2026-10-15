"""Business services for rule versioning and dispense validation.

Why this file exists:
    This module owns the pharmacy business rules from the assessment brief. The
    API routes call into these functions, but this file decides how rule periods
    are versioned, how dispenses are validated, how rejected attempts are
    audited, and how idempotent retries are replayed safely.

Important design choices:
    * Every dispense attempt, accepted or rejected, is recorded.
    * Rejected dispenses return every failed rule in one response.
    * Idempotency keys replay the original result for identical payloads.
    * PostgreSQL advisory transaction locks prevent concurrent requests from
      jointly breaching a patient's rolling 30-day medicine limit.
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
    # `sort_keys=True` makes the hash stable regardless of JSON key order.
    # Compact separators avoid whitespace differences affecting the digest.
    encoded = json.dumps(payload.model_dump(mode="json"), sort_keys=True, separators=(",", ":")).encode("utf-8")

    # SHA-256 is deterministic and collision-resistant enough for comparing
    # request payload identity in this assessment.
    return hashlib.sha256(encoded).hexdigest()


def introduce_rule(session: Session, medicine_code: str, payload: RuleCreate) -> FormularyRule | None:
    """Create a new rule period by truncating the rule currently in force.

    If the new effective date falls inside an existing period, that period is
    closed at the new start date. If a future rule already exists, the new rule
    ends at that future rule's start date. The database exclusion constraint is
    still the final guard against overlap, including concurrent writes.
    """
    # Resolve the medicine once at the boundary. Returning `None` lets the route
    # convert the domain outcome into a 404 without mixing HTTP into the service.
    medicine = get_medicine_by_code(session, medicine_code)
    if medicine is None:
        return None

    # All rule periods are stored as UTC-aware datetimes so range comparisons are
    # consistent even when callers submit local or offset-aware timestamps.
    start = to_utc(payload.effective_from)

    # The current rule may need to be shortened so the new rule can start at the
    # requested effective instant without overlapping history.
    current = get_rule_in_force(session, medicine.id, start)

    # A future rule, if present, defines where this newly inserted period should
    # end. That preserves the rest of the existing timeline.
    next_rule = session.scalar(
        select(FormularyRule)
        .where(FormularyRule.medicine_id == medicine.id, FormularyRule.effective_from > start)
        .order_by(FormularyRule.effective_from.asc())
        .limit(1)
    )

    # If a rule already starts at this exact instant, update it in place instead
    # of creating a duplicate period with the same boundary.
    if current and current.effective_from == start:
        current.max_quantity_per_dispense = payload.max_quantity_per_dispense
        current.max_quantity_per_30_days = payload.max_quantity_per_30_days
        current.requires_authorisation = payload.requires_authorisation
        session.commit()
        return current

    # Close the period that was in force at the new start date so history remains
    # non-overlapping and auditable.
    if current:
        current.effective_to = start

    # Insert the new period. If a future rule exists, this period ends exactly
    # where that next rule starts; otherwise it becomes the open-ended current rule.
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

    # Commit here because introducing a rule is a complete unit of work and the
    # database exclusion constraint should reject overlaps before returning.
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
    # The hash is used to detect whether a repeated idempotency key has the same
    # body or is trying to represent a different dispense request.
    payload_hash = canonical_hash(payload)

    # One transaction covers idempotency, validation, audit rows, and successful
    # dispense insert so the stored outcome always matches the durable database state.
    with session.begin():
        # Try to claim the idempotency key. `on_conflict_do_nothing` makes this
        # safe when two identical client retries arrive at nearly the same time.
        inserted_key = session.execute(
            pg_insert(IdempotencyRecord)
            .values(idempotency_key=payload.idempotency_key, payload_hash=payload_hash)
            .on_conflict_do_nothing(index_elements=[IdempotencyRecord.idempotency_key])
            .returning(IdempotencyRecord.idempotency_key)
        ).scalar_one_or_none()

        if inserted_key is None:
            # Existing idempotency rows are locked so concurrent retries cannot
            # observe or overwrite a half-written outcome.
            existing = session.scalar(
                select(IdempotencyRecord)
                .where(IdempotencyRecord.idempotency_key == payload.idempotency_key)
                .with_for_update()
            )
            if existing is None:
                return 409, _error_body("idempotency_missing", "Idempotency record could not be resolved.", [])
            if existing.payload_hash != payload_hash:
                # Same key, different payload is dangerous because a retry would
                # no longer mean "same request"; reject it explicitly.
                return 409, _error_body(
                    "idempotency_payload_mismatch",
                    "This idempotency key was already used with a different payload.",
                    [ApiErrorItem(field="idempotency_key", code="payload_mismatch", message="Use a new key for changed payloads.")],
                )
            if existing.status_code is None or existing.response_body is None:
                # This protects clients from replaying an outcome that has not
                # finished writing yet.
                return 409, _error_body("idempotency_in_progress", "The original request is still being processed.", [])
            return existing.status_code, existing.response_body

        # Only the first request for a new idempotency key reaches validation and
        # persistence; retries replay from the record above.
        status_code, body = _evaluate_and_persist_dispense(session, payload, payload_hash)
        record = session.get(IdempotencyRecord, payload.idempotency_key)
        if record is None:
            raise RuntimeError("Idempotency record disappeared during dispense processing.")

        # Store the exact outcome so identical retries can return the same status
        # and body without creating duplicate dispenses or attempts.
        record.status_code = status_code
        record.response_body = body
        return status_code, body


def _evaluate_and_persist_dispense(session: Session, payload: DispenseCreate, payload_hash: str) -> tuple[int, dict[str, Any]]:
    """Run every dispense rule, persist the correct audit rows, and return the API body."""
    # Convert the submitted timestamp once and use that canonical value for rule
    # lookup, rolling-window calculation, and persistence.
    dispensed_at = to_utc(payload.dispensed_at)

    # Unknown medicines still produce an audit row, so `medicine_id` is nullable
    # until lookup succeeds.
    medicine = get_medicine_by_code(session, payload.medicine_code)
    medicine_id = medicine.id if medicine else None

    # Lock by patient plus medicine identity. This serialises only requests that
    # could affect the same rolling-window limit and leaves unrelated requests free.
    lock_key = f"{payload.patient_ref}:{medicine_id or payload.medicine_code.lower()}"
    session.execute(text("SELECT pg_advisory_xact_lock(hashtextextended(:key, 42))"), {"key": lock_key})

    # Collect every failed rule rather than returning early; the brief asks for
    # all rejection reasons in one response.
    reasons: list[ApiErrorItem] = []
    rule = None
    if medicine is None:
        reasons.append(ApiErrorItem(field="medicine_code", code="medicine_not_found", message="Medicine code does not exist."))
    elif not medicine.is_active:
        reasons.append(ApiErrorItem(field="medicine_code", code="medicine_inactive", message="Inactive medicines may not be dispensed."))
    else:
        # Rule lookup is time-specific because historical rule versions can
        # change the answer for backdated or future-dated dispense attempts.
        rule = get_rule_in_force(session, medicine.id, dispensed_at)
        if rule is None:
            reasons.append(ApiErrorItem(field="dispensed_at", code="no_rule_in_force", message="No formulary rule is in force at this time."))

    if rule is not None:
        # At this point a rule can only exist when a medicine exists; the assert
        # communicates that invariant to type checkers and future readers.
        assert medicine is not None

        # Single-dispense maximum is checked independently from rolling 30-day
        # maximum so a request can report both failures when both are true.
        if payload.quantity > rule.max_quantity_per_dispense:
            reasons.append(
                ApiErrorItem(
                    field="quantity",
                    code="max_per_dispense_exceeded",
                    message="Quantity exceeds the single-dispense limit.",
                    meta={"limit": rule.max_quantity_per_dispense, "requested": payload.quantity},
                )
            )

        # The rolling window is calculated in Johannesburg business time, then
        # converted back to UTC for querying stored timestamps.
        window_start, window_end = thirty_day_window_utc(dispensed_at)
        existing_total = session.scalar(
            select(func.coalesce(func.sum(Dispense.quantity), 0)).where(
                Dispense.patient_ref == payload.patient_ref,
                Dispense.medicine_id == medicine.id,
                Dispense.dispensed_at >= window_start,
                Dispense.dispensed_at <= window_end,
            )
        )

        # Compare the already-dispensed quantity plus the requested quantity
        # against the active rule's 30-day maximum.
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

        # Some rules require an authorisation reference. Whitespace-only strings
        # are treated as missing so the UI cannot bypass the rule accidentally.
        if rule.requires_authorisation and not (payload.authorisation_ref or "").strip():
            reasons.append(
                ApiErrorItem(field="authorisation_ref", code="authorisation_required", message="Authorisation reference is required for this medicine.")
            )

    if reasons:
        # Rejected attempts are still persisted for auditability, but no dispense
        # row is inserted.
        session.add(_attempt(payload, payload_hash, medicine_id, False, reasons))
        return 422, _error_body("dispense_rejected", "Dispense rejected by formulary rules.", reasons)

    # If there are no reasons, lookup succeeded and the medicine is active with
    # a rule in force. The assert makes that invariant explicit.
    assert medicine is not None

    # Persist the successful dispense before creating the success response so the
    # response can include the database-generated dispense ID.
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

    # Record successful attempts too, making the audit table a complete request
    # history rather than only an error log.
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
    # This helper keeps accepted/rejected audit creation identical everywhere the
    # service needs to record an attempt.
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
        # Store reasons as JSON-friendly dictionaries so PostgreSQL JSONB can
        # persist them without depending on Pydantic internals.
        reasons=[reason.model_dump(mode="json") for reason in reasons],
    )


def _error_body(error: str, message: str, reasons: list[ApiErrorItem]) -> dict[str, Any]:
    """Create an error body without raising, allowing idempotent replay storage."""
    # Services return bodies rather than raising for dispense validation because
    # accepted/rejected outcomes must both be saved into the idempotency table.
    return {"error": error, "message": message, "details": [reason.model_dump(mode="json") for reason in reasons]}

