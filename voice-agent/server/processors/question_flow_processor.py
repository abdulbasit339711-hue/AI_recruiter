import asyncio
import os

from loguru import logger
from pipecat.frames.frames import (
    Frame,
    TranscriptionFrame,
    LLMRunFrame,
    BotConnectedFrame,
    EndTaskFrame,
)
from pipecat.processors.frame_processor import FrameProcessor, FrameDirection
from pipecat.processors.aggregators.llm_context import LLMContext
from interview_session import (
    InterviewSession,
    InterviewStatus,
    GoalStatus,
    AnswerDepth,
)
from events.broadcaster import broadcaster

# ── Answer quality thresholds ──────────────────────────────────────────────────
# Voice answers are naturally shorter than written ones — 40 words spoken aloud
# is a solid paragraph. Keep thresholds realistic for live speech.

DEPTH_MIN_WORDS = {
    AnswerDepth.SHORT:  3,
    AnswerDepth.MEDIUM: 10,
    AnswerDepth.LONG:   20,
}

FILLER_WORDS = {
    "um", "uh", "like", "you know", "sort of",
    "kind of", "basically", "literally", "actually"
}

# One-word or near-empty "no/don't know" dismissals
_EVASIVE_PATTERNS = {
    "no", "nope", "nah", "dont know", "don't know", "idk",
    "i don't know", "i dont know", "not sure", "no idea",
    "kiyun btaon", "kyon btaon", "kyun btaon", "nahi pata",
    "nahi", "nhi", "pata nahi", "nai pata",
}


def _word_count(text: str) -> int:
    return len(text.split())


