"""
Goal Tracking Processor - Real-time goal analysis integrated with Pipecat pipeline
"""

import asyncio
import json
from typing import Dict, Any
from loguru import logger

from pipecat.frames.frames import Frame, TranscriptionFrame
from pipecat.processors.frame_processor import FrameProcessor

from database import db_manager
from services.goal_tracking_service import GoalTrackingService
from interview_session import InterviewSession


class GoalTrackingProcessor(FrameProcessor):
    """
    Processes transcription frames to track goal progress in real-time
    Integrates with existing dual LLM pipeline
    """

    def __init__(self, interview_session: InterviewSession, goal_service: GoalTrackingService,
                 broadcaster, groq_api_key: str):
        super().__init__()
        self.session = interview_session
        self.goal_service = goal_service
        self.broadcaster = broadcaster
        self.groq_api_key = groq_api_key

        # State tracking
        self.goals_initialized = False
        self._initializing = False  # synchronous guard against duplicate init tasks
        self.analyzing = False
        self.last_analysis_timestamp = 0

        # Analysis throttling (prevent too frequent analysis)
        self.min_analysis_interval = 5.0  # seconds
        self.min_response_length = 20     # characters

    async def initialize_goals(self):
        """Initialize goal tracking for the session"""
        if self.goals_initialized or self.session is None:
            return

        try:
            self._initializing = True
            goal_ids = await self.goal_service.initialize_session_goals(self.session)
            self.goals_initialized = True

            # Broadcast goal initialization to dashboard
            await self.broadcaster.broadcast("goals_initialized", {
                "session_id": self.session.session_id,
                "goal_count": len(goal_ids),
                "goals": await self.goal_service.get_goal_progress_summary(self.session.session_id)
            })

            logger.info(f"[GoalTracking] Initialized {len(goal_ids)} goals for session: {self.session.session_id}")

        except Exception as e:
            logger.error(f"[GoalTracking] Failed to initialize goals: {e}")

    def set_session(self, session):
        self.session = session

    async def process_frame(self, frame: Frame, direction):
        await super().process_frame(frame, direction)

        # Analyze candidate speech for goal progress
        if isinstance(frame, TranscriptionFrame):
            await self._handle_transcription(frame)

        # Always pass frame through
        await self.push_frame(frame, direction)

    async def _handle_transcription(self, frame: TranscriptionFrame):
        """Handle transcription frame and analyze for goal progress"""
        try:
            # Analyze applicant speech. Manual-input (typed via /chat) is treated as
            # applicant speech too, so conversations can be replayed to test goal tracking.
            if len(frame.text.strip()) < self.min_response_length:
                return

            # Throttle analysis to prevent overload
            import time
            current_time = time.time()
            if current_time - self.last_analysis_timestamp < self.min_analysis_interval:
                return

            if self.analyzing:
                return  # Skip if already analyzing

            # Start background analysis
            asyncio.create_task(self._analyze_response_for_goals(frame.text, current_time))

        except Exception as e:
            logger.error(f"[GoalTracking] Error handling transcription: {e}")

    async def _analyze_response_for_goals(self, response_text: str, timestamp: float):
        """Analyze candidate response for goal progress"""
        if not self.goals_initialized:
            return

        self.analyzing = True
        self.last_analysis_timestamp = timestamp

        try:
            # Build context for analysis
            context = {
                "current_question": getattr(self.session.current_question, 'text', None) if hasattr(self.session, 'current_question') else None,
                "interview_phase": "active",
                "time_elapsed": f"{timestamp - self.session.start_time:.0f}s" if hasattr(self.session, 'start_time') else "N/A"
            }

            # Analyze with goal service
            analysis = await self.goal_service.analyze_candidate_response(
                self.session.session_id,
                response_text,
                context
            )

            # Broadcast results to dashboard
            if analysis.get("goal_updates"):
                await self._broadcast_goal_updates(analysis)

            # Log significant progress
            for update in analysis.get("goal_updates", []):
                if update.get("progress_delta", 0) > 0.1:  # Significant progress
                    logger.info(f"[GoalTracking] Progress on '{update['goal_title']}': +{update['progress_delta']:.1%}")

        except Exception as e:
            logger.error(f"[GoalTracking] Analysis failed: {e}")
        finally:
            self.analyzing = False

    async def _broadcast_goal_updates(self, analysis: Dict[str, Any]):
        """Broadcast goal updates to dashboard"""
        try:
            # Get updated goal summary
            progress_summary = await self.goal_service.get_goal_progress_summary(self.session.session_id)

            # Broadcast detailed progress update
            await self.broadcaster.broadcast("goal_progress_update", {
                "session_id": self.session.session_id,
                "timestamp": asyncio.get_event_loop().time(),
                "updates": analysis.get("goal_updates", []),
                "response_quality": analysis.get("response_quality", "moderate"),
                "follow_up_needed": analysis.get("follow_up_needed", False),
                "suggested_probe": analysis.get("suggested_probe"),
                "summary": progress_summary
            })

            # Broadcast individual goal updates
            for update in analysis.get("goal_updates", []):
                await self.broadcaster.broadcast("goal_updated", {
                    "session_id": self.session.session_id,
                    "goal_title": update["goal_title"],
                    "progress_delta": update.get("progress_delta", 0),
                    "evidence_type": update.get("evidence_type"),
                    "evidence_text": update.get("evidence_text"),
                    "confidence": update.get("confidence", 0.5)
                })

        except Exception as e:
            logger.error(f"[GoalTracking] Failed to broadcast updates: {e}")

    async def get_adaptive_question_suggestion(self) -> str:
        """Get next question suggestion based on goal progress"""
        if not self.goals_initialized:
            return None

        try:
            # Get current goal progress
            progress_summary = await self.goal_service.get_goal_progress_summary(self.session.session_id)

            # Find underperforming goals
            underperforming = [
                goal for goal in progress_summary.get("goals", [])
                if goal["progress"] < 0.6 and goal["status"] in ["not_started", "in_progress"]
            ]

            if not underperforming:
                return None

            # Select highest priority underperforming goal
            priority_goal = max(underperforming, key=lambda g: g.get("priority_weight", 0.5))

            # Generate adaptive question
            from processors.adaptive_questioning_processor import AdaptiveQuestioningProcessor
            questioning_processor = AdaptiveQuestioningProcessor(self.goal_service, self.groq_api_key)

            suggestion = await questioning_processor.generate_follow_up_question(
                self.session.session_id,
                priority_goal["title"]
            )

            return suggestion

        except Exception as e:
            logger.error(f"[GoalTracking] Failed to get question suggestion: {e}")
            return None

    async def finalize_session_goals(self, graceful: bool = True):
        """Perform final goal analysis when session ends.

        ``graceful`` is True when the interview reached its natural end (all questions
        covered); False when it was interrupted (so the session stays resumable)."""
        if not self.goals_initialized:
            return

        try:
            logger.info(f"[GoalTracking] Finalizing goals for session: {self.session.session_id}")

            # Perform comprehensive analysis
            final_analysis = await self.goal_service.comprehensive_goal_analysis(self.session.session_id)

            # Embed phase scores into the assessment so the backend can surface them.
            if isinstance(final_analysis, dict):
                boundary = getattr(getattr(self.session, "config", None), "phase1_boundary", 0)
                if boundary > 0:
                    final_analysis["phase1_score"] = getattr(self.session, "phase1_score", None)
                    final_analysis["phase1_boundary"] = boundary
                    final_analysis["current_phase"] = getattr(self.session, "current_phase", "initial")

            # Non-technical screening interview: also extract the structured qualifying
            # summary (experience, salary, stack, achievements, …) from the transcript
            # and attach it so HR reads it alongside (or instead of) the goal scores.
            interview_type = getattr(getattr(self.session, "config", None), "interview_type", "") or ""
            if "screening" in interview_type.lower():
                try:
                    from services.screening_extraction import extract_screening_summary
                    screening_summary = await extract_screening_summary(self.session.session_id)
                    if not isinstance(final_analysis, dict) or "error" in final_analysis:
                        # Goal analysis was thin/failed — still persist the screening summary.
                        final_analysis = {"interview_type": interview_type}
                    final_analysis["screening_summary"] = screening_summary
                except Exception as e:
                    logger.error(f"[GoalTracking] screening extraction failed: {e}")

            # Persist the final assessment so HR can read it later. Skip on analysis
            # error so we never overwrite the record with an error blob.
            if isinstance(final_analysis, dict) and "error" not in final_analysis:
                try:
                    await db_manager.finalize_session_record(
                        self.session.session_id, json.dumps(final_analysis), completed=graceful
                    )
                except Exception as e:
                    logger.error(f"[GoalTracking] Failed to persist final assessment: {e}")

            # Broadcast final results
            await self.broadcaster.broadcast("session_goals_finalized", {
                "session_id": self.session.session_id,
                "final_analysis": final_analysis,
                "completion_time": asyncio.get_event_loop().time()
            })

            # Log completion summary
            overall = final_analysis.get("overall_assessment", {})
            logger.info(f"[GoalTracking] Session complete - Coverage: {overall.get('goal_coverage_rate', 0):.1%}, "
                       f"Performance: {overall.get('candidate_performance', 0):.1%}")

        except Exception as e:
            logger.error(f"[GoalTracking] Failed to finalize session goals: {e}")


