"""Query helpers used by routers and services.

Why this file exists:
    Routers and services both need a few repeatable database queries. Keeping
    those SELECT patterns here prevents duplication while preserving a clean
    boundary: repositories fetch data, services make business decisions, and
    routers translate HTTP requests/responses.
"""

from datetime import datetime

from sqlalchemy import Select, func, or_, select
from sqlalchemy.orm import Session

from app.models import Dispense, FormularyRule, Medicine


def medicine_search_query(term: str | None) -> Select[tuple[Medicine]]:
    """Build the medicine catalogue query with partial code/name matching."""
    # Start with all medicines so an empty search term returns the default
    # catalogue list used by the first frontend screen.
    query = select(Medicine)
    if term:
        # Lowercase matching makes searches forgiving without needing a
        # database-specific full text index for this small assessment dataset.
        like = f"%{term.lower()}%"
        query = query.where(or_(func.lower(Medicine.code).like(like), func.lower(Medicine.name).like(like)))

    # Stable ordering makes pagination deterministic and screenshots repeatable.
    return query.order_by(Medicine.name.asc(), Medicine.code.asc())


def get_medicine_by_code(session: Session, code: str) -> Medicine | None:
    """Fetch a medicine by externally supplied code."""
    # API callers know medicine codes, not internal IDs. Case-insensitive lookup
    # avoids surprises from user-entered code casing.
    return session.scalar(select(Medicine).where(func.lower(Medicine.code) == code.lower()))


def get_rule_in_force(session: Session, medicine_id: int, when_utc: datetime) -> FormularyRule | None:
    """Return the historical rule active at a specific UTC instant."""
    # A rule is active when it started on/before the requested instant and either
    # has no end date or ends after that instant.
    return session.scalar(
        select(FormularyRule)
        .where(
            FormularyRule.medicine_id == medicine_id,
            FormularyRule.effective_from <= when_utc,
            or_(FormularyRule.effective_to.is_(None), FormularyRule.effective_to > when_utc),
        )
        # The newest active period wins if data ever contains adjacent boundary
        # records. The database exclusion constraint still prevents overlaps.
        .order_by(FormularyRule.effective_from.desc())
    )


def dispense_to_api(row: Dispense) -> dict:
    """Convert a joined dispense ORM object into the public API shape."""
    # The ledger needs medicine code/name alongside dispense fields. Returning a
    # simple dict keeps the route response independent from internal ORM shape.
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

