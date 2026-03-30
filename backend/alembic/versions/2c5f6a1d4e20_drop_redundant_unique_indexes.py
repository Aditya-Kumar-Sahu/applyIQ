"""drop redundant unique indexes

Revision ID: 2c5f6a1d4e20
Revises: 1f3d2e4c5b6a
Create Date: 2026-03-30 21:54:00.000000
"""

from __future__ import annotations

from alembic import op
from sqlalchemy import inspect


revision = "2c5f6a1d4e20"
down_revision = "1f3d2e4c5b6a"
branch_labels = None
depends_on = None


_REDUNDANT_INDEXES: tuple[tuple[str, str], ...] = (
    ("jobs", "ix_jobs_apply_url"),
    ("refresh_token_sessions", "ix_refresh_token_sessions_token_hash"),
    ("resume_profiles", "ix_resume_profiles_user_id"),
    ("search_preferences", "ix_search_preferences_user_id"),
)


def upgrade() -> None:
    bind = op.get_bind()
    for table_name, index_name in _REDUNDANT_INDEXES:
        _drop_index_if_exists(bind, table_name, index_name)


def downgrade() -> None:
    bind = op.get_bind()
    for table_name, index_name in _REDUNDANT_INDEXES:
        _create_index_if_missing(bind, table_name, index_name)


def _drop_index_if_exists(bind, table_name: str, index_name: str) -> None:
    inspector = inspect(bind)
    if any(index.get("name") == index_name for index in inspector.get_indexes(table_name)):
        op.drop_index(index_name, table_name=table_name)


def _create_index_if_missing(bind, table_name: str, index_name: str) -> None:
    inspector = inspect(bind)
    if any(index.get("name") == index_name for index in inspector.get_indexes(table_name)):
        return

    column_name = {
        "ix_jobs_apply_url": "apply_url",
        "ix_refresh_token_sessions_token_hash": "token_hash",
        "ix_resume_profiles_user_id": "user_id",
        "ix_search_preferences_user_id": "user_id",
    }[index_name]
    op.create_index(index_name, table_name, [column_name], unique=True)
