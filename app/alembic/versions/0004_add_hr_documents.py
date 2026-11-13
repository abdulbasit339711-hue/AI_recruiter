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


def upgrade() -> None:
    # ── New columns on candidates ──────────────────────────────────────────
    with op.batch_alter_table("candidates") as batch_op:
        batch_op.add_column(sa.Column("address",               sa.Text(),   nullable=True))
        batch_op.add_column(sa.Column("date_of_birth",         sa.String(), nullable=True))
        batch_op.add_column(sa.Column("national_id",           sa.String(), nullable=True))
        batch_op.add_column(sa.Column("employee_id",           sa.String(), nullable=True))
        batch_op.add_column(sa.Column("department",            sa.String(), nullable=True))
        batch_op.add_column(sa.Column("emergency_contact",     sa.Text(),   nullable=True))
        batch_op.add_column(sa.Column("profile_summary",       sa.Text(),   nullable=True))
        batch_op.add_column(sa.Column("profile_skills",        sa.Text(),   nullable=True))
        batch_op.add_column(sa.Column("profile_certifications",sa.Text(),   nullable=True))

    # ── New employee_documents table ──────────────────────────────────────
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
    op.drop_table("employee_documents")
    with op.batch_alter_table("candidates") as batch_op:
        for col in [
            "address", "date_of_birth", "national_id", "employee_id",
            "department", "emergency_contact", "profile_summary",
            "profile_skills", "profile_certifications",
        ]:
            batch_op.drop_column(col)