class GoalAwareTranscriptProcessor(FrameProcessor):
    """
    Enhanced transcript processor that includes goal context
    Extends existing WorkingTranscriptProcessor functionality
    """

    def __init__(self, session: InterviewSession, broadcaster, goal_service: GoalTrackingService):
        super().__init__()
        self.session = session
        self.broadcaster = broadcaster
        self.goal_service = goal_service

    def set_session(self, session):
        self.session = session

    async def process_frame(self, frame: Frame, direction):
        await super().process_frame(frame, direction)

        if isinstance(frame, TranscriptionFrame):
            await self._process_transcript_with_goals(frame)

        await self.push_frame(frame, direction)

    async def _process_transcript_with_goals(self, frame: TranscriptionFrame):
        """Process transcript entry and update database with goal context"""
        try:
            # A TranscriptionFrame is always applicant speech (STT mic output or
            # text injected via /chat). The bot's own words are emitted as TTS
            # TextFrames and labelled "agent" by WorkingMetricsProcessor.
            transcript_data = {
                "speaker": "candidate",
                "text": frame.text,
                "timestamp": frame.timestamp,
                "tokens_estimated": len(frame.text.split())  # Simple word count
            }

            from database import db_manager
            transcript_id = await db_manager.add_transcript_entry(self.session.session_id, transcript_data)

            # Enhanced broadcast with goal context
            progress_summary = await self.goal_service.get_goal_progress_summary(self.session.session_id)

            await self.broadcaster.broadcast("transcript", {
                "session_id": self.session.session_id,
                "transcript_id": transcript_id,
                "speaker": transcript_data["speaker"],
                "text": frame.text,
                "timestamp": frame.timestamp,
                "goal_context": {
                    "completion_rate": progress_summary.get("completion_rate", 0),
                    "active_goals": len([g for g in progress_summary.get("goals", []) if g["status"] == "in_progress"])
                }
            })

        except Exception as e:
            logger.error(f"[GoalAwareTranscript] Failed to process transcript: {e}")
            # Fallback to basic broadcast
            await self.broadcaster.broadcast("transcript", {
                "speaker": "candidate",
                "text": frame.text,
                "timestamp": frame.timestamp
            })