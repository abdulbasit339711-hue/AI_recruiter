from sqlalchemy import Column, Integer, String, Float, Text, ForeignKey
from sqlalchemy.orm import relationship
from .database import Base


class Job(Base):
    __tablename__ = "jobs"

    id = Column(Integer, primary_key=True, index=True)
    title = Column(String, index=True, nullable=False)
    department = Column(String, nullable=False)
    job_description = Column(Text, nullable=False)
    llm_prompt = Column(Text, nullable=True)
    status = Column(String, default="Active")
    created_at = Column(String, nullable=False)

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
    skills_matched = Column(Text, nullable=True)
    skills_missing = Column(Text, nullable=True)

    status = Column(String, default="Queued")
    created_at = Column(String, nullable=True)

    hr_status = Column(String, nullable=True, default=None)
    hr_notes = Column(Text, nullable=True, default=None)
    hr_score_override = Column(Float, nullable=True, default=None)
    status_history = Column(Text, nullable=True, default=None)

    job = relationship("Job", back_populates="candidates")
