"""SQLAlchemy model declarations.

Why this file exists:
    The ORM models are the Python representation of the PostgreSQL schema. They
    let repositories and services query medicines, historical formulary rules,
    successful dispenses, rejected attempts, and idempotency outcomes without
    hand-writing raw SQL for every operation.

How to read this file in the technical review:
    1. `Medicine` is the catalogue item users search for and dispense.
    2. `FormularyRule` is the versioned business rule history for one medicine.
    3. `Dispense` records successful medicine handovers only.
    4. `DispenseAttempt` records every submitted attempt, including rejections.
    5. `IdempotencyRecord` lets POST /dispenses safely replay retries.

Important architecture point:
    These classes describe persistence, not request/response JSON. Public API
    shapes live separately in `schemas.py`, which keeps frontend contracts stable
    even if internal tables change.
"""

# Postpones evaluation of type hints so relationships can reference classes
# declared later in this file, for example `Medicine.rules -> FormularyRule`.
from __future__ import annotations

# SQLAlchemy timezone-aware DateTime columns are represented as Python datetime
# objects when rows are loaded from PostgreSQL.
from datetime import datetime

# Decimal preserves medicine strength precision better than float, which matters
# when displaying values like 50.000 mcg or 125.000 mg.
from decimal import Decimal

# SQLAlchemy column and constraint building blocks used to map Python attributes
# to PostgreSQL columns.
from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, Numeric, String, UniqueConstraint, text

# JSONB is PostgreSQL-specific and is used for audit/error details that are
# naturally structured but do not need their own child table in this assessment.
from sqlalchemy.dialects.postgresql import JSONB

# DeclarativeBase registers table metadata; Mapped/mapped_column provide typed
# ORM columns; relationship defines object links between tables.
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


class Base(DeclarativeBase):
    """Base class used by SQLAlchemy and Alembic metadata discovery."""

    # No columns live on the base class. It only gives SQLAlchemy one registry
    # that contains all table mappings for migrations and runtime queries.


class Medicine(Base):
    """Medicine catalogue item.

    Why this table exists:
        The frontend search page needs medicine code/name/strength/form, while
        the dispense service needs a stable medicine row to connect rules and
        successful dispenses.
    """

    # Explicit table name keeps database naming clear and stable for Alembic,
    # SQL queries, tests, and reviewer inspection.
    __tablename__ = "medicines"

    # Internal surrogate key. Services use it for joins because integers are
    # compact and stable inside the database.
    id: Mapped[int] = mapped_column(primary_key=True)

    # External medicine identifier. This is what users, routes, seed data, and
    # screenshots use, for example `MED-0001`.
    code: Mapped[str] = mapped_column(String(64), unique=True, nullable=False)

    # Human-readable medicine name displayed in the search table and detail page.
    name: Mapped[str] = mapped_column(String(255), nullable=False)

    # Dosage form such as tablet, capsule, suspension, or injection.
    form: Mapped[str] = mapped_column(String(80), nullable=False)

    # Numeric strength value stored as Decimal/Numeric to avoid float rounding.
    strength_value: Mapped[Decimal] = mapped_column(Numeric(12, 3), nullable=False)

    # Unit for the strength value, such as mg, mcg, or ml.
    strength_unit: Mapped[str] = mapped_column(String(24), nullable=False)

    # Inactive medicines remain visible historically but are rejected by dispense
    # validation so old data is preserved without allowing new handovers.
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default=text("true"))

    # Server-generated timestamp records when the catalogue row was created.
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=text("now()"))

    # One medicine has many historical rules. `cascade="all, delete-orphan"` is
    # useful for tests/cleanup because rule rows should not outlive their medicine.
    rules: Mapped[list[FormularyRule]] = relationship(back_populates="medicine", cascade="all, delete-orphan")


class FormularyRule(Base):
    """Versioned formulary rule period for one medicine.

    Why this table exists:
        The assessment requires rule changes over time. Instead of overwriting a
        medicine's limits, every rule version is stored with an effective range
        so historical dispenses can be validated against the rule active then.
    """

    # Stores the rule timeline for all medicines.
    __tablename__ = "formulary_rules"

    # Version labels only need to be unique within one medicine timeline. This
    # allows labels like `seed-v1-med-0001` while preventing duplicate labels for
    # the same medicine.
    __table_args__ = (UniqueConstraint("medicine_id", "version_label", name="uq_rules_medicine_version_label"),)

    # Internal primary key for one rule version row.
    id: Mapped[int] = mapped_column(primary_key=True)

    # Owning medicine. Cascade delete is allowed because rules have no meaning
    # without their medicine catalogue row.
    medicine_id: Mapped[int] = mapped_column(ForeignKey("medicines.id", ondelete="CASCADE"), nullable=False)

    # Start of the period when this rule is active. Stored timezone-aware so
    # comparisons are deterministic.
    effective_from: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)

    # End of the rule period. NULL means this is open-ended/current until a later
    # rule supersedes it.
    effective_to: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    # Maximum units allowed in one dispense request.
    max_quantity_per_dispense: Mapped[int] = mapped_column(Integer, nullable=False)

    # Maximum units allowed for one patient/medicine inside the rolling 30-day
    # business window.
    max_quantity_per_30_days: Mapped[int] = mapped_column(Integer, nullable=False)

    # When true, the dispense request must include an authorisation reference.
    requires_authorisation: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default=text("false"))

    # Human-readable version name displayed in the Angular rule timeline.
    version_label: Mapped[str] = mapped_column(String(80), nullable=False)

    # Server-generated creation timestamp for auditing rule rows.
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=text("now()"))

    # Back-reference to the parent medicine. `back_populates` keeps both sides of
    # the relationship consistent in Python.
    medicine: Mapped[Medicine] = relationship(back_populates="rules")


