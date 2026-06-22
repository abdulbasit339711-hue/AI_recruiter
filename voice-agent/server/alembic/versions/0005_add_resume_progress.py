"""add resume-progress columns to interview sessions

Lets an interrupted interview resume at the exact question it left off on. The
transcript (session_transcripts) already persists the conversation; these columns
persist the question-flow position so a re-opened link continues deterministically
instead of restarting from the intro.

- current_question_index: which question in the bank the candidate is on
- question_states: per-question status/follow-up snapshot (JSONB map keyed by question id)

Also widens valid_session_status to allow 'interrupted'. The resume design marks a
dropped interview 'interrupted' (so the link stays reusable), but the original CHECK
constraint only permitted active/completed/cancelled — so those writes silently failed
and interrupted sessions never persisted their status or final assessment.

Revision ID: 0005_add_resume_progress
Revises: 0004_add_transcript_evaluation
Create Date: 2026-06-10
"""
from typing import Sequence, Union

from alembic import op

revision: str = "0005_add_resume_progress"
down_revision: Union[str, None] = "0004_add_transcript_evaluation"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute(
        """
        ALTER TABLE interview_sessions
            ADD COLUMN IF NOT EXISTS current_question_index INTEGER NOT NULL DEFAULT 0,
            ADD COLUMN IF NOT EXISTS question_states JSONB NOT NULL DEFAULT '{}'::jsonb;

        ALTER TABLE interview_sessions DROP CONSTRAINT IF EXISTS valid_session_status;
        ALTER TABLE interview_sessions ADD CONSTRAINT valid_session_status
            CHECK (status IN ('active', 'completed', 'cancelled', 'interrupted'));
        """
    )


def downgrade() -> None:
    op.execute(
        """
        ALTER TABLE interview_sessions DROP CONSTRAINT IF EXISTS valid_session_status;
        ALTER TABLE interview_sessions ADD CONSTRAINT valid_session_status
            CHECK (status IN ('active', 'completed', 'cancelled'));

        ALTER TABLE interview_sessions
            DROP COLUMN IF EXISTS current_question_index,
            DROP COLUMN IF EXISTS question_states;
        """
    )
