"""Add employee_documents table and HR profiling fields to candidates

Revision ID: 0004
Revises: 0003a
Create Date: 2026-09-21
"""
from alembic import op
import sqlalchemy as sa

revision = "0004"
down_revision = "0003a"
branch_labels = None
depends_on = None


_COLUMNS = [
    ("address", sa.Text()), ("date_of_birth", sa.String()), ("national_id", sa.String()),
    ("employee_id", sa.String()), ("department", sa.String()), ("emergency_contact", sa.Text()),
    ("profile_summary", sa.Text()), ("profile_skills", sa.Text()), ("profile_certifications", sa.Text()),
]


def _columns(table: str) -> set[str]:
    return {c["name"] for c in sa.inspect(op.get_bind()).get_columns(table)}


def upgrade() -> None:
    # Idempotent: the app runs Base.metadata.create_all() BEFORE `alembic upgrade head`, so a
    # fresh database already has these columns/table from the models — only add what's missing.
    # ── New columns on candidates ──────────────────────────────────────────
    existing = _columns("candidates")
    missing = [(n, t) for n, t in _COLUMNS if n not in existing]
    if missing:
        with op.batch_alter_table("candidates") as batch_op:
            for name, type_ in missing:
                batch_op.add_column(sa.Column(name, type_, nullable=True))

    # ── New employee_documents table ──────────────────────────────────────
    if "employee_documents" in sa.inspect(op.get_bind()).get_table_names():
        return
    op.create_table(
        "employee_documents",
        sa.Column("id",               sa.Integer(), primary_key=True),
        sa.Column("candidate_id",     sa.Integer(), sa.ForeignKey("candidates.id", ondelete="CASCADE"), nullable=False, index=True),
        sa.Column("filename",         sa.String(),  nullable=False),
        sa.Column("file_type",        sa.String(),  nullable=True),
        sa.Column("file_size_kb",     sa.Integer(), nullable=True),
        sa.Column("ocr_used",         sa.Boolean(), default=False),
        sa.Column("document_type",    sa.String(),  nullable=True),
        sa.Column("raw_text",         sa.Text(),    nullable=True),
        sa.Column("extracted_fields", sa.Text(),    nullable=True),
        sa.Column("file_data",        sa.LargeBinary(), nullable=True),
        sa.Column("uploaded_by",      sa.String(),  nullable=True),
        sa.Column("uploaded_at",      sa.String(),  nullable=True),
    )


def downgrade() -> None:
    if "employee_documents" in sa.inspect(op.get_bind()).get_table_names():
        op.drop_table("employee_documents")
    present = [n for n, _ in _COLUMNS if n in _columns("candidates")]
    if present:
        with op.batch_alter_table("candidates") as batch_op:
            for col in present:
                batch_op.drop_column(col)
