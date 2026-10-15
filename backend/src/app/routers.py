"""FastAPI route definitions.

Why this file exists:
    This module is the HTTP boundary of the backend. It parses path/query/body
    input, injects a request-scoped database session, delegates business work to
    repositories/services, and returns response models shaped for Angular.

Design rule:
    Routes stay thin. If a block starts making pharmacy decisions, it belongs in
    `services.py`; if it is only a reusable SELECT, it belongs in
    `repositories.py`.
"""

from datetime import UTC, datetime

from fastapi import APIRouter, Depends, Query
from fastapi.responses import JSONResponse
from sqlalchemy import func, select
from sqlalchemy.orm import Session, joinedload

from app.database import get_session
from app.errors import api_error
from app.models import Dispense, FormularyRule, Medicine
from app.repositories import dispense_to_api, get_medicine_by_code, get_rule_in_force, medicine_search_query
from app.schemas import DispenseCreate, MedicineDetailResponse, MedicineListResponse, RuleCreate, RuleListResponse, RuleOut
from app.services import create_dispense_idempotently, introduce_rule
from app.timezone import to_utc

router = APIRouter()


@router.get("/health")
def health() -> dict[str, str]:
    """Small readiness endpoint used by people and containers."""
    return {"status": "ok"}


@router.get("/medicines", response_model=MedicineListResponse)
def list_medicines(
    q: str | None = Query(default=None),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=25, ge=1, le=100),
    session: Session = Depends(get_session),
) -> dict:
    """Search medicines by partial code or name with offset pagination."""
    # Build the reusable SELECT in the repository, then use it once for counting
    # and once for the current page. That keeps pagination metadata accurate.
    base = medicine_search_query(q)
    total = session.scalar(select(func.count()).select_from(base.subquery()))
    rows = session.scalars(base.offset((page - 1) * page_size).limit(page_size)).all()
    return {"data": rows, "meta": {"page": page, "page_size": page_size, "total": total}}


@router.get("/medicines/{code}", response_model=MedicineDetailResponse)
def get_medicine(code: str, session: Session = Depends(get_session)) -> dict:
    """Return medicine details plus the rule currently in force."""
    # Medicine codes are the public identifier used by the UI and seeded data.
    medicine = get_medicine_by_code(session, code)
    if medicine is None:
        raise api_error(404, "not_found", "Medicine was not found.")

    # The current rule is time-dependent, so calculate it at request time rather
    # than denormalising it onto the medicine row.
    current_rule = get_rule_in_force(session, medicine.id, to_utc(datetime.now(UTC)))
    return {"medicine": medicine, "current_rule": current_rule}


@router.get("/medicines/{code}/rules", response_model=RuleListResponse)
def list_rules(code: str, session: Session = Depends(get_session)) -> dict:
    """Return the full rule history ordered as a timeline."""
    # First resolve the public code to an internal medicine row so unknown codes
    # get a clear 404 instead of an empty timeline.
    medicine = get_medicine_by_code(session, code)
    if medicine is None:
        raise api_error(404, "not_found", "Medicine was not found.")

    # Oldest-to-newest ordering matches how people read a rule history timeline.
    rules = session.scalars(
        select(FormularyRule).where(FormularyRule.medicine_id == medicine.id).order_by(FormularyRule.effective_from.asc())
    ).all()
    return {"data": rules}


@router.post("/medicines/{code}/rules", response_model=RuleOut, status_code=201)
def create_rule(code: str, payload: RuleCreate, session: Session = Depends(get_session)):
    """Introduce a new rule period and supersede the period currently in force."""
    # Versioning rules are complex enough to stay in the service layer where they
    # can be unit-tested without HTTP.
    rule = introduce_rule(session, code, payload)
    if rule is None:
        raise api_error(404, "not_found", "Medicine was not found.")
    return rule


@router.post("/dispenses")
def create_dispense(payload: DispenseCreate, session: Session = Depends(get_session)):
    """Submit a validated, idempotent dispense request."""
    # The service returns both status and body so accepted, rejected, replayed,
    # and conflict outcomes can all be persisted/replayed consistently.
    status_code, body = create_dispense_idempotently(session, payload)
    return JSONResponse(status_code=status_code, content=body)


@router.get("/dispenses")
def list_dispenses(
    patient_ref: str | None = Query(default=None),
    medicine: str | None = Query(default=None),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=25, ge=1, le=100),
    session: Session = Depends(get_session),
) -> dict:
    """Return newest-first dispenses, optionally filtered for the patient ledger."""
    # Join medicine once so the ledger can show medicine code/name without
    # triggering one query per row.
    query = select(Dispense).options(joinedload(Dispense.medicine)).join(Medicine)
    if patient_ref:
        query = query.where(Dispense.patient_ref == patient_ref)
    if medicine:
        query = query.where(func.lower(Medicine.code) == medicine.lower())

    # Newest-first ordering supports the UI's ledger view and uses ID as a stable
    # tiebreaker for records with the same timestamp.
    query = query.order_by(Dispense.dispensed_at.desc(), Dispense.id.desc())
    total = session.scalar(select(func.count()).select_from(query.subquery()))
    rows = session.scalars(query.offset((page - 1) * page_size).limit(page_size)).all()
    return {"data": [dispense_to_api(row) for row in rows], "meta": {"page": page, "page_size": page_size, "total": total}}

