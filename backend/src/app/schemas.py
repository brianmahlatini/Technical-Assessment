"""Pydantic request and response schemas.

Why this file exists:
    SQLAlchemy models describe persistence; Pydantic schemas describe the public
    API contract. Keeping them separate lets the database evolve without forcing
    Angular to know about internal IDs, relationships, or audit-only columns.

How to read this file:
    `...Create` classes are request bodies accepted by the API. `...Out` and
    `...Response` classes are response bodies returned to the frontend. Error
    schemas are shared by routers and services so validation failures have one
    predictable shape.
"""

from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class ApiErrorItem(BaseModel):
    """One frontend-addressable validation or business-rule failure."""

    # `field` points the UI at the form input or conceptual field that failed.
    field: str

    # `code` is stable for automated clients and tests; the message can change
    # wording without breaking integrations.
    code: str
    message: str

    # `meta` carries rule-specific details such as limits and requested values.
    meta: dict[str, Any] = Field(default_factory=dict)


class ApiErrorResponse(BaseModel):
    """Consistent error envelope returned by all application-managed failures."""

    error: str
    message: str

    # Defaulting to an empty list avoids `null` checks in the Angular UI.
    details: list[ApiErrorItem] = Field(default_factory=list)


class PageMeta(BaseModel):
    """Pagination metadata shared by list endpoints."""

    page: int
    page_size: int
    total: int


class MedicineOut(BaseModel):
    """Medicine payload used by search and detail views."""

    # `from_attributes=True` allows FastAPI/Pydantic to serialize SQLAlchemy ORM
    # instances directly through this public response model.
    model_config = ConfigDict(from_attributes=True)

    code: str
    name: str
    form: str
    strength_value: Decimal
    strength_unit: str
    is_active: bool


class RuleOut(BaseModel):
    """Formulary rule payload exposed in detail and rule-history views."""

    # Rule endpoints return ORM rows, so this option is required for safe
    # serialization instead of leaking raw SQLAlchemy objects.
    model_config = ConfigDict(from_attributes=True)

    id: int
    effective_from: datetime
    effective_to: datetime | None
    max_quantity_per_dispense: int
    max_quantity_per_30_days: int
    requires_authorisation: bool
    version_label: str


class MedicineListResponse(BaseModel):
    """Paginated medicine search response."""

    data: list[MedicineOut]
    meta: PageMeta


class MedicineDetailResponse(BaseModel):
    """Medicine detail response including the rule in force now if one exists."""

    medicine: MedicineOut
    current_rule: RuleOut | None


class RuleListResponse(BaseModel):
    """Full historical rule timeline for a medicine."""

    data: list[RuleOut]


class RuleCreate(BaseModel):
    """Request body for introducing a new historical rule period."""

    effective_from: datetime

    # Positive-only limits stop invalid rule definitions before service logic
    # attempts to version or persist them.
    max_quantity_per_dispense: int = Field(gt=0)
    max_quantity_per_30_days: int = Field(gt=0)
    requires_authorisation: bool = False


class DispenseCreate(BaseModel):
    """Request body for the idempotent dispense endpoint."""

    # String bounds keep accidental empty/oversized references out before
    # business validation begins.
    medicine_code: str = Field(min_length=1, max_length=64)
    patient_ref: str = Field(min_length=1, max_length=128)

    # Dispensing zero or negative units is invalid at request-schema level.
    quantity: int = Field(gt=0)
    dispensed_at: datetime
    authorisation_ref: str | None = None

    # Clients must provide a key so retries can be made safely.
    idempotency_key: str = Field(min_length=1, max_length=128)


class DispenseOut(BaseModel):
    """Successful dispense response and patient ledger item."""

    id: int
    medicine_code: str
    medicine_name: str
    patient_ref: str
    quantity: int
    dispensed_at: datetime
    authorisation_ref: str | None
    idempotency_key: str


class DispenseListResponse(BaseModel):
    """Paginated dispense ledger response."""

    data: list[DispenseOut]
    meta: PageMeta

