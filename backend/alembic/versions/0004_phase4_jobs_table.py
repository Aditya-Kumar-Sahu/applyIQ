"""phase 4 jobs table

Revision ID: 0004_phase4_jobs_table
Revises: 0003_phase3_resume_tables
Create Date: 2026-03-24 13:30:00
"""
from __future__ import annotations

from alembic import op
import sqlalchemy as sa


revision = "0004_phase4_jobs_table"
down_revision = "0003_phase3_resume_tables"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "jobs",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column("external_id", sa.String(length=100), nullable=False),
        sa.Column("source", sa.String(length=30), nullable=False),
        sa.Column("title", sa.String(length=255), nullable=False),
        sa.Column("company_name", sa.String(length=255), nullable=False),
        sa.Column("company_domain", sa.String(length=255), nullable=True),
        sa.Column("location", sa.String(length=255), nullable=False),
        sa.Column("is_remote", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("salary_min", sa.Integer(), nullable=True),
        sa.Column("salary_max", sa.Integer(), nullable=True),
        sa.Column("description_text", sa.Text(), nullable=False),
        sa.Column("description_embedding", sa.JSON(), nullable=False),
        sa.Column("apply_url", sa.String(length=500), nullable=False),
        sa.Column("posted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("scraped_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.UniqueConstraint("apply_url"),
    )
    op.create_index("ix_jobs_external_id", "jobs", ["external_id"], unique=False)
    op.create_index("ix_jobs_source", "jobs", ["source"], unique=False)
    op.create_index("ix_jobs_title", "jobs", ["title"], unique=False)
    op.create_index("ix_jobs_company_name", "jobs", ["company_name"], unique=False)
    op.create_index("ix_jobs_apply_url", "jobs", ["apply_url"], unique=True)


def downgrade() -> None:
    op.drop_index("ix_jobs_apply_url", table_name="jobs")
    op.drop_index("ix_jobs_company_name", table_name="jobs")
    op.drop_index("ix_jobs_title", table_name="jobs")
    op.drop_index("ix_jobs_source", table_name="jobs")
    op.drop_index("ix_jobs_external_id", table_name="jobs")
    op.drop_table("jobs")
