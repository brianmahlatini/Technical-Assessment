"""Query helpers used by routers and services.

These functions keep common SELECT patterns in one place. The service layer
still owns business decisions; repositories only shape database access.
"""

from datetime import datetime

from sqlalchemy import Select, func, or_, select
from sqlalchemy.orm import Session

from app.models import Dispense, FormularyRule, Medicine


def medicine_search_query(term: str | None) -> Select[tuple[Medicine]]:
    """Build the medicine catalogue query with partial code/name matching."""
    query = select(Medicine)
    if term:
        like = f"%{term.lower()}%"
        query = query.where(or_(func.lower(Medicine.code).like(like), func.lower(Medicine.name).like(like)))
    return query.order_by(Medicine.name.asc(), Medicine.code.asc())


def get_medicine_by_code(session: Session, code: str) -> Medicine | None:
    """Fetch a medicine by externally supplied code."""
    return session.scalar(select(Medicine).where(func.lower(Medicine.code) == code.lower()))


def get_rule_in_force(session: Session, medicine_id: int, when_utc: datetime) -> FormularyRule | None:
    """Return the historical rule active at a specific UTC instant."""
    return session.scalar(
        select(FormularyRule)
        .where(
            FormularyRule.medicine_id == medicine_id,
            FormularyRule.effective_from <= when_utc,
            or_(FormularyRule.effective_to.is_(None), FormularyRule.effective_to > when_utc),
        )
        .order_by(FormularyRule.effective_from.desc())
    )


def dispense_to_api(row: Dispense) -> dict:
    """Convert a joined dispense ORM object into the public API shape."""
    return {
        "id": row.id,
        "medicine_code": row.medicine.code,
        "medicine_name": row.medicine.name,
        "patient_ref": row.patient_ref,
        "quantity": row.quantity,
        "dispensed_at": row.dispensed_at,
        "authorisation_ref": row.authorisation_ref,
        "idempotency_key": row.idempotency_key,
    }

