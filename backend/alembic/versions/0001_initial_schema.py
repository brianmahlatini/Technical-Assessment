"""Initial pharmacy formulary schema.

Revision ID: 0001_initial_schema
Revises:
Create Date: 2026-10-15
"""

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision = "0001_initial_schema"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    """Create core tables and database-enforced rule-period exclusion."""
    op.execute("CREATE EXTENSION IF NOT EXISTS btree_gist")

    op.create_table(
        "medicines",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("code", sa.String(length=64), nullable=False),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column("form", sa.String(length=80), nullable=False),
        sa.Column("strength_value", sa.Numeric(12, 3), nullable=False),
        sa.Column("strength_unit", sa.String(length=24), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.UniqueConstraint("code", name="uq_medicines_code"),
    )
    op.create_index("ix_medicines_code_lower", "medicines", [sa.text("lower(code)")])
    op.create_index("ix_medicines_name_trgm_ready", "medicines", ["name"])

    op.create_table(
        "formulary_rules",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("medicine_id", sa.Integer(), sa.ForeignKey("medicines.id", ondelete="CASCADE"), nullable=False),
        sa.Column("effective_from", sa.DateTime(timezone=True), nullable=False),
        sa.Column("effective_to", sa.DateTime(timezone=True), nullable=True),
        sa.Column("max_quantity_per_dispense", sa.Integer(), nullable=False),
        sa.Column("max_quantity_per_30_days", sa.Integer(), nullable=False),
        sa.Column("requires_authorisation", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.CheckConstraint("effective_to IS NULL OR effective_to > effective_from", name="ck_rules_period_forward"),
        sa.CheckConstraint("max_quantity_per_dispense > 0", name="ck_rules_max_per_dispense_positive"),
        sa.CheckConstraint("max_quantity_per_30_days > 0", name="ck_rules_max_30_days_positive"),
    )
    op.create_index("ix_rules_medicine_from", "formulary_rules", ["medicine_id", "effective_from"])
    op.execute(
        """
        ALTER TABLE formulary_rules
        ADD CONSTRAINT ex_rules_no_overlap_per_medicine
        EXCLUDE USING gist (
            medicine_id WITH =,
            tstzrange(effective_from, COALESCE(effective_to, 'infinity'::timestamptz), '[)') WITH &&
        )
        """
    )

    op.create_table(
        "dispenses",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("medicine_id", sa.Integer(), sa.ForeignKey("medicines.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("patient_ref", sa.String(length=128), nullable=False),
        sa.Column("quantity", sa.Integer(), nullable=False),
        sa.Column("dispensed_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("authorisation_ref", sa.String(length=128), nullable=True),
        sa.Column("idempotency_key", sa.String(length=128), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.CheckConstraint("quantity > 0", name="ck_dispenses_quantity_positive"),
        sa.UniqueConstraint("idempotency_key", name="uq_dispenses_idempotency_key"),
    )
    op.create_index("ix_dispenses_patient_medicine_time", "dispenses", ["patient_ref", "medicine_id", "dispensed_at"])
    op.create_index("ix_dispenses_time_desc", "dispenses", [sa.text("dispensed_at DESC")])

    op.create_table(
        "dispense_attempts",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("medicine_code", sa.String(length=64), nullable=False),
        sa.Column("medicine_id", sa.Integer(), nullable=True),
        sa.Column("patient_ref", sa.String(length=128), nullable=False),
        sa.Column("quantity", sa.Integer(), nullable=False),
        sa.Column("dispensed_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("authorisation_ref", sa.String(length=128), nullable=True),
        sa.Column("idempotency_key", sa.String(length=128), nullable=False),
        sa.Column("payload_hash", sa.String(length=64), nullable=False),
        sa.Column("accepted", sa.Boolean(), nullable=False),
        sa.Column("reasons", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
    )
    op.create_index("ix_attempts_idempotency_key", "dispense_attempts", ["idempotency_key"])
    op.create_index("ix_attempts_created_at", "dispense_attempts", [sa.text("created_at DESC")])

    op.create_table(
        "idempotency_records",
        sa.Column("idempotency_key", sa.String(length=128), primary_key=True),
        sa.Column("payload_hash", sa.String(length=64), nullable=False),
        sa.Column("status_code", sa.Integer(), nullable=True),
        sa.Column("response_body", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
    )


def downgrade() -> None:
    """Drop tables in dependency order; the extension is left installed for safety."""
    op.drop_table("idempotency_records")
    op.drop_index("ix_attempts_created_at", table_name="dispense_attempts")
    op.drop_index("ix_attempts_idempotency_key", table_name="dispense_attempts")
    op.drop_table("dispense_attempts")
    op.drop_index("ix_dispenses_time_desc", table_name="dispenses")
    op.drop_index("ix_dispenses_patient_medicine_time", table_name="dispenses")
    op.drop_table("dispenses")
    op.execute("ALTER TABLE formulary_rules DROP CONSTRAINT ex_rules_no_overlap_per_medicine")
    op.drop_index("ix_rules_medicine_from", table_name="formulary_rules")
    op.drop_table("formulary_rules")
    op.drop_index("ix_medicines_name_trgm_ready", table_name="medicines")
    op.drop_index("ix_medicines_code_lower", table_name="medicines")
    op.drop_table("medicines")

