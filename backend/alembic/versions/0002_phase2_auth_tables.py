"""phase 2 auth tables

Revision ID: 0002_phase2_auth_tables
Revises: 0001_phase1_bootstrap
Create Date: 2026-03-23 22:30:00
"""
from __future__ import annotations

from alembic import op
import sqlalchemy as sa


revision = "0002_phase2_auth_tables"
down_revision = "0001_phase1_bootstrap"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "users",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column("email", sa.String(length=320), nullable=False),
        sa.Column("hashed_password", sa.String(length=255), nullable=False),
        sa.Column("full_name", sa.String(length=255), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("last_login", sa.DateTime(timezone=True), nullable=True),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("subscription_tier", sa.String(length=20), nullable=False, server_default="free"),
    )
    op.create_index("ix_users_email", "users", ["email"], unique=True)

    op.create_table(
        "credential_vault",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column("user_id", sa.String(length=36), nullable=False),
        sa.Column("site_name", sa.String(length=100), nullable=False),
        sa.Column("site_url", sa.String(length=255), nullable=False),
        sa.Column("encrypted_username", sa.String(), nullable=False),
        sa.Column("encrypted_password", sa.String(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("last_used_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
    )
    op.create_index("ix_credential_vault_user_id", "credential_vault", ["user_id"], unique=False)


def downgrade() -> None:
    op.drop_index("ix_credential_vault_user_id", table_name="credential_vault")
    op.drop_table("credential_vault")
    op.drop_index("ix_users_email", table_name="users")
    op.drop_table("users")
