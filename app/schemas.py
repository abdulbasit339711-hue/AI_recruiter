from pydantic import BaseModel, Field, field_validator
from typing import Optional, List, Dict


# ── Pre-application IQ screen ──────────────────────────────────────────────────
class IqQuestionPublic(BaseModel):
    id: str
    prompt: str
    options: List[str]


class IqTestResponse(BaseModel):
    questions: List[IqQuestionPublic]
    test_token: str
    time_limit_seconds: int
    total: int


class IqSubmitRequest(BaseModel):
    test_token: str = Field(..., max_length=4096)
    answers: Dict[str, int]              # {question_id: chosen_option_index}
    times: Optional[Dict[str, int]] = None  # {question_id: seconds spent} (client-reported)

    @field_validator("answers")
    @classmethod
    def _bound_answers(cls, v: Dict[str, int]) -> Dict[str, int]:
        if len(v) > 100:
            raise ValueError("too many answers")
        for qid, idx in v.items():
            if len(qid) > 64:
                raise ValueError("question id too long")
            if not (0 <= idx < 50):
                raise ValueError("option index out of range")
        return v

    @field_validator("times")
    @classmethod
    def _bound_times(cls, v):
        if v and len(v) > 100:
            raise ValueError("too many time entries")
        return v


class IqSubmitResponse(BaseModel):
    correct: int
    total: int
    accuracy: float       # raw correct/total percentage
    score: float          # time-adjusted percentage 0–100
    time_seconds: int     # server-measured time taken
    detail: List[dict]    # per-question breakdown
    result_token: str

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

    # Pre-application IQ screen (server-scored; recorded, never gates).
    iq_score: Optional[float] = None
    iq_correct: Optional[int] = None
    iq_total: Optional[int] = None
    iq_time_seconds: Optional[int] = None
    iq_attempted_at: Optional[str] = None
    iq_details: Optional[str] = None  # JSON: per-question breakdown

    # Availability scheduling fields
    availability_invited_at: Optional[str] = None
    availability_response: Optional[str] = None
    availability_submitted_at: Optional[str] = None
    interview_confirmed_slot: Optional[str] = None
    interview_confirmed_at: Optional[str] = None

    model_config = {"from_attributes": True}


class AvailabilitySubmit(BaseModel):
    selected_slot: Optional[str] = None
    custom_time: Optional[str] = None


class SlotConfirm(BaseModel):
    slot: Optional[str] = None
