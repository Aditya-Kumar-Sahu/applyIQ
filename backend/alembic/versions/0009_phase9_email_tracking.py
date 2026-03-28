"""phase 9 email tracking

Revision ID: 0009_phase9_email_tracking
Revises: 0008_phase8_auto_apply_meta
Create Date: 2026-03-28 00:00:00.000000
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa


revision = "0009_phase9_email_tracking"
down_revision = "0008_phase8_auto_apply_meta"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "email_monitors",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("user_id", sa.String(length=36), nullable=False),
        sa.Column("application_id", sa.String(length=36), nullable=False),
        sa.Column("gmail_thread_id", sa.String(length=255), nullable=False),
        sa.Column("sender", sa.String(length=320), nullable=False),
        sa.Column("subject", sa.String(length=500), nullable=False),
        sa.Column("snippet", sa.Text(), nullable=False),
        sa.Column("latest_classification", sa.String(length=50), nullable=False),
        sa.Column("last_checked_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("is_resolved", sa.Boolean(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["application_id"], ["applications.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_email_monitors_user_id", "email_monitors", ["user_id"])
    op.create_index("ix_email_monitors_application_id", "email_monitors", ["application_id"])
    op.create_index("ix_email_monitors_gmail_thread_id", "email_monitors", ["gmail_thread_id"])


def downgrade() -> None:
    op.drop_index("ix_email_monitors_gmail_thread_id", table_name="email_monitors")
    op.drop_index("ix_email_monitors_application_id", table_name="email_monitors")
    op.drop_index("ix_email_monitors_user_id", table_name="email_monitors")
    op.drop_table("email_monitors")
