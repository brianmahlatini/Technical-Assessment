"""Pydantic request and response schemas.

Schemas are separate from ORM models so the API contract can stay stable even
when persistence details change. They also carry field descriptions that help a
frontend map validation and business-rule errors back to form controls.
"""

from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class ApiErrorItem(BaseModel):
    """One frontend-addressable validation or business-rule failure."""

    field: str
    code: str
    message: str
    meta: dict[str, Any] = Field(default_factory=dict)


class ApiErrorResponse(BaseModel):
    """Consistent error envelope returned by all application-managed failures."""

    error: str
    message: str
    details: list[ApiErrorItem] = Field(default_factory=list)


class PageMeta(BaseModel):
    """Pagination metadata shared by list endpoints."""

    page: int
    page_size: int
    total: int


class MedicineOut(BaseModel):
    """Medicine payload used by search and detail views."""

    model_config = ConfigDict(from_attributes=True)

    code: str
    name: str
    form: str
    strength_value: Decimal
    strength_unit: str
    is_active: bool


class RuleOut(BaseModel):
    """Formulary rule payload exposed in detail and rule-history views."""

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


class RuleCreate(BaseModel):
    """Request body for introducing a new historical rule period."""

    effective_from: datetime
    max_quantity_per_dispense: int = Field(gt=0)
    max_quantity_per_30_days: int = Field(gt=0)
    requires_authorisation: bool = False


class DispenseCreate(BaseModel):
    """Request body for the idempotent dispense endpoint."""

    medicine_code: str = Field(min_length=1, max_length=64)
    patient_ref: str = Field(min_length=1, max_length=128)
    quantity: int = Field(gt=0)
    dispensed_at: datetime
    authorisation_ref: str | None = None
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

