"""Initial schema — full baseline for new installations.

Existing databases are stamped to this revision automatically by env.py
(see _stamp_existing_if_needed) so this migration is skipped on them.

Revision ID: 0001_initial
Revises: —
Create Date: 2026-06-23
"""

from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa

revision: str = "0001_initial"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # --- orgs ---------------------------------------------------------------
    op.create_table(
        "orgs",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("slug", sa.String, nullable=False, unique=True),
        sa.Column("name", sa.String, nullable=False),
        sa.Column("primary_color", sa.String),
        sa.Column("logo_url", sa.String),
        sa.Column("tagline", sa.String),
        sa.Column("about", sa.Text),
        sa.Column("contact_email", sa.String),
        sa.Column("social_links", sa.Text),
        sa.Column("created_at", sa.String),
    )

    # --- jobs ---------------------------------------------------------------
    op.create_table(
        "jobs",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("title", sa.String, nullable=False),
        sa.Column("department", sa.String),
        sa.Column("job_description", sa.Text),
        sa.Column("llm_prompt", sa.Text),
        sa.Column("status", sa.String, default="Active"),
        sa.Column("created_at", sa.String),
        sa.Column("role_type", sa.String),
        sa.Column("tier1_weight", sa.Float, default=1.0),
        sa.Column("tier2_weight", sa.Float, default=1.0),
        sa.Column("tier3_weight", sa.Float, default=1.0),
        sa.Column("org_id", sa.Integer, sa.ForeignKey("orgs.id")),
        sa.Column("resume_deadline", sa.String),
        sa.Column("interview_deadline", sa.String),
    )

    # --- candidates ---------------------------------------------------------
    op.create_table(
        "candidates",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("filename", sa.String),
        sa.Column("name", sa.String),
        sa.Column("email", sa.String),
        sa.Column("raw_text", sa.Text),
        sa.Column("job_id", sa.Integer, sa.ForeignKey("jobs.id")),
        sa.Column("tier1", sa.Float),
        sa.Column("tier2", sa.Float),
        sa.Column("tier3", sa.Float),
        sa.Column("total_score", sa.Float),
        sa.Column("summary", sa.Text),
        sa.Column("evidence", sa.Text),
        sa.Column("status", sa.String, default="Pending"),
        sa.Column("created_at", sa.String),
        sa.Column("warnings", sa.Text),
        sa.Column("evaluation_data", sa.Text),
        sa.Column("current_role", sa.String),
        sa.Column("companies", sa.Text),
        sa.Column("skills_matched", sa.Text),
        sa.Column("skills_missing", sa.Text),
        sa.Column("hr_status", sa.String),
        sa.Column("hr_notes", sa.Text),
        sa.Column("hr_score_override", sa.Float),
        sa.Column("status_history", sa.Text),
        sa.Column("interview_invited_at", sa.String),
        sa.Column("llm_prompt_tokens", sa.Integer),
        sa.Column("llm_completion_tokens", sa.Integer),
        sa.Column("llm_cost_usd", sa.Float),
        sa.Column("years_experience", sa.Float),
        sa.Column("interview_questions", sa.Text),
        sa.Column("iq_score", sa.Float),
        sa.Column("iq_correct", sa.Integer),
        sa.Column("iq_total", sa.Integer),
        sa.Column("iq_time_seconds", sa.Integer),
        sa.Column("iq_attempted_at", sa.String),
        sa.Column("iq_details", sa.Text),
        sa.Column("iq_result_jti", sa.String),
        sa.Column("availability_invited_at", sa.String),
        sa.Column("availability_response", sa.String),
        sa.Column("availability_submitted_at", sa.String),
        sa.Column("interview_confirmed_slot", sa.String),
        sa.Column("interview_confirmed_at", sa.String),
        sa.Column("interview_token", sa.String),
        sa.Column("github_url", sa.String),
        sa.Column("linkedin_url", sa.String),
        sa.Column("projects", sa.Text),
        sa.Column("certifications", sa.Text),
        sa.Column("interview_completed_at", sa.String),
        sa.Column("interview_phase1_score", sa.Float),
        sa.Column("interview_phase2_score", sa.Float),
        sa.Column("interview_overall_score", sa.Float),
        sa.Column("interview_passed", sa.Boolean),
    )

    # --- settings -----------------------------------------------------------
    op.create_table(
        "settings",
        sa.Column("key", sa.String, primary_key=True),
        sa.Column("value", sa.Text, nullable=False),
        sa.Column("description", sa.Text),
    )

    # --- IQ test jti blacklist (prevents replay across restarts) -----------
    op.create_table(
        "used_iq_test_tokens",
        sa.Column("jti", sa.String, primary_key=True),
        sa.Column("used_at", sa.String, nullable=False),
    )

    # Seed default settings
    op.execute(
        "INSERT INTO settings (key, value, description) VALUES "
        "('availability_threshold', '60', "
        "'Minimum total score (0–100) required to auto-send the availability scheduling form.')"
        " ON CONFLICT (key) DO NOTHING"
    )


def downgrade() -> None:
    op.drop_table("used_iq_test_tokens")
    op.drop_table("settings")
    op.drop_table("candidates")
    op.drop_table("jobs")
    op.drop_table("orgs")
