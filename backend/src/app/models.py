"""SQLAlchemy model declarations.

These classes mirror the Alembic schema and give the service layer typed access
to medicines, historical formulary rules, successful dispenses, rejected
attempts, and idempotency outcomes.
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

    id: Mapped[int] = mapped_column(primary_key=True)
    code: Mapped[str] = mapped_column(String(64), unique=True, nullable=False)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    form: Mapped[str] = mapped_column(String(80), nullable=False)
    strength_value: Mapped[Decimal] = mapped_column(Numeric(12, 3), nullable=False)
    strength_unit: Mapped[str] = mapped_column(String(24), nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default=text("true"))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=text("now()"))

    rules: Mapped[list[FormularyRule]] = relationship(back_populates="medicine", cascade="all, delete-orphan")


class FormularyRule(Base):
    """A versioned rule period for one medicine."""

    __tablename__ = "formulary_rules"
    __table_args__ = (UniqueConstraint("medicine_id", "version_label", name="uq_rules_medicine_version_label"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    medicine_id: Mapped[int] = mapped_column(ForeignKey("medicines.id", ondelete="CASCADE"), nullable=False)
    effective_from: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    effective_to: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    max_quantity_per_dispense: Mapped[int] = mapped_column(Integer, nullable=False)
    max_quantity_per_30_days: Mapped[int] = mapped_column(Integer, nullable=False)
    requires_authorisation: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default=text("false"))
    version_label: Mapped[str] = mapped_column(String(80), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=text("now()"))

    medicine: Mapped[Medicine] = relationship(back_populates="rules")


class Dispense(Base):
    """A successful handover of medicine to a patient reference."""

    __tablename__ = "dispenses"

    id: Mapped[int] = mapped_column(primary_key=True)
    medicine_id: Mapped[int] = mapped_column(ForeignKey("medicines.id", ondelete="RESTRICT"), nullable=False)
    patient_ref: Mapped[str] = mapped_column(String(128), nullable=False)
    quantity: Mapped[int] = mapped_column(Integer, nullable=False)
    dispensed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    authorisation_ref: Mapped[str | None] = mapped_column(String(128), nullable=True)
    idempotency_key: Mapped[str] = mapped_column(String(128), unique=True, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=text("now()"))

    medicine: Mapped[Medicine] = relationship()


class DispenseAttempt(Base):
    """Audit row for every accepted or rejected dispense attempt."""

    __tablename__ = "dispense_attempts"

    id: Mapped[int] = mapped_column(primary_key=True)
    medicine_code: Mapped[str] = mapped_column(String(64), nullable=False)
    medicine_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    patient_ref: Mapped[str] = mapped_column(String(128), nullable=False)
    quantity: Mapped[int] = mapped_column(Integer, nullable=False)
    dispensed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    authorisation_ref: Mapped[str | None] = mapped_column(String(128), nullable=True)
    idempotency_key: Mapped[str] = mapped_column(String(128), nullable=False)
    payload_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    accepted: Mapped[bool] = mapped_column(Boolean, nullable=False)
    reasons: Mapped[list[dict]] = mapped_column(JSONB, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=text("now()"))


class IdempotencyRecord(Base):
    """Cached outcome for POST /dispenses keyed by the client idempotency key."""

    __tablename__ = "idempotency_records"

    idempotency_key: Mapped[str] = mapped_column(String(128), primary_key=True)
    payload_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    status_code: Mapped[int | None] = mapped_column(Integer, nullable=True)
    response_body: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=text("now()"))

