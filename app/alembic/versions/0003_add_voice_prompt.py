"""add voice_prompt column to jobs

Revision ID: 0003
Revises: 0002
Create Date: 2026-06-24
"""
from alembic import op
import sqlalchemy as sa

revision = "0003"
down_revision = "0002"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("jobs", sa.Column("voice_prompt", sa.Text(), nullable=True))


def downgrade() -> None:
    op.drop_column("jobs", "voice_prompt")