class Dispense(Base):
    """Successful dispense record.

    Why this table exists:
        It stores accepted dispense submissions only. Rejected attempts go to
        `DispenseAttempt`, which keeps this table clean for ledger and rolling
        total calculations.
    """

    # Successful dispense ledger table.
    __tablename__ = "dispenses"

    # Internal primary key returned to the UI after a successful capture.
    id: Mapped[int] = mapped_column(primary_key=True)

    # Medicine dispensed. Restrict delete protects successful history from losing
    # its catalogue link.
    medicine_id: Mapped[int] = mapped_column(ForeignKey("medicines.id", ondelete="RESTRICT"), nullable=False)

    # Opaque patient reference. The assessment does not model patient personal
    # information, only this stable lookup key.
    patient_ref: Mapped[str] = mapped_column(String(128), nullable=False)

    # Accepted quantity for this dispense.
    quantity: Mapped[int] = mapped_column(Integer, nullable=False)

    # Time the medicine was dispensed, stored timezone-aware for rule lookup and
    # rolling-window calculations.
    dispensed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)

    # Optional proof/reference used when the active rule requires authorisation.
    authorisation_ref: Mapped[str | None] = mapped_column(String(128), nullable=True)

    # Unique client-supplied key prevents duplicate successful inserts when a
    # browser/client retries the same POST request.
    idempotency_key: Mapped[str] = mapped_column(String(128), unique=True, nullable=False)

    # Server-generated timestamp showing when the row was inserted.
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=text("now()"))

    # Relationship loaded by the ledger endpoint so it can return medicine code
    # and name next to dispense fields.
    medicine: Mapped[Medicine] = relationship()


class DispenseAttempt(Base):
    """Audit row for every accepted or rejected dispense attempt.

    Why this table exists:
        The brief requires rejected attempts to be persisted. This table stores
        both success and failure attempts so reviewers can see a complete audit
        trail of submissions, not only accepted dispenses.
    """

    # Audit table for all dispense submissions.
    __tablename__ = "dispense_attempts"

    # Internal audit row ID.
    id: Mapped[int] = mapped_column(primary_key=True)

    # Submitted medicine code is stored even if no medicine row exists, which is
    # necessary to audit unknown-code rejections.
    medicine_code: Mapped[str] = mapped_column(String(64), nullable=False)

    # Internal medicine ID when lookup succeeds; nullable for unknown-code attempts.
    medicine_id: Mapped[int | None] = mapped_column(Integer, nullable=True)

    # Opaque patient reference from the submitted payload.
    patient_ref: Mapped[str] = mapped_column(String(128), nullable=False)

    # Requested quantity, whether accepted or rejected.
    quantity: Mapped[int] = mapped_column(Integer, nullable=False)

    # Submitted dispense timestamp normalised by the service.
    dispensed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)

    # Submitted authorisation reference, if any.
    authorisation_ref: Mapped[str | None] = mapped_column(String(128), nullable=True)

    # Idempotency key from the submitted request so attempts can be connected to
    # idempotent outcomes.
    idempotency_key: Mapped[str] = mapped_column(String(128), nullable=False)

    # Hash of the JSON payload. This ties the audit row back to the exact request
    # body used for idempotency comparison.
    payload_hash: Mapped[str] = mapped_column(String(64), nullable=False)

    # True when the service created a successful `Dispense`; false when it
    # returned rule-validation errors.
    accepted: Mapped[bool] = mapped_column(Boolean, nullable=False)

    # Structured rejection reasons. Empty list for accepted attempts; one entry
    # per failed business rule for rejected attempts.
    reasons: Mapped[list[dict]] = mapped_column(JSONB, nullable=False)

    # Server-generated timestamp for audit ordering.
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=text("now()"))


class IdempotencyRecord(Base):
    """Cached outcome for POST /dispenses keyed by the client idempotency key.

    Why this table exists:
        HTTP clients can retry POST requests after timeouts. This table makes the
        dispense endpoint safe to retry: same key and same payload replays the
        original response; same key with a different payload is rejected.
    """

    # One idempotency row per client-supplied key.
    __tablename__ = "idempotency_records"

    # Primary key is the client-provided idempotency key.
    idempotency_key: Mapped[str] = mapped_column(String(128), primary_key=True)

    # Hash of the first payload used with the key. Later payloads with the same
    # key must match this hash.
    payload_hash: Mapped[str] = mapped_column(String(64), nullable=False)

    # HTTP status from the original completed request. NULL means the first
    # request is still in progress.
    status_code: Mapped[int | None] = mapped_column(Integer, nullable=True)

    # Exact JSON response body from the original completed request. Stored so
    # retries can replay the same response without recalculating business logic.
    response_body: Mapped[dict | None] = mapped_column(JSONB, nullable=True)

    # Server-generated timestamp showing when the idempotency key was first seen.
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=text("now()"))

