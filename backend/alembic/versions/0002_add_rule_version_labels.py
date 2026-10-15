"""Add generated rule version labels.

Revision ID: 0002_add_rule_version_labels
Revises: 0001_initial_schema
Create Date: 2026-10-15
"""

import sqlalchemy as sa

from alembic import op

revision = "0002_add_rule_version_labels"
down_revision = "0001_initial_schema"
branch_labels = None
depends_on = None


def upgrade() -> None:
    """Add and backfill a reviewer-friendly version label for historical rules."""
    op.add_column("formulary_rules", sa.Column("version_label", sa.String(length=80), nullable=True))
    op.execute(
        """
        UPDATE formulary_rules
        SET version_label = 'rule-' || id::text || '-' || to_char(effective_from AT TIME ZONE 'Africa/Johannesburg', 'YYYYMMDD')
        WHERE version_label IS NULL
        """
    )
    op.alter_column("formulary_rules", "version_label", nullable=False)
    op.create_unique_constraint("uq_rules_medicine_version_label", "formulary_rules", ["medicine_id", "version_label"])


def downgrade() -> None:
    """Remove the derived label and its uniqueness constraint cleanly."""
    op.drop_constraint("uq_rules_medicine_version_label", "formulary_rules", type_="unique")
    op.drop_column("formulary_rules", "version_label")

