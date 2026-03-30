"""restore uniqueness constraints

Revision ID: 1f3d2e4c5b6a
Revises: 699751a0fd51
Create Date: 2026-03-30 17:00:00
"""
from __future__ import annotations

from alembic import op
import sqlalchemy as sa
from sqlalchemy import inspect


# revision identifiers, used by Alembic.
revision = "1f3d2e4c5b6a"
down_revision = "699751a0fd51"
branch_labels = None
depends_on = None


_UNIQUE_CONSTRAINTS: tuple[tuple[str, str, tuple[str, ...], str], ...] = (
    ("jobs", "uq_jobs_apply_url", ("apply_url",), "scraped_at"),
    ("refresh_token_sessions", "uq_refresh_token_sessions_token_hash", ("token_hash",), "issued_at"),
    ("resume_profiles", "uq_resume_profiles_user_id", ("user_id",), "updated_at"),
    ("search_preferences", "uq_search_preferences_user_id", ("user_id",), "id"),
)


def upgrade() -> None:
    bind = op.get_bind()
    for table_name, constraint_name, column_names, order_column in _UNIQUE_CONSTRAINTS:
        _dedupe_rows(table_name, column_names, order_column)
        _ensure_unique_constraint(bind, table_name, constraint_name, column_names)
    _ensure_application_demo_flag(bind)


def downgrade() -> None:
    bind = op.get_bind()
    for table_name, constraint_name, column_names, _ in _UNIQUE_CONSTRAINTS:
        _drop_unique_constraint(bind, table_name, constraint_name, column_names)
    if _column_exists(bind, "applications", "is_demo"):
        op.drop_column("applications", "is_demo")


def _dedupe_rows(table_name: str, column_names: tuple[str, ...], order_column: str) -> None:
    if len(column_names) == 0:
        return

    partition_clause = ", ".join(column_names)
    op.execute(
        sa.text(
            f"""
            DELETE FROM {table_name}
            WHERE id IN (
                SELECT id
                FROM (
                    SELECT
                        id,
                        ROW_NUMBER() OVER (
                            PARTITION BY {partition_clause}
                            ORDER BY {order_column} DESC, id DESC
                        ) AS row_number
                    FROM {table_name}
                ) AS ranked_rows
                WHERE row_number > 1
            )
            """
        )
    )


def _ensure_unique_constraint(
    bind,
    table_name: str,
    constraint_name: str,
    column_names: tuple[str, ...],
) -> None:
    inspector = inspect(bind)
    existing_constraint = _find_unique_constraint(inspector, table_name, column_names)

    if existing_constraint is not None:
        if existing_constraint.get("name") == constraint_name:
            return
        if bind.dialect.name == "postgresql":
            op.execute(
                sa.text(
                    f'ALTER TABLE "{table_name}" RENAME CONSTRAINT "{existing_constraint["name"]}" TO "{constraint_name}"'
                )
            )
        return

    if bind.dialect.name == "sqlite":
        with op.batch_alter_table(table_name) as batch_op:
            batch_op.create_unique_constraint(constraint_name, list(column_names))
        return

    op.create_unique_constraint(constraint_name, table_name, list(column_names))


def _drop_unique_constraint(
    bind,
    table_name: str,
    constraint_name: str,
    column_names: tuple[str, ...],
) -> None:
    inspector = inspect(bind)
    existing_constraint = _find_unique_constraint(inspector, table_name, column_names)

    if existing_constraint is None:
        return

    if bind.dialect.name == "sqlite":
        with op.batch_alter_table(table_name) as batch_op:
            batch_op.drop_constraint(existing_constraint["name"], type_="unique")
        return

    op.drop_constraint(existing_constraint["name"], table_name, type_="unique")


def _find_unique_constraint(
    inspector,
    table_name: str,
    column_names: tuple[str, ...],
) -> dict[str, object] | None:
    target_columns = list(column_names)
    for constraint in inspector.get_unique_constraints(table_name):
        if list(constraint.get("column_names", [])) == target_columns:
            return constraint
    return None


def _ensure_application_demo_flag(bind) -> None:
    if _column_exists(bind, "applications", "is_demo"):
        return

    op.add_column(
        "applications",
        sa.Column("is_demo", sa.Boolean(), nullable=False, server_default=sa.false()),
    )


def _column_exists(bind, table_name: str, column_name: str) -> bool:
    inspector = inspect(bind)
    return column_name in {column["name"] for column in inspector.get_columns(table_name)}
