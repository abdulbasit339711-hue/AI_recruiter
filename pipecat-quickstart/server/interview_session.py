# interview_session.py

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Optional, List, Dict
from uuid import uuid4


# ── Enums ──────────────────────────────────────────────────────────────────────

class InterviewStatus(Enum):
    PENDING     = "pending"      # created, candidate not yet joined
    ACTIVE      = "active"       # candidate is on the call
    PAUSED      = "paused"       # candidate dropped, awaiting rejoin
    COMPLETED   = "completed"    # all questions done or time limit hit
    ABORTED     = "aborted"      # ended early due to technical failure


class AnswerDepth(Enum):
    SHORT   = "short"    # one-liners, greetings, yes/no
    MEDIUM  = "medium"   # 2–4 sentences expected
    LONG    = "long"     # detailed technical or behavioral answer expected


class GoalStatus(Enum):
    PENDING     = "pending"      # not yet asked
    IN_PROGRESS = "in_progress"  # question asked, waiting for answer
    COVERED     = "covered"      # answer was sufficient
    WEAK        = "weak"         # answer was insufficient, follow-up used
    SKIPPED     = "skipped"      # intentionally skipped


# ── Recruiter config layer (immutable after init) ───────────────────────────────

@dataclass
class FollowUpPrompt:
    """A follow-up question to use when the primary answer is weak."""
    text: str
    trigger_reason: str  # e.g. "answer too short", "no example given"


@dataclass
class InterviewQuestion:
    """One question in the recruiter's question bank."""
    id: str
    text: str                           # what the AI will ask
    goal_id: str                        # which goal this question covers
    expected_depth: AnswerDepth         # how long an answer should be
    expected_theme: str                 # for evaluator — what a good answer covers
    follow_ups: List[FollowUpPrompt] = field(default_factory=list)
    is_mandatory: bool = True           # if False, can be skipped if time is short


@dataclass
class InterviewGoal:
    """A topic or competency the recruiter wants assessed."""
    id: str
    label: str          # e.g. "problem solving", "communication"
    description: str    # what a strong answer looks like
    weight: float       # 0.0–1.0, used in final scoring


@dataclass
class RecruiterConfig:
    """
    Everything the recruiter sets up before the interview.
    This never changes once the session starts.
    """
    job_role: str
    company_name: str
    interview_type: str             # e.g. "technical", "behavioural", "mixed"
    system_prompt: str              # the AI interviewer's persona and instructions
    questions: List[InterviewQuestion]
    goals: List[InterviewGoal]
    time_limit_seconds: int = 1800  # default 30 minutes
    max_follow_ups_per_question: int = 2
    language: str = "en"

    def get_question(self, question_id: str) -> Optional[InterviewQuestion]:
        return next((q for q in self.questions if q.id == question_id), None)

    def get_goal(self, goal_id: str) -> Optional[InterviewGoal]:
        return next((g for g in self.goals if g.id == goal_id), None)


# ── Transcript layer (append-only) ─────────────────────────────────────────────

@dataclass
class TranscriptTurn:
    """One turn in the conversation."""
    speaker: str            # "agent" or "candidate"
    text: str
    timestamp: datetime
    question_id: Optional[str] = None   # which question was active
    is_follow_up: bool = False


# ── Live state layer (mutates during interview) ─────────────────────────────────

@dataclass
class QuestionState:
    """Tracks the live state of one question during the interview."""
    question_id: str
    goal_id: str
    status: GoalStatus = GoalStatus.PENDING
    follow_up_count: int = 0
    asked_at: Optional[datetime] = None
    answered_at: Optional[datetime] = None


@dataclass
class ConnectionEvent:
    """Records connection quality events for post-call analysis."""
    event_type: str     # "dropped", "rejoined", "degraded", "restored"
    timestamp: datetime
    detail: str = ""


# ── Root session object ─────────────────────────────────────────────────────────

