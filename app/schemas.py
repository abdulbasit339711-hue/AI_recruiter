from pydantic import BaseModel, Field, field_validator
from typing import Optional, List

class StatusUpdateRequest(BaseModel):
    hr_status: str
    changed_by: str
    note: Optional[str] = None

    @field_validator("hr_status")
    @classmethod
    def validate_hr_status(cls, v: str) -> str:
        valid_statuses = ["Applied", "Screened", "Interview", "Offer", "Hired", "Rejected"]
        if v not in valid_statuses:
            raise ValueError(f"hr_status must be one of {valid_statuses}")
        return v

class NoteRequest(BaseModel):
    note: str
    author: str

class ScoreOverrideRequest(BaseModel):
    override_score: float
    reason: str
    changed_by: str

    @field_validator("override_score")
    @classmethod
    def validate_score(cls, v: float) -> float:
        if not (0.0 <= v <= 100.0):
            raise ValueError("override_score must be between 0.0 and 100.0")
        return v

class TimelineEntry(BaseModel):
    type: str
    status: str
    changed_by: str
    changed_at: str
    note: Optional[str] = None

class TimelineResponse(BaseModel):
    timeline: List[TimelineEntry]

class CandidateResponse(BaseModel):
    id: int
    filename: str
    name: Optional[str] = None
    phone: Optional[str] = None
    email: Optional[str] = None
    raw_text: Optional[str] = None
    job_id: Optional[int] = None
    tier1: float
    tier2: float
    tier3: float
    total_score: float
    summary: Optional[str] = None
    evidence: Optional[str] = None
    warnings: Optional[str] = None
    evaluation_data: Optional[str] = None
    current_role: Optional[str] = None
    companies: Optional[str] = None
    years_experience: Optional[float] = None
    skills_matched: Optional[str] = None
    skills_missing: Optional[str] = None
    interview_questions: Optional[str] = None
    status: str
    created_at: Optional[str] = None
    
    # New fields
    hr_status: Optional[str] = None
    hr_notes: Optional[str] = None
    hr_score_override: Optional[float] = None
    status_history: Optional[str] = None

    model_config = {"from_attributes": True}
