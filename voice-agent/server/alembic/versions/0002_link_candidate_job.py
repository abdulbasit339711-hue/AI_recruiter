"""link interview sessions to candidate & job

Adds nullable candidate_id / job_id to interview_sessions so an interview can be
tied back to the main app's candidates/jobs records. No cross-table FK yet — that
is added in a later revision once the main app's tables live in the same
PostgreSQL database (see plan Phase 1, open decision #3).

Revision ID: 0002_link_candidate_job
Revises: 0001_initial_schema
Create Date: 2026-06-08
"""
from typing import Sequence, Union

from alembic import op

revision: str = "0002_link_candidate_job"
down_revision: Union[str, None] = "0001_initial_schema"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute(
        """
        ALTER TABLE interview_sessions
            ADD COLUMN IF NOT EXISTS candidate_id INTEGER,
            ADD COLUMN IF NOT EXISTS job_id INTEGER;
        CREATE INDEX IF NOT EXISTS idx_sessions_candidate ON interview_sessions(candidate_id);
        CREATE INDEX IF NOT EXISTS idx_sessions_job ON interview_sessions(job_id);
        """
    )


def downgrade() -> None:
    op.execute(
        """
        DROP INDEX IF EXISTS idx_sessions_job;
        DROP INDEX IF EXISTS idx_sessions_candidate;
        ALTER TABLE interview_sessions
            DROP COLUMN IF EXISTS job_id,
            DROP COLUMN IF EXISTS candidate_id;
        """
    )
