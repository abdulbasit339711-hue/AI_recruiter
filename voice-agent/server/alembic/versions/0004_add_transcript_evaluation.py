"""add per-answer evaluation to transcript turns

Stores the real-time judge's per-message evaluation (score, depth, strengths, weaknesses,
follow-up) on each candidate transcript row so HR sees a per-answer assessment.

Revision ID: 0004_add_transcript_evaluation
Revises: 0003_add_audio_path
Create Date: 2026-06-09
"""
from typing import Sequence, Union

from alembic import op

revision: str = "0004_add_transcript_evaluation"
down_revision: Union[str, None] = "0003_add_audio_path"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute(
        """
        ALTER TABLE session_transcripts
            ADD COLUMN IF NOT EXISTS evaluation JSONB;
        """
    )


def downgrade() -> None:
    op.execute(
        """
        ALTER TABLE session_transcripts
            DROP COLUMN IF EXISTS evaluation;
        """
    )
