"""phase 7 cover letter metadata

Revision ID: 0007_phase7_cover_letter_meta
Revises: 0006_phase6_pipeline_tables
Create Date: 2026-03-27 00:00:00.000000
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa


revision = "0007_phase7_cover_letter_meta"
down_revision = "0006_phase6_pipeline_tables"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("applications", sa.Column("cover_letter_tone", sa.String(length=30), nullable=False, server_default="formal"))
    op.add_column("applications", sa.Column("cover_letter_word_count", sa.Integer(), nullable=False, server_default="0"))
    op.alter_column("applications", "cover_letter_tone", server_default=None)
    op.alter_column("applications", "cover_letter_word_count", server_default=None)


def downgrade() -> None:
    op.drop_column("applications", "cover_letter_word_count")
    op.drop_column("applications", "cover_letter_tone")
