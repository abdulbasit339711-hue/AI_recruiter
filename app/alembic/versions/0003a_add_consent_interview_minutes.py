"""add candidates.consent_at and jobs.interview_minutes

Idempotent: the app runs Base.metadata.create_all() BEFORE `alembic upgrade head`, so a
fresh database already has these columns (the models define them) — only existing
databases need them added.

Revision ID: 0003a
Revises: 0003
"""
from alembic import op
import sqlalchemy as sa

revision = "0003a"
down_revision = "0003"
branch_labels = None
depends_on = None

_COLUMNS = (
    ("candidates", "consent_at", sa.String()),
    ("jobs", "interview_minutes", sa.Integer()),
)


def _has_column(table: str, column: str) -> bool:
    return column in {c["name"] for c in sa.inspect(op.get_bind()).get_columns(table)}


def upgrade() -> None:
    for table, column, type_ in _COLUMNS:
        if not _has_column(table, column):
            with op.batch_alter_table(table) as batch:
                batch.add_column(sa.Column(column, type_, nullable=True))


def downgrade() -> None:
    for table, column, _ in reversed(_COLUMNS):
        if _has_column(table, column):
            with op.batch_alter_table(table) as batch:
                batch.drop_column(column)
