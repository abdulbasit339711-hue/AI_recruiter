"""
Judge LLM Processor - Evaluates candidate responses in real-time
"""

from loguru import logger
from pipecat.frames.frames import Frame, TranscriptionFrame
from pipecat.processors.frame_processor import FrameProcessor
from groq import AsyncGroq
import asyncio

from services.goal_tracking_service import _safe_json_loads

JUDGE_MODEL = "llama-3.1-8b-instant"


class JudgeProcessor(FrameProcessor):
    """
    Evaluates candidate responses using a fast judge model (llama-3.1-8b-instant)
    Runs in parallel with the main pipeline to provide real-time evaluation
    """

    def __init__(self, session, broadcaster, api_key):
        super().__init__()
        self._session = session
        self._broadcaster = broadcaster
        self._current_transcript = []
        self._evaluating = False
        self._api_key = api_key
        self._client = AsyncGroq(api_key=api_key)

    def _get_judge_prompt(self):
        """Get the system prompt for the judge model"""
        return """You are an expert interview evaluator. Analyze the candidate's response and provide a brief JSON evaluation.

Focus on:
1. Completeness - Does the answer fully address the question?
2. Depth - Is it surface-level or detailed?
3. Relevance - Is it on-topic?
4. Technical accuracy - Are technical details correct?
5. Communication clarity - Is it well-structured?

Respond ONLY with JSON in this format:
{
    "score": 7,
    "completeness": 0.8,
    "depth": "detailed",
    "relevance": 0.9,
    "clarity": 0.85,
    "strengths": ["specific examples", "clear structure"],
    "weaknesses": ["missing metrics"],
    "follow_up_needed": true,
    "suggested_probe": "Can you share specific metrics?"
}"""

    def set_session(self, session):
        self._session = session

    async def process_frame(self, frame: Frame, direction):
        await super().process_frame(frame, direction)

        # Capture user transcriptions for evaluation
        if isinstance(frame, TranscriptionFrame):
            text = frame.text.strip()
            if text and len(text) > 20:  # Only evaluate substantial responses
                # Start evaluation in background
                asyncio.create_task(self._evaluate_response(text))

        # Always pass frame through
        await self.push_frame(frame, direction)

    async def _evaluate_response(self, text: str):
        """Evaluate the candidate's response asynchronously"""
        if self._evaluating:
            return  # Skip if already evaluating

        self._evaluating = True
        try:
            # Skip if no session is configured yet (race before set_session).
            if self._session is None:
                self._evaluating = False
                return
            # Get current question context
            current_q = self._session.current_question
            if not current_q:
                self._evaluating = False
                return

            # Create evaluation prompt
            eval_prompt = f"""Question asked: {current_q.text}
Candidate response: {text}

Evaluate this response."""

            # Get a real evaluation from the judge model
            logger.info(f"[Judge] Evaluating response: {text[:100]}...")

            completion = await self._client.chat.completions.create(
                model=JUDGE_MODEL,
                messages=[
                    {"role": "system", "content": self._get_judge_prompt()},
                    {"role": "user", "content": eval_prompt},
                ],
                temperature=0.2,
                max_tokens=400,
                response_format={"type": "json_object"},
            )

            response_text = completion.choices[0].message.content

            if response_text:
                evaluation = _safe_json_loads(response_text)
                if not evaluation:
                    logger.warning("[Judge] Empty/unparseable evaluation, skipping")
                else:
                    # Store evaluation in session
                    self._session.evaluations.append({
                        "question_id": current_q.id,
                        "evaluation": evaluation,
                        "response_text": text
                    })

                    # Broadcast evaluation to dashboard
                    await self._broadcaster.broadcast("judge_evaluation", {
                        "question_id": current_q.id,
                        "score": evaluation.get("score", 0),
                        "completeness": evaluation.get("completeness", 0),
                        "depth": evaluation.get("depth", "unknown"),
                        "strengths": evaluation.get("strengths", []),
                        "weaknesses": evaluation.get("weaknesses", []),
                        "follow_up_needed": evaluation.get("follow_up_needed", False),
                        "suggested_probe": evaluation.get("suggested_probe", "")
                    })

                    # Add to context for responder LLM
                    self._session.last_evaluation = evaluation

                    # Persist the per-answer evaluation onto the candidate's transcript row
                    # so HR sees a per-message assessment.
                    try:
                        from database import db_manager
                        await db_manager.attach_transcript_evaluation(
                            self._session.session_id, text, evaluation
                        )
                    except Exception as e:
                        logger.debug(f"[Judge] eval persist skipped: {e}")

                    logger.info(f"[Judge] Score: {evaluation.get('score')}/10, "
                               f"Follow-up needed: {evaluation.get('follow_up_needed')}")

        except Exception as e:
            logger.error(f"[Judge] Evaluation error: {e}")
        finally:
            self._evaluating = False


class DualLLMContextProcessor(FrameProcessor):
    """
    Enriches LLM context with judge evaluation for smarter responses
    """

    def __init__(self, session, context):
        super().__init__()
        self._session = session
        self._context = context

    def set_session(self, session):
        self._session = session

    async def process_frame(self, frame: Frame, direction):
        await super().process_frame(frame, direction)

        # Wire the judge into the responder: when a fresh evaluation says a
        # follow-up is needed, inject its suggested probe into the LLM context so
        # the responder naturally asks it on its next turn. Injected once per
        # evaluation (tracked by identity) and best-effort so it can never break
        # the response path.
        try:
            ev = getattr(self._session, "last_evaluation", None) if self._session else None
            if (
                ev
                and ev is not getattr(self, "_consumed_eval", None)
                and ev.get("follow_up_needed")
                and ev.get("suggested_probe")
            ):
                self._consumed_eval = ev
                guidance = (
                    "[Interview coach] The candidate's previous answer scored "
                    f"{ev.get('score')}/10 (depth: {ev.get('depth')}). A follow-up is "
                    f"warranted — naturally weave in this probe: \"{ev.get('suggested_probe')}\""
                )
                self._context.add_message({"role": "system", "content": guidance})
                logger.debug("[DualLLM] Injected judge follow-up guidance into context")
        except Exception as e:
            logger.debug(f"[DualLLM] guidance injection skipped: {e}")

        await self.push_frame(frame, direction)