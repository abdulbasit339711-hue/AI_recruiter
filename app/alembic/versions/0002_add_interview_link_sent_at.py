"""add interview_link_sent_at column

Revision ID: 0002
Revises: 0001
Create Date: 2026-06-24
"""
from alembic import op
import sqlalchemy as sa

revision = "0002"
down_revision = "0001_initial"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("candidates", sa.Column("interview_link_sent_at", sa.String(), nullable=True))


def downgrade() -> None:
    op.drop_column("candidates", "interview_link_sent_at")
