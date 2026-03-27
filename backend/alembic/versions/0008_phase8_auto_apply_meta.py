"""phase 8 auto apply metadata

Revision ID: 0008_phase8_auto_apply_meta
Revises: 0007_phase7_cover_letter_meta
Create Date: 2026-03-28 00:00:00.000000
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa


revision = "0008_phase8_auto_apply_meta"
down_revision = "0007_phase7_cover_letter_meta"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("applications", sa.Column("ats_provider", sa.String(length=50), nullable=True))
    op.add_column("applications", sa.Column("manual_required_reason", sa.Text(), nullable=True))


def downgrade() -> None:
    op.drop_column("applications", "manual_required_reason")
    op.drop_column("applications", "ats_provider")
