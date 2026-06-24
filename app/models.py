from sqlalchemy import Boolean, Column, Integer, String, Float, Text, ForeignKey
from sqlalchemy.orm import relationship
from .database import Base


class Setting(Base):
    __tablename__ = "settings"

    key = Column(String, primary_key=True, nullable=False)
    value = Column(Text, nullable=False)
    description = Column(Text, nullable=True)


class Org(Base):
    __tablename__ = "orgs"

    id = Column(Integer, primary_key=True, index=True)
    slug = Column(String, unique=True, nullable=False, index=True)
    name = Column(String, nullable=False)
    primary_color = Column(String, default="#1C99BF")
    logo_url = Column(String, nullable=True)
    tagline = Column(String, nullable=True)
    about = Column(Text, nullable=True)
    contact_email = Column(String, nullable=True)
    social_links = Column(Text, nullable=True)  # JSON: {"website":…, "linkedin":…, "twitter":…}
    created_at = Column(String, nullable=False)

    jobs = relationship("Job", back_populates="org")


class Job(Base):
    __tablename__ = "jobs"

    id = Column(Integer, primary_key=True, index=True)
    title = Column(String, index=True, nullable=False)
    department = Column(String, nullable=False)
    job_description = Column(Text, nullable=False)
    llm_prompt = Column(Text, nullable=True)
    voice_prompt = Column(Text, nullable=True)   # extra instructions appended to Emily's system prompt
    # Optional explicit interview role slug (e.g. "backend_engineer"); defaults to a
    # normalized form of the title when blank. Drives goal_templates lookup.
    role_type = Column(String, nullable=True)
    status = Column(String, default="Active")
    created_at = Column(String, nullable=False)

    # Per-job scoring weights: multipliers applied to each tier in the final total
    # (default 1.0 → the plain tier sum). Lets HR re-weight tiers per role.
    tier1_weight = Column(Float, default=1.0)
    tier2_weight = Column(Float, default=1.0)
    tier3_weight = Column(Float, default=1.0)

    org_id = Column(Integer, ForeignKey("orgs.id", ondelete="SET NULL"), nullable=True)
    org = relationship("Org", back_populates="jobs")

    # Soft deadline dates (ISO date string, e.g. "2025-03-31"); informational only.
    resume_deadline = Column(String, nullable=True)
    interview_deadline = Column(String, nullable=True)

    candidates = relationship("Candidate", back_populates="job", cascade="all, delete-orphan")


class Candidate(Base):
    __tablename__ = "candidates"

    id = Column(Integer, primary_key=True, index=True)
    filename = Column(String, index=True)
    name = Column(String, nullable=True)
    phone = Column(String, nullable=True)
    email = Column(String, nullable=True)
    raw_text = Column(Text, nullable=True)

    job_id = Column(Integer, ForeignKey("jobs.id", ondelete="CASCADE"), nullable=True)

    tier1 = Column(Float, default=0.0)
    tier2 = Column(Float, default=0.0)
    tier3 = Column(Float, default=0.0)
    total_score = Column(Float, default=0.0)

    summary = Column(Text, nullable=True)
    evidence = Column(Text, nullable=True)
    warnings = Column(Text, nullable=True)
    evaluation_data = Column(Text, nullable=True)

    current_role = Column(String, nullable=True)
    companies = Column(Text, nullable=True)
    years_experience = Column(Float, nullable=True)
    skills_matched = Column(Text, nullable=True)
    skills_missing = Column(Text, nullable=True)
    # Résumé-tailored interview questions (JSON list) generated during Tier-3 scoring;
    # used as interviewer presets and shown in the HR panel.
    interview_questions = Column(Text, nullable=True)

    status = Column(String, default="Queued")
    created_at = Column(String, nullable=True)

    hr_status = Column(String, nullable=True, default=None)
    hr_notes = Column(Text, nullable=True, default=None)
    hr_score_override = Column(Float, nullable=True, default=None)
    status_history = Column(Text, nullable=True, default=None)

    # Timestamp (ISO string) when the interview invite email was sent; used to
    # avoid re-sending on reprocess.
    interview_invited_at = Column(String, nullable=True, default=None)

    # Availability scheduling: sent when candidate clears the score threshold.
    availability_invited_at = Column(String, nullable=True, default=None)
    availability_response = Column(String, nullable=True, default=None)     # chosen slot text
    availability_submitted_at = Column(String, nullable=True, default=None) # when candidate submitted
    interview_confirmed_slot = Column(String, nullable=True, default=None)  # HR-confirmed slot
    interview_confirmed_at = Column(String, nullable=True, default=None)    # when HR confirmed
    interview_token = Column(String, nullable=True, default=None)           # minted when slot confirmed
    interview_link_sent_at = Column(String, nullable=True, default=None)    # when 30-min reminder was sent

    # Tier-3 (resume scoring) LLM token usage + estimated cost, surfaced to HR.
    llm_prompt_tokens = Column(Integer, nullable=True, default=None)
    llm_completion_tokens = Column(Integer, nullable=True, default=None)
    llm_cost_usd = Column(Float, nullable=True, default=None)

    # Pre-application IQ screen (server-scored). Recorded for HR ranking; never
    # gates the application. iq_score is the time-adjusted percentage (0–100);
    # correct/total are the raw accuracy; iq_time_seconds is the server-measured
    # duration; iq_attempted_at is when it was submitted (ISO).
    iq_score = Column(Float, nullable=True, default=None)
    iq_correct = Column(Integer, nullable=True, default=None)
    iq_total = Column(Integer, nullable=True, default=None)
    iq_time_seconds = Column(Integer, nullable=True, default=None)
    iq_attempted_at = Column(String, nullable=True, default=None)
    # Per-question breakdown (JSON list): prompt, options, chosen, correct, is_correct,
    # time_seconds — shown in the HR "Aptitude screen" block.
    iq_details = Column(Text, nullable=True, default=None)
    # jti of the IQ result token consumed at upload — makes the token single-use so the
    # same signed score can't be replayed onto multiple candidate uploads.
    iq_result_jti = Column(String, nullable=True, default=None)

    # Enriched resume profile — extracted during Tier 1 scoring
    github_url = Column(String, nullable=True, default=None)
    linkedin_url = Column(String, nullable=True, default=None)
    projects = Column(Text, nullable=True, default=None)        # JSON list of project names
    certifications = Column(Text, nullable=True, default=None)  # JSON list of certifications

    # Voice AI interview result — written back by the voice agent after the session ends
    interview_completed_at = Column(String, nullable=True, default=None)  # ISO timestamp
    interview_phase1_score = Column(Float, nullable=True, default=None)   # behavioral phase (0-60 gate)
    interview_phase2_score = Column(Float, nullable=True, default=None)   # technical phase
    interview_overall_score = Column(Float, nullable=True, default=None)  # combined 0-100
    interview_passed = Column(Boolean, nullable=True, default=None)        # cleared both phases

    job = relationship("Job", back_populates="candidates")
