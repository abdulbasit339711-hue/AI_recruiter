"""
Minimal working processors that don't break the audio pipeline
"""

import asyncio
from loguru import logger
from pipecat.frames.frames import (
    Frame,
    TextFrame,
    TranscriptionFrame,
)
from pipecat.processors.frame_processor import FrameProcessor


class WorkingTranscriptProcessor(FrameProcessor):
    """
    Enhanced processor that captures transcripts and tracks STT metrics
    """

    def __init__(self, session, broadcaster):
        super().__init__()
        self._session = session
        self._broadcaster = broadcaster
        self._stt_metrics = {
            "total_chars_processed": 0,
            "total_requests": 0,
            "estimated_tokens": 0
        }

    def set_session(self, session):
        self._session = session

    async def process_frame(self, frame: Frame, direction):
        await super().process_frame(frame, direction)

        # Only capture user transcription frames
        if isinstance(frame, TranscriptionFrame):
            text = frame.text.strip()
            if text:
                logger.info(f"[Transcript] User: {text[:100]}...")

                # Track STT metrics (for both real STT and manual text injection)
                self._stt_metrics["total_chars_processed"] += len(text)
                self._stt_metrics["total_requests"] += 1
                self._stt_metrics["estimated_tokens"] += len(text.split())  # Estimate ~1 token per word

                # Add to session (skip if no session is configured yet — must not
                # crash the pipeline / block the transcript broadcast below)
                if self._session:
                    self._session.add_turn(
                        speaker="candidate",
                        text=text,
                        question_id=self._session.current_question.id if self._session.current_question else None
                    )

                # Broadcast to dashboard (session_id lets the SSE layer route it
                # only to this interview's candidate page)
                await self._broadcaster.broadcast("transcript", {
                    "session_id": self._session.session_id if self._session else None,
                    "speaker": "candidate",
                    "text": text
                })

                # Broadcast STT metrics
                await self._broadcaster.broadcast("stt_metrics", {
                    "session_id": self._session.session_id if self._session else None,
                    "text_length": len(text),
                    "estimated_tokens": len(text.split()),
                    "session_totals": self._stt_metrics
                })

                logger.info(f"[STT Metrics] Processed {len(text)} chars, ~{len(text.split())} tokens. "
                           f"Session: {self._stt_metrics['total_chars_processed']} chars, "
                           f"~{self._stt_metrics['estimated_tokens']} tokens")

        # Always pass frame through unchanged
        await self.push_frame(frame, direction)


