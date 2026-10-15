"""SQLAlchemy model declarations.

Why this file exists:
    The ORM models are the Python representation of the PostgreSQL schema. They
    let repositories and services query medicines, historical formulary rules,
    successful dispenses, rejected attempts, and idempotency outcomes without
    hand-writing raw SQL for every operation.

How to read this file:
    Each class maps to one database table. The column definitions document what
    data is persisted, while relationships document how records are connected in
    application code. Alembic also imports this metadata when generating or
    running migrations.
"""

from __future__ import annotations

from datetime import datetime
from decimal import Decimal

from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, Numeric, String, UniqueConstraint, text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


class Base(DeclarativeBase):
    """Base class used by Alembic metadata discovery."""


class Medicine(Base):
    """A product that may or may not be dispensable depending on active rules."""

    __tablename__ = "medicines"

    # `id` is the internal database key; `code` is the stable external value used
    # by the API, seed data, and frontend routes.
    id: Mapped[int] = mapped_column(primary_key=True)
    code: Mapped[str] = mapped_column(String(64), unique=True, nullable=False)

    # These fields describe the catalogue item shown in search/detail screens.
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    form: Mapped[str] = mapped_column(String(80), nullable=False)
    strength_value: Mapped[Decimal] = mapped_column(Numeric(12, 3), nullable=False)
    strength_unit: Mapped[str] = mapped_column(String(24), nullable=False)

    # Inactive medicines stay visible historically but cannot be dispensed.
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default=text("true"))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=text("now()"))

    # Rules are owned by their medicine; deleting a medicine in test cleanup also
    # removes its rule history.
    rules: Mapped[list[FormularyRule]] = relationship(back_populates="medicine", cascade="all, delete-orphan")


class FormularyRule(Base):
    """A versioned rule period for one medicine."""

    __tablename__ = "formulary_rules"

    # Version labels only need to be unique per medicine, allowing readable seed
    # labels while preventing duplicate labels inside one medicine timeline.
    __table_args__ = (UniqueConstraint("medicine_id", "version_label", name="uq_rules_medicine_version_label"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    medicine_id: Mapped[int] = mapped_column(ForeignKey("medicines.id", ondelete="CASCADE"), nullable=False)

    # `effective_to = NULL` marks the currently open-ended period. The Alembic
    # migration adds the PostgreSQL exclusion constraint that prevents overlap.
    effective_from: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    effective_to: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    # These are the business limits evaluated by the dispense service.
    max_quantity_per_dispense: Mapped[int] = mapped_column(Integer, nullable=False)
    max_quantity_per_30_days: Mapped[int] = mapped_column(Integer, nullable=False)
    requires_authorisation: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default=text("false"))

    # Labels make history easy to read in the Angular timeline and API output.
    version_label: Mapped[str] = mapped_column(String(80), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=text("now()"))

    medicine: Mapped[Medicine] = relationship(back_populates="rules")


class Dispense(Base):
    """A successful handover of medicine to a patient reference."""

    __tablename__ = "dispenses"

    id: Mapped[int] = mapped_column(primary_key=True)

    # Successful dispenses reference the medicine by internal ID for fast joins
    # and preserve patient references as opaque strings.
    medicine_id: Mapped[int] = mapped_column(ForeignKey("medicines.id", ondelete="RESTRICT"), nullable=False)
    patient_ref: Mapped[str] = mapped_column(String(128), nullable=False)
    quantity: Mapped[int] = mapped_column(Integer, nullable=False)
    dispensed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    authorisation_ref: Mapped[str | None] = mapped_column(String(128), nullable=True)

    # The unique idempotency key prevents duplicate successful inserts when a
    # client retries the same POST.
    idempotency_key: Mapped[str] = mapped_column(String(128), unique=True, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=text("now()"))

    medicine: Mapped[Medicine] = relationship()


class DispenseAttempt(Base):
    """Audit row for every accepted or rejected dispense attempt."""

    __tablename__ = "dispense_attempts"

    id: Mapped[int] = mapped_column(primary_key=True)

    # Attempts store the submitted medicine code even when the medicine does not
    # exist, which keeps rejected attempts auditable.
    medicine_code: Mapped[str] = mapped_column(String(64), nullable=False)
    medicine_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    patient_ref: Mapped[str] = mapped_column(String(128), nullable=False)
    quantity: Mapped[int] = mapped_column(Integer, nullable=False)
    dispensed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    authorisation_ref: Mapped[str | None] = mapped_column(String(128), nullable=True)
    idempotency_key: Mapped[str] = mapped_column(String(128), nullable=False)

    # The payload hash ties the audit row back to the exact request body used for
    # idempotency comparison.
    payload_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    accepted: Mapped[bool] = mapped_column(Boolean, nullable=False)

    # Rejection reasons are stored as JSON so every failed business rule can be
    # inspected later without needing a separate child table.
    reasons: Mapped[list[dict]] = mapped_column(JSONB, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=text("now()"))


class IdempotencyRecord(Base):
    """Cached outcome for POST /dispenses keyed by the client idempotency key."""

    __tablename__ = "idempotency_records"

    # One row per key lets retries replay the original result and lets changed
    # payloads with the same key be rejected.
    idempotency_key: Mapped[str] = mapped_column(String(128), primary_key=True)
    payload_hash: Mapped[str] = mapped_column(String(64), nullable=False)

    # These fields start empty while a request is being processed, then store the
    # exact status/body once the service reaches a durable outcome.
    status_code: Mapped[int | None] = mapped_column(Integer, nullable=True)
    response_body: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=text("now()"))