def _is_evasive(text: str) -> bool:
    """True when the candidate dismisses the question with a short negative."""
    cleaned = text.lower().strip().rstrip("?!.,")
    return cleaned in _EVASIVE_PATTERNS or len(text.split()) <= 2


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
    # Evasive one-liners always fail regardless of depth
    if _is_evasive(text):
        logger.debug(f"[flow] evasive/dismissive answer detected: {text!r}")
        return False

    wc = _word_count(text)
    min_words = DEPTH_MIN_WORDS[question.expected_depth]

    if wc < min_words:
        logger.debug(f"[flow] answer too short: {wc} words, need {min_words}")
        return False

    fr = _filler_ratio(text)
    if fr > 0.40:
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

        if isinstance(frame, BotConnectedFrame):
            logger.info("[flow] Bot connected to room — triggering opening")
            await self.trigger_opening()

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

    async def trigger_opening(self):
        """Manually trigger the opening question."""
        if not self._opening_done:
            logger.info("[flow] triggering opening via manual call")
            self._opening_done = True
            await self._ask_question(self._session.current_question, is_opening=True)

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
            await self._persist_progress()

            # Phase boundary check: if we just finished Phase 1, handle transition.
            boundary = session.config.phase1_boundary
            if boundary > 0 and session.current_question_index == boundary and session.current_phase == "initial":
                await self._handle_phase_transition()
                return

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

                # Tailor the instruction based on WHY the answer was insufficient
                if _is_evasive(text):
                    inject_msg = (
                        f"The candidate gave a dismissive or very brief response ('{text}'). "
                        f"Do NOT simply accept this and move on. Instead, gently re-engage: "
                        f"acknowledge that the question might feel broad, then rephrase it or "
                        f"ask what experience they DO have in this area. "
                        f"If they answered 'no' to a specific technology, ask which alternative "
                        f"tools or approaches they use for the same purpose. "
                        f"Suggested follow-up: {follow_up.text}"
                    )
                else:
                    inject_msg = (
                        f"The candidate's answer was insufficient. "
                        f"Reason: {follow_up.trigger_reason}. "
                        f"Ask this follow-up naturally: {follow_up.text}"
                    )
                await self._inject_instruction(inject_msg)
            else:
                # Follow-up budget exhausted — mark weak and move on
                logger.info(
                    f"[flow] follow-up budget exhausted for {current_q.id}, "
                    f"marking weak"
                )
                session.mark_question_answered(current_q.id, GoalStatus.WEAK)
                session.advance_question()
                await self._persist_progress()

                # Phase boundary check
                boundary = session.config.phase1_boundary
                if boundary > 0 and session.current_question_index == boundary and session.current_phase == "initial":
                    await self._handle_phase_transition()
                    return

                next_q = session.current_question
                if next_q:
                    await self._ask_question(next_q)
                else:
                    await self._close_interview()

    def _compute_phase_score(self, start: int, end: int) -> float:
        """Weighted score 0-100 for questions in index range [start, end)."""
        session = self._session
        weighted = 0.0
        total_w = 0.0
        for i in range(start, min(end, len(session.config.questions))):
            q = session.config.questions[i]
            goal = session.config.get_goal(q.goal_id)
            w = goal.weight if goal else 1.0
            qs = session.question_states.get(q.id)
            status = qs.status if qs else GoalStatus.SKIPPED
            if status == GoalStatus.COVERED:
                s = 1.0
            elif status == GoalStatus.WEAK:
                s = 0.5
            else:
                s = 0.0
            weighted += w * s
            total_w += w
        return round((weighted / total_w) * 100.0, 1) if total_w > 0 else 0.0

    async def _handle_phase_transition(self):
        """Called when Phase 1 is complete. Scores Phase 1 and decides whether to proceed."""
        session = self._session
        boundary = session.config.phase1_boundary
        score = self._compute_phase_score(0, boundary)
        session.phase1_score = score
        threshold = session.config.phase1_threshold

        logger.info(
            f"[flow] Phase 1 complete. Score={score:.1f}, threshold={threshold}. "
            f"Proceeding={'yes' if score >= threshold else 'no'}"
        )

        await broadcaster.broadcast("phase_transition", {
            "phase": "evaluating",
            "phase1_score": score,
            "threshold": threshold,
            "advancing": score >= threshold,
        })

        if score >= threshold:
            session.current_phase = "technical"
            # Gradual transition announcement
            transition_msg = (
                f"The candidate has completed the initial portion of the interview. "
                f"Acknowledge their responses warmly and naturally. Then smoothly transition "
                f"by saying something like: 'You've shared some great insights — let's now "
                f"move into the technical part of the interview. I have a few more questions "
                f"about your technical skills and problem-solving approach.' Then ask the "
                f"next question: {session.current_question.text}"
                if session.current_question else
                "The initial portion is complete. Thank the candidate warmly and close the interview."
            )
            await self._inject_instruction(transition_msg)
            if session.current_question:
                session.mark_question_asked(session.current_question.id)
        else:
            session.current_phase = "complete"
            instruction = (
                "The initial screening portion of the interview is now complete. "
                "Thank the candidate sincerely for their time and answers. "
                "Let them know the recruitment team will carefully review their responses "
                "and will be in touch regarding next steps. Close the conversation "
                "warmly and professionally."
            )
            await self._inject_instruction(instruction)
            session.end()
            await broadcaster.broadcast("status", {"status": "completed", "phase": "initial_only"})
            logger.info(f"[flow] Interview ended after Phase 1 (score {score:.1f} < threshold {threshold}).")
            grace = float(os.getenv("INTERVIEW_CLOSE_GRACE_SECS", "14"))
            async def _end_after_phase1():
                await asyncio.sleep(grace)
                await self.push_frame(EndTaskFrame(), FrameDirection.UPSTREAM)
            asyncio.create_task(_end_after_phase1())

    async def _ask_question(
        self,
        question,
        is_opening: bool = False
    ):
        """Inject an instruction into LLM context to ask this question."""
        await broadcaster.broadcast("state", {"status": "speaking", "speaker": "agent"})
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

        await self._persist_progress()
        await self._inject_instruction(instruction)
        logger.info(f"[flow] asking question: {question.id}")

    async def _persist_progress(self):
        """Save the current question-flow position so an interrupted interview resumes
        in place. Best-effort: DB hiccups must never break the live interview."""
        session = self._session
        try:
            from database import db_manager
            await db_manager.save_session_progress(
                session.session_id,
                session.current_question_index,
                session.progress_snapshot(),
            )
        except Exception as e:
            logger.debug(f"[flow] progress persist skipped: {e}")

    async def _close_interview(self):
        """Inject a closing instruction when all questions are done."""
        session = self._session
        covered = len(session.covered_goals)
        total = len(session.config.goals)

        # If we completed Phase 2, compute the Phase 2 score.
        boundary = session.config.phase1_boundary
        if boundary > 0 and session.current_phase == "technical":
            n_total = len(session.config.questions)
            phase2_score = self._compute_phase_score(boundary, n_total)
            session.current_phase = "complete"
            await broadcaster.broadcast("phase_transition", {
                "phase": "complete",
                "phase2_score": phase2_score,
            })
            logger.info(f"[flow] Phase 2 complete. Score={phase2_score:.1f}")

        instruction = (
            f"The interview is now complete. All {total} topics have been covered. "
            f"Thank the candidate warmly, let them know the team will be in touch, "
            f"and close the conversation naturally."
        )
        await self._inject_instruction(instruction)
        session.end()
        await broadcaster.broadcast("status", {"status": "completed"})
        logger.info(f"[flow] interview complete. goals covered: {covered}/{total}")

        # End the pipeline shortly after the closing line is spoken so the worker
        # terminates and runner._make_and_run_bot's finally block finalizes the session
        # (saves the recording + runs the post-call evaluation) immediately — instead of
        # waiting out the idle timeout. Delay lets the goodbye TTS actually play.
        grace = float(os.getenv("INTERVIEW_CLOSE_GRACE_SECS", "14"))

        async def _end_after_closing():
            await asyncio.sleep(grace)
            logger.info("[flow] ending pipeline to finalize the completed interview")
            await self.push_frame(EndTaskFrame(), FrameDirection.UPSTREAM)

        asyncio.create_task(_end_after_closing())

    async def _inject_instruction(self, instruction: str):
        """
        Add a system-role instruction to LLM context and trigger a response.
        """
        await broadcaster.broadcast("state", {"status": "thinking", "speaker": "agent"})
        
        json_instruction = (
            f"{instruction} \n\n"
            f"CRITICAL: You must return a valid JSON object. Do not include any text before or after the JSON. "
            f"Template: {{\"response\": \"Natural text to speak\", \"evaluation\": {{\"score\": 5, \"critique\": \"your feedback\", \"goal_progress\": 0}}}}"
        )

        # Using 'system' role for strict JSON guidance
        self._context.add_message({
            "role": "system",
            "content": json_instruction,
        })
        await self.push_frame(LLMRunFrame())
