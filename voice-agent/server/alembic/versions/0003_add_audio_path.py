"""add audio_path to interview sessions

Stores the filesystem path of the recorded interview audio (single merged WAV)
so HR can replay the conversation from the dashboard.

Revision ID: 0003_add_audio_path
Revises: 0002_link_candidate_job
Create Date: 2026-06-09
"""
from typing import Sequence, Union

from alembic import op

revision: str = "0003_add_audio_path"
down_revision: Union[str, None] = "0002_link_candidate_job"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute(
        """
        ALTER TABLE interview_sessions
            ADD COLUMN IF NOT EXISTS audio_path VARCHAR(500);
        """
    )


def downgrade() -> None:
    op.execute(
        """
        ALTER TABLE interview_sessions
            DROP COLUMN IF EXISTS audio_path;
        """
    )
