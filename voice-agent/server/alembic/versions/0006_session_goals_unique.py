"""deduplicate session_goals and add unique constraint

Removes duplicate (session_id, goal_template_id) rows left by the double-init
race (process_frame + configure_session both calling initialize_goals before the
goals_initialized flag was set), then adds a UNIQUE constraint so the race is
harmless on new installs. The application-level fix (removing the redundant
auto-init from process_frame) ships in the same commit.

Revision ID: 0006_session_goals_unique
Revises: 0005_add_resume_progress
"""

from __future__ import annotations
from typing import Union
from alembic import op

revision: str = "0006_session_goals_unique"
down_revision: Union[str, None] = "0005_add_resume_progress"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Remove duplicates keeping the oldest row per (session_id, goal_template_id)
    op.execute("""
        DELETE FROM session_goals
        WHERE id NOT IN (
            SELECT DISTINCT ON (session_id, goal_template_id) id
            FROM session_goals
            ORDER BY session_id, goal_template_id, created_at
        )
    """)
    # Add unique constraint (idempotent — DO NOTHING if it already exists)
    op.execute("""
        ALTER TABLE session_goals
        ADD CONSTRAINT uq_session_goal UNIQUE (session_id, goal_template_id)
    """)


def downgrade() -> None:
    op.execute("ALTER TABLE session_goals DROP CONSTRAINT IF EXISTS uq_session_goal")