@dataclass
class InterviewSession:
    """
    Single source of truth for one candidate interview.

    Rules:
    - config: set at creation, never mutated
    - state fields: only mutated by QuestionFlowProcessor
    - transcript: append-only, never mutated
    - everything else reads from here, nothing else owns state
    """

    # Identity
    session_id: str = field(default_factory=lambda: str(uuid4()))
    candidate_id: str = ""
    candidate_name: str = ""

    # Recruiter config — immutable after init
    config: RecruiterConfig = field(default_factory=lambda: RecruiterConfig(
        job_role="", company_name="", interview_type="",
        system_prompt="", questions=[], goals=[]
    ))

    # Live state
    status: InterviewStatus = InterviewStatus.PENDING
    current_question_index: int = 0
    question_states: Dict[str, QuestionState] = field(default_factory=dict)
    started_at: Optional[datetime] = None
    ended_at: Optional[datetime] = None
    connection_events: List[ConnectionEvent] = field(default_factory=list)

    # Transcript — append only
    transcript: List[TranscriptTurn] = field(default_factory=list)

    # Dashboard state
    evaluations: List[Dict] = field(default_factory=list)
    metrics: List[Dict] = field(default_factory=list)
    current_goal_id: Optional[str] = None
    session_timeout_seconds: int = 300  # 5 minutes default
    auto_kill_on_disconnect: bool = False

    # Service Status tracking
    service_status: Dict[str, str] = field(default_factory=lambda: {
        "STT": "offline",
        "LLM": "offline",
        "TTS": "offline"
    })

    def __post_init__(self):
        """Initialize question states from config on creation."""
        for q in self.config.questions:
            self.question_states[q.id] = QuestionState(
                question_id=q.id,
                goal_id=q.goal_id,
            )

    # ── Read helpers (used by all other modules) ──────────────────────────────

    @property
    def current_question(self) -> Optional[InterviewQuestion]:
        questions = self.config.questions
        if self.current_question_index < len(questions):
            return questions[self.current_question_index]
        return None

    @property
    def is_complete(self) -> bool:
        mandatory = [q for q in self.config.questions if q.is_mandatory]
        return all(
            self.question_states[q.id].status in
            (GoalStatus.COVERED, GoalStatus.WEAK, GoalStatus.SKIPPED)
            for q in mandatory
        )

    @property
    def covered_goals(self) -> List[str]:
        return [
            qs.goal_id for qs in self.question_states.values()
            if qs.status == GoalStatus.COVERED
        ]

    @property
    def elapsed_seconds(self) -> float:
        if not self.started_at:
            return 0.0
        end = self.ended_at or datetime.utcnow()
        return (end - self.started_at).total_seconds()

    @property
    def is_over_time(self) -> bool:
        return self.elapsed_seconds > self.config.time_limit_seconds

    def get_goal_coverage(self) -> Dict[str, GoalStatus]:
        """Returns goal_id → status for all goals."""
        return {
            goal.id: self.question_states.get(
                next((q.id for q in self.config.questions
                      if q.goal_id == goal.id), ""),
                QuestionState(question_id="", goal_id=goal.id)
            ).status
            for goal in self.config.goals
        }

    # ── Write helpers (only QuestionFlowProcessor should call these) ──────────

    def start(self):
        self.status = InterviewStatus.ACTIVE
        self.started_at = datetime.utcnow()

    def mark_question_asked(self, question_id: str):
        if question_id in self.question_states:
            self.question_states[question_id].status = GoalStatus.IN_PROGRESS
            self.question_states[question_id].asked_at = datetime.utcnow()

    def mark_question_answered(self, question_id: str, status: GoalStatus):
        if question_id in self.question_states:
            self.question_states[question_id].status = status
            self.question_states[question_id].answered_at = datetime.utcnow()

    def increment_follow_up(self, question_id: str):
        if question_id in self.question_states:
            self.question_states[question_id].follow_up_count += 1

    def advance_question(self):
        self.current_question_index += 1

    def add_turn(self, speaker: str, text: str,
                 question_id: Optional[str] = None,
                 is_follow_up: bool = False):
        self.transcript.append(TranscriptTurn(
            speaker=speaker,
            text=text,
            timestamp=datetime.utcnow(),
            question_id=question_id,
            is_follow_up=is_follow_up,
        ))

    def log_connection_event(self, event_type: str, detail: str = ""):
        self.connection_events.append(ConnectionEvent(
            event_type=event_type,
            timestamp=datetime.utcnow(),
            detail=detail,
        ))

    def end(self, status: InterviewStatus = InterviewStatus.COMPLETED):
        self.status = status
        self.ended_at = datetime.utcnow()

    # ── Dashboard write helpers ──────────────────────────────────────────────

    def add_evaluation(self, evaluation: Dict):
        self.evaluations.append({
            **evaluation,
            "timestamp": datetime.utcnow().isoformat()
        })

    def add_metrics(self, turn_metrics: Dict):
        self.metrics.append({
            **turn_metrics,
            "timestamp": datetime.utcnow().isoformat()
        })

    def update_settings(self, timeout: int, auto_kill: bool):
        self.session_timeout_seconds = timeout
        self.auto_kill_on_disconnect = auto_kill
