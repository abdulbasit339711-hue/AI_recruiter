"""rename pipeline status 'Rejected' -> 'Not recommended'

The automatic pipeline label is advisory, not a decision, so it no longer reads like one.
Only candidates.status changes; the HR-set candidates.hr_status 'Rejected' (a human decision) does not.
Re-runnable: it just updates whatever rows still carry the old value.

Revision ID: 0005
Revises: 0004
"""
from alembic import op

revision = "0005"
down_revision = "0004"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("UPDATE candidates SET status = 'Not recommended' WHERE status = 'Rejected'")


def downgrade() -> None:
    op.execute("UPDATE candidates SET status = 'Rejected' WHERE status = 'Not recommended'")
