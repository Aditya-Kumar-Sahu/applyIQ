"""add composite indexes

Revision ID: e17d65c3b9a0
Revises: d46c487e0236
Create Date: 2026-05-10 10:00:00.000000
"""
from __future__ import annotations

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = 'e17d65c3b9a0'
down_revision = 'd46c487e0236'
branch_labels = None
depends_on = None

def upgrade() -> None:
    # Applications: user_id + status for optimized listing
    op.create_index('ix_applications_user_status', 'applications', ['user_id', 'status'], unique=False)
    # Applications: user_id + job_id for faster duplicate checks
    op.create_index('ix_applications_user_job', 'applications', ['user_id', 'job_id'], unique=False)
    # Job Matches: user_id + match_score DESC for ranked dashboard
    op.create_index('ix_job_matches_user_score', 'job_matches', ['user_id', sa.text('match_score DESC')], unique=False)

def downgrade() -> None:
    op.drop_index('ix_job_matches_user_score', table_name='job_matches')
    op.drop_index('ix_applications_user_job', table_name='applications')
    op.drop_index('ix_applications_user_status', table_name='applications')
