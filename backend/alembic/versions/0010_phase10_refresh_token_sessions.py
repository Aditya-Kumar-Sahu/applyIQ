"""phase 10 refresh token sessions

Revision ID: 0010_phase10_tkns
Revises: 0009_phase9_email_tracking
Create Date: 2026-03-28 20:00:00.000000
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa


revision = "0010_phase10_tkns"
down_revision = "0009_phase9_email_tracking"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "refresh_token_sessions",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("user_id", sa.String(length=36), nullable=False),
        sa.Column("token_hash", sa.String(length=64), nullable=False),
        sa.Column("issued_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("revoked_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("replaced_by_token_hash", sa.String(length=64), nullable=True),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("token_hash"),
    )
    op.create_index("ix_refresh_token_sessions_user_id", "refresh_token_sessions", ["user_id"], unique=False)
    op.create_index("ix_refresh_token_sessions_token_hash", "refresh_token_sessions", ["token_hash"], unique=True)


def downgrade() -> None:
    op.drop_index("ix_refresh_token_sessions_token_hash", table_name="refresh_token_sessions")
    op.drop_index("ix_refresh_token_sessions_user_id", table_name="refresh_token_sessions")
    op.drop_table("refresh_token_sessions")