class WorkingMetricsProcessor(FrameProcessor):
    """
    Enhanced processor that captures detailed token metrics from all services
    """

    def __init__(self, session, broadcaster):
        super().__init__()
        self._session = session
        self._broadcaster = broadcaster
        self._current_response = []
        self._collecting = False
        self._aggregating_response = False

        # Detailed token tracking
        self._session_metrics = {
            "stt": {
                "total_chars_processed": 0,
                "total_requests": 0,
                "estimated_tokens": 0
            },
            "llm": {
                "prompt_tokens": 0,
                "completion_tokens": 0,
                "total_tokens": 0,
                "requests": 0
            },
            "tts": {
                "total_chars_synthesized": 0,
                "total_requests": 0,
                "estimated_tokens": 0
            },
            "session_totals": {
                "total_tokens": 0,
                "total_cost_estimate": 0.0
            }
        }

    def set_session(self, session):
        self._session = session

    async def process_frame(self, frame: Frame, direction):
        await super().process_frame(frame, direction)

        # Import frame types we need to check
        from pipecat.frames.frames import (
            LLMFullResponseStartFrame,
            LLMFullResponseEndFrame,
            TTSStartedFrame,
            TTSStoppedFrame,
            TranscriptionFrame,
        )

        # Count candidate speech (STT) — char + estimated token tally for the breakdown.
        if isinstance(frame, TranscriptionFrame):
            stt_text = (frame.text or "").strip()
            if stt_text:
                self._session_metrics["stt"]["total_chars_processed"] += len(stt_text)
                self._session_metrics["stt"]["total_requests"] += 1
                self._session_metrics["stt"]["estimated_tokens"] += len(stt_text.split())

        # Start aggregating response
        if isinstance(frame, LLMFullResponseStartFrame):
            self._aggregating_response = True
            self._current_response = []
            logger.debug("[Agent] Started collecting response")

        # Collect text frames that are going to TTS (agent responses)
        elif isinstance(frame, TextFrame) and self._aggregating_response:
            text = frame.text.strip()
            if text:
                # Collect for aggregation
                self._current_response.append(text)

        # End aggregating and send complete response
        elif isinstance(frame, LLMFullResponseEndFrame):
            self._aggregating_response = False
            await self._handle_llm_metrics(frame)

            # Send the complete aggregated response
            if self._current_response:
                full_text = " ".join(self._current_response)
                logger.info(f"[Agent] Complete response: {full_text[:100]}...")

                # Add to session (skip if not configured — must not block the
                # agent transcript broadcast below)
                if self._session:
                    self._session.add_turn(
                        speaker="agent",
                        text=full_text,
                        question_id=self._session.current_question.id if self._session.current_question else None
                    )

                # Broadcast complete agent transcript
                await self._broadcaster.broadcast("transcript", {
                    "session_id": self._session.session_id if self._session else None,
                    "speaker": "agent",
                    "text": full_text
                })

                # Persist the agent turn so HR sees the full two-sided transcript.
                if self._session is not None:
                    try:
                        import time
                        from database import db_manager
                        await db_manager.add_transcript_entry(self._session.session_id, {
                            "speaker": "agent",
                            "text": full_text,
                            "timestamp": str(time.time()),
                            "tokens_estimated": len(full_text.split()),
                        })
                    except Exception as e:
                        logger.debug(f"[Agent] transcript persist skipped: {e}")

                # Update TTS metrics (characters to be synthesized)
                self._session_metrics["tts"]["total_chars_synthesized"] += len(full_text)
                self._session_metrics["tts"]["estimated_tokens"] += len(full_text) // 4  # Rough estimate

                self._current_response = []

        # Track TTS usage
        elif isinstance(frame, TTSStartedFrame):
            await self._handle_tts_start(frame)

        elif isinstance(frame, TTSStoppedFrame):
            await self._handle_tts_end(frame)

        # Pass frame through unchanged
        await self.push_frame(frame, direction)

    async def _handle_llm_metrics(self, frame):
        """Handle LLM usage metrics from response frames"""

        # The LLMFullResponseEndFrame contains the usage data
        # Try to get actual usage data from frame
        usage = getattr(frame, 'usage', None)

        # If no usage on the frame, try to get the aggregated response text
        if not usage and self._current_response:
            # Estimate based on the full response we collected
            full_text = " ".join(self._current_response)
            word_count = len(full_text.split())

            # Rough estimation: ~1.3 tokens per word
            completion_tokens = int(word_count * 1.3)
            # Estimate prompt tokens based on context size
            prompt_tokens = int(completion_tokens * 0.5)  # Rough estimate
            total_tokens = prompt_tokens + completion_tokens

            logger.info(f"[LLM] Estimated metrics - Prompt: {prompt_tokens}, Completion: {completion_tokens}, Total: {total_tokens}")
        elif usage:
            # Real metrics from LLM
            prompt_tokens = getattr(usage, 'prompt_tokens', 0)
            completion_tokens = getattr(usage, 'completion_tokens', 0)
            total_tokens = getattr(usage, 'total_tokens', prompt_tokens + completion_tokens)

            logger.info(f"[LLM] Real metrics - Prompt: {prompt_tokens}, Completion: {completion_tokens}, Total: {total_tokens}")
        else:
            logger.warning("[LLM] No metrics available and no response text to estimate from")
            return

        # Update session metrics
        self._session_metrics["llm"]["prompt_tokens"] += prompt_tokens
        self._session_metrics["llm"]["completion_tokens"] += completion_tokens
        self._session_metrics["llm"]["total_tokens"] += total_tokens
        self._session_metrics["llm"]["requests"] += 1

        await self._broadcast_detailed_metrics(prompt_tokens, completion_tokens, total_tokens, "llm_response")

    async def persist_summary(self) -> None:
        """Write the per-service token breakdown to session_metrics at interview end.

        One row each for STT (est.), LLM input, LLM output, and TTS (est.). STT/TTS counts
        are character-derived estimates; LLM counts are real usage from the API. Called from
        BotManager.finalize_session().
        """
        if self._session is None:
            return
        from database import db_manager
        llm = self._session_metrics["llm"]
        stt = self._session_metrics["stt"]
        tts = self._session_metrics["tts"]
        input_cost = (llm["prompt_tokens"] / 1_000_000) * 0.20
        output_cost = (llm["completion_tokens"] / 1_000_000) * 1.00
        model = getattr(self._session, "model_name", None) or "llama-3.3-70b-versatile"
        rows = [
            {"metric_type": "stt_tokens", "service_name": "deepgram", "model_name": None,
             "token_count": int(stt["estimated_tokens"]), "cost_usd": 0.0, "analysis_type": "estimated"},
            {"metric_type": "llm_input", "service_name": "groq", "model_name": model,
             "token_count": int(llm["prompt_tokens"]), "cost_usd": round(input_cost, 6), "analysis_type": "actual"},
            {"metric_type": "llm_output", "service_name": "groq", "model_name": model,
             "token_count": int(llm["completion_tokens"]), "cost_usd": round(output_cost, 6), "analysis_type": "actual"},
            {"metric_type": "tts_tokens", "service_name": "cartesia", "model_name": None,
             "token_count": int(tts["estimated_tokens"]), "cost_usd": 0.0, "analysis_type": "estimated"},
        ]
        for r in rows:
            try:
                await db_manager.add_session_metrics(self._session.session_id, r)
            except Exception as e:
                logger.debug(f"[Metrics] persist {r['metric_type']} skipped: {e}")
        logger.info(
            f"[Metrics] Persisted token breakdown: stt={stt['estimated_tokens']}(est) "
            f"llm_in={llm['prompt_tokens']} llm_out={llm['completion_tokens']} "
            f"tts={tts['estimated_tokens']}(est)"
        )


    async def _handle_tts_start(self, frame):
        """Handle TTS start events"""
        self._session_metrics["tts"]["total_requests"] += 1
        logger.debug("[TTS] Started synthesis")

    async def _handle_tts_end(self, frame):
        """Handle TTS end events"""
        logger.debug("[TTS] Completed synthesis")

    async def _broadcast_detailed_metrics(self, prompt_tokens, completion_tokens, total_tokens, event_type):
        """Broadcast detailed metrics to dashboard"""

        # Update session totals
        self._session_metrics["session_totals"]["total_tokens"] += total_tokens

        # Estimate cost (rough Groq pricing: ~$0.20 per 1M input tokens, ~$1.00 per 1M output tokens)
        input_cost = (prompt_tokens / 1_000_000) * 0.20
        output_cost = (completion_tokens / 1_000_000) * 1.00
        total_cost = input_cost + output_cost
        self._session_metrics["session_totals"]["total_cost_estimate"] += total_cost

        # Broadcast detailed metrics
        await self._broadcaster.broadcast("metrics_detailed", {
            "session_id": self._session.session_id if self._session else None,
            "event_type": event_type,
            "timestamp": str(__import__('datetime').datetime.now().isoformat()),
            "current_request": {
                "prompt_tokens": prompt_tokens,
                "completion_tokens": completion_tokens,
                "total_tokens": total_tokens,
                "estimated_cost": total_cost
            },
            "service_breakdown": {
                "stt": {
                    "chars_processed": self._session_metrics["stt"]["total_chars_processed"],
                    "requests": self._session_metrics["stt"]["total_requests"],
                    "estimated_tokens": self._session_metrics["stt"]["estimated_tokens"]
                },
                "llm": {
                    "prompt_tokens": self._session_metrics["llm"]["prompt_tokens"],
                    "completion_tokens": self._session_metrics["llm"]["completion_tokens"],
                    "total_tokens": self._session_metrics["llm"]["total_tokens"],
                    "requests": self._session_metrics["llm"]["requests"]
                },
                "tts": {
                    "chars_synthesized": self._session_metrics["tts"]["total_chars_synthesized"],
                    "requests": self._session_metrics["tts"]["total_requests"],
                    "estimated_tokens": self._session_metrics["tts"]["estimated_tokens"]
                }
            },
            "session_totals": self._session_metrics["session_totals"]
        })

        # Also broadcast simplified metrics for backward compatibility
        await self._broadcaster.broadcast("metrics", {
            "session_id": self._session.session_id if self._session else None,
            "metrics": {
                "prompt_tokens": prompt_tokens,
                "completion_tokens": completion_tokens,
                "total_tokens": total_tokens
            },
            "session_totals": self._session_metrics["session_totals"]
        })

        logger.info(f"[Detailed Metrics] LLM - Input: {prompt_tokens}, Output: {completion_tokens}, Total: {total_tokens}")
        logger.info(f"[Session Totals] LLM: {self._session_metrics['llm']['total_tokens']}, "
                   f"STT: {self._session_metrics['stt']['estimated_tokens']}, "
                   f"TTS: {self._session_metrics['tts']['estimated_tokens']}")