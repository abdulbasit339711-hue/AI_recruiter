# question_flow_processor.py

from loguru import logger
from pipecat.frames.frames import (
    Frame,
    TranscriptionFrame,
    LLMRunFrame,
)
from pipecat.processors.frame_processor import FrameProcessor
from pipecat.processors.aggregators.llm_context import LLMContext
from interview_session import (
    InterviewSession,
    InterviewStatus,
    GoalStatus,
    AnswerDepth,
)
from events.broadcaster import broadcaster

# ── Answer quality thresholds ──────────────────────────────────────────────────

DEPTH_MIN_WORDS = {
    AnswerDepth.SHORT:  3,
    AnswerDepth.MEDIUM: 15,
    AnswerDepth.LONG:   40,
}

FILLER_WORDS = {
    "um", "uh", "like", "you know", "sort of",
    "kind of", "basically", "literally", "actually"
}


def _word_count(text: str) -> int:
    return len(text.split())


def _filler_ratio(text: str) -> float:
    words = text.lower().split()
    if not words:
        return 0.0
    filler_hits = sum(1 for w in words if w in FILLER_WORDS)
    return filler_hits / len(words)


def _has_theme_signal(text: str, expected_theme: str) -> bool:
    """
    Very lightweight check — does the answer contain any word
    from the expected theme description?
    """
    theme_words = set(expected_theme.lower().split())
    answer_words = set(text.lower().split())
    return bool(theme_words & answer_words)


def _answer_is_sufficient(text: str, question) -> bool:
    """
    Returns True if the answer passes basic quality gates.
    """
    wc = _word_count(text)
    min_words = DEPTH_MIN_WORDS[question.expected_depth]

    if wc < min_words:
        logger.debug(f"[flow] answer too short: {wc} words, need {min_words}")
        return False

    fr = _filler_ratio(text)
    if fr > 0.35:
        logger.debug(f"[flow] filler ratio too high: {fr:.0%}")
        return False

    if not _has_theme_signal(text, question.expected_theme):
        logger.debug(f"[flow] no theme signal found for: {question.expected_theme}")
        return False

    return True


# ── Processor ─────────────────────────────────────────────────────────────────

class QuestionFlowProcessor(FrameProcessor):
    """
    Controls the interview question flow.
    """

    def __init__(self, session: InterviewSession, context: LLMContext):
        super().__init__()
        self._session = session
        self._context = context
        self._opening_done = False

    async def process_frame(self, frame: Frame, direction):
        await super().process_frame(frame, direction)
        if isinstance(frame, TranscriptionFrame):
            text = frame.text.strip()
            if text:
                await broadcaster.broadcast("state", {
                    "status": "speaking",
                    "speaker": "candidate",
                    "text": text
                })
                await self._handle_candidate_turn(text)

        await self.push_frame(frame, direction)

    async def _handle_candidate_turn(self, text: str):
        session = self._session

        # Guard: don't process if interview isn't active
        if session.status != InterviewStatus.ACTIVE:
            return

        # ── Opening: first time candidate speaks ──────────────────────────────
        if not self._opening_done:
            self._opening_done = True
            await self._ask_question(session.current_question, is_opening=True)
            return

        # ── Ongoing: evaluate the answer to current question ──────────────────
        current_q = session.current_question
        if current_q is None:
            # All questions exhausted
            await self._close_interview()
            return

        q_state = session.question_states.get(current_q.id)
        if q_state is None or q_state.status not in (
            GoalStatus.IN_PROGRESS, GoalStatus.PENDING
        ):
            # Question not yet asked — ask it now
            await self._ask_question(current_q)
            return

        # Question is IN_PROGRESS — evaluate the answer
        sufficient = _answer_is_sufficient(text, current_q)
        max_follow_ups = session.config.max_follow_ups_per_question

        if sufficient:
            logger.info(f"[flow] answer sufficient for {current_q.id}")
            session.mark_question_answered(current_q.id, GoalStatus.COVERED)
            session.advance_question()
            next_q = session.current_question

            if next_q:
                await self._ask_question(next_q)
            else:
                await self._close_interview()

        else:
            # Answer insufficient — follow up if we have budget
            follow_up_count = q_state.follow_up_count
            follow_ups = current_q.follow_ups

            if follow_up_count < max_follow_ups and follow_up_count < len(follow_ups):
                follow_up = follow_ups[follow_up_count]
                logger.info(
                    f"[flow] triggering follow-up {follow_up_count + 1} "
                    f"for {current_q.id}: {follow_up.trigger_reason}"
                )
                session.increment_follow_up(current_q.id)
                await self._inject_instruction(
                    f"The candidate's answer was insufficient. "
                    f"Reason: {follow_up.trigger_reason}. "
                    f"Ask this follow-up naturally: {follow_up.text}"
                )
            else:
                # Follow-up budget exhausted — mark weak and move on
                logger.info(
                    f"[flow] follow-up budget exhausted for {current_q.id}, "
                    f"marking weak"
                )
                session.mark_question_answered(current_q.id, GoalStatus.WEAK)
                session.advance_question()
                next_q = session.current_question

                if next_q:
                    await self._ask_question(next_q)
                else:
                    await self._close_interview()

    async def _ask_question(
        self,
        question,
        is_opening: bool = False
    ):
        """Inject an instruction into LLM context to ask this question."""
        session = self._session
        session.mark_question_asked(question.id)

        if is_opening:
            instruction = (
                f"You are conducting an interview for the role of "
                f"{session.config.job_role} at {session.config.company_name}. "
                f"Briefly introduce yourself as the AI interviewer, then "
                f"naturally transition into asking this first question: "
                f"{question.text}"
            )
        else:
            instruction = (
                f"The candidate has answered the previous question. "
                f"Acknowledge their answer briefly and naturally, "
                f"then ask the next question: {question.text}"
            )

        await self._inject_instruction(instruction)
        logger.info(f"[flow] asking question: {question.id}")

    async def _close_interview(self):
        """Inject a closing instruction when all questions are done."""
        session = self._session
        covered = len(session.covered_goals)
        total = len(session.config.goals)

        instruction = (
            f"The interview is now complete. All {total} topics have been covered. "
            f"Thank the candidate warmly, let them know the team will be in touch, "
            f"and close the conversation naturally."
        )
        await self._inject_instruction(instruction)
        session.end()
        await broadcaster.broadcast("status", {"status": "completed"})
        logger.info(f"[flow] interview complete. goals covered: {covered}/{total}")

    async def _inject_instruction(self, instruction: str):
        """
        Add a developer-role instruction to LLM context and trigger a response.
        """
        await broadcaster.broadcast("state", {"status": "thinking", "speaker": "agent"})
        
        json_instruction = (
            f"{instruction} "
            f"CRITICAL: Return your response ONLY as a JSON object with two keys: "
            f"'response' (the text you will speak) and 'evaluation' (an object containing "
            f"'score' 1-10, 'critique' of the candidate's performance, and 'goal_progress')."
        )

        self._context.add_message({
            "role": "developer",
            "content": json_instruction,
        })
        await self.push_frame(LLMRunFrame())
