"""phase 3 resume tables

Revision ID: 0003_phase3_resume_tables
Revises: 0002_phase2_auth_tables
Create Date: 2026-03-23 23:10:00
"""
from __future__ import annotations

from alembic import op
import sqlalchemy as sa


revision = "0003_phase3_resume_tables"
down_revision = "0002_phase2_auth_tables"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "resume_profiles",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column("user_id", sa.String(length=36), nullable=False),
        sa.Column("raw_text", sa.Text(), nullable=False),
        sa.Column("parsed_profile", sa.JSON(), nullable=False),
        sa.Column("resume_embedding", sa.JSON(), nullable=False),
        sa.Column("file_url", sa.String(length=255), nullable=True),
        sa.Column("file_hash", sa.String(length=64), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.UniqueConstraint("user_id"),
    )
    op.create_index("ix_resume_profiles_file_hash", "resume_profiles", ["file_hash"], unique=False)
    op.create_index("ix_resume_profiles_user_id", "resume_profiles", ["user_id"], unique=True)

    op.create_table(
        "search_preferences",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column("user_id", sa.String(length=36), nullable=False),
        sa.Column("target_roles", sa.JSON(), nullable=False),
        sa.Column("preferred_locations", sa.JSON(), nullable=False),
        sa.Column("remote_preference", sa.String(length=20), nullable=False),
        sa.Column("salary_min", sa.Integer(), nullable=True),
        sa.Column("salary_max", sa.Integer(), nullable=True),
        sa.Column("currency", sa.String(length=12), nullable=False),
        sa.Column("excluded_companies", sa.JSON(), nullable=False),
        sa.Column("seniority_level", sa.String(length=20), nullable=True),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.UniqueConstraint("user_id"),
    )
    op.create_index("ix_search_preferences_user_id", "search_preferences", ["user_id"], unique=True)


def downgrade() -> None:
    op.drop_index("ix_search_preferences_user_id", table_name="search_preferences")
    op.drop_table("search_preferences")
    op.drop_index("ix_resume_profiles_user_id", table_name="resume_profiles")
    op.drop_index("ix_resume_profiles_file_hash", table_name="resume_profiles")
    op.drop_table("resume_profiles")
