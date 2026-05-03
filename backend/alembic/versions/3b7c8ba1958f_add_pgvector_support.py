"""add_pgvector_support

Revision ID: 3b7c8ba1958f
Revises: 2c5f6a1d4e20
Create Date: 2026-05-03 15:42:01.215433
"""
from __future__ import annotations

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '3b7c8ba1958f'
down_revision = '2c5f6a1d4e20'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # 1. Enable pgvector extension
    op.execute("CREATE EXTENSION IF NOT EXISTS vector")

    # 2. Cleanup mismatched dimensions in jobs
    # Note: Use a zero vector string that pgvector can parse
    op.execute(
        "UPDATE jobs SET description_embedding = ('[' || repeat('0,', 3071) || '0]')::json "
        "WHERE description_embedding IS NOT NULL "
        "AND json_array_length(description_embedding::json) != 3072"
    )

    # 3. Alter jobs.description_embedding from JSON to vector(3072)
    op.execute(
        "ALTER TABLE jobs ALTER COLUMN description_embedding TYPE vector(3072) "
        "USING description_embedding::text::vector"
    )

    # 4. Cleanup mismatched dimensions in resume_profiles
    op.execute(
        "UPDATE resume_profiles SET resume_embedding = ('[' || repeat('0,', 3071) || '0]')::json "
        "WHERE resume_embedding IS NOT NULL "
        "AND json_array_length(resume_embedding::json) != 3072"
    )

    # 5. Alter resume_profiles.resume_embedding from JSON to vector(3072)
    op.execute(
        "ALTER TABLE resume_profiles ALTER COLUMN resume_embedding TYPE vector(3072) "
        "USING resume_embedding::text::vector"
    )


def downgrade() -> None:
    # 1. Revert columns to JSON
    op.execute(
        "ALTER TABLE jobs ALTER COLUMN description_embedding TYPE JSON "
        "USING description_embedding::text::json"
    )
    op.execute(
        "ALTER TABLE resume_profiles ALTER COLUMN resume_embedding TYPE JSON "
        "USING resume_embedding::text::json"
    )
