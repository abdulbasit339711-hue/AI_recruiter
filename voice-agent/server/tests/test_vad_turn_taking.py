"""Real-time turn-taking timing test for the VAD config.

Drives the actual Pipecat SpeechTimeoutUserTurnStopStrategy built by
bot_manager.build_user_turn_strategies() through the frame sequence a live
interview produces (final transcript -> VAD reports the pause) and asserts the
bot waits the configured silence window before declaring the candidate's turn
over — instead of Pipecat's aggressive 0.6s default that cuts interviewees off.

This is the one behavior the VAD change alters, and it only manifests in
real-time timing, so we exercise the real strategy rather than a mock.
"""
import asyncio
import time

from pipecat.frames.frames import TranscriptionFrame, VADUserStoppedSpeakingFrame
from pipecat.turns.user_stop.speech_timeout_user_turn_stop_strategy import (
    SpeechTimeoutUserTurnStopStrategy,
)
from pipecat.utils.asyncio.task_manager import TaskManager, TaskManagerParams

import bot_manager


async def _measure(strategy) -> float:
    """Seconds from the VAD pause until the user turn is declared stopped."""
    tm = TaskManager()
    tm.setup(TaskManagerParams(loop=asyncio.get_running_loop()))
    await strategy.setup(tm)

    stopped = asyncio.get_running_loop().create_future()

    @strategy.event_handler("on_user_turn_stopped")
    async def _on_stop(_s, *args):
        if not stopped.done():
            stopped.set_result(time.monotonic())

    await strategy.process_frame(
        TranscriptionFrame(
            text="I guard against overfitting with cross-validation.",
            user_id="candidate",
            timestamp="2026-06-15T16:00:00Z",
            finalized=True,
        )
    )
    t0 = time.monotonic()
    await strategy.process_frame(VADUserStoppedSpeakingFrame())
    elapsed = await asyncio.wait_for(stopped, timeout=10) - t0
    await strategy.cleanup()
    return elapsed


async def test_factory_uses_interview_silence_window():
    """The factory's turn-end delay tracks VAD_USER_SPEECH_TIMEOUT_SECS."""
    strategy = bot_manager.build_user_turn_strategies().stop[0]
    waited = await _measure(strategy)
    assert abs(waited - bot_manager.VAD_USER_SPEECH_TIMEOUT_SECS) < 0.5


async def test_factory_window_is_longer_than_pipecat_default():
    """Configured window gives clearly more think-time than the 0.6s default."""
    default = await _measure(SpeechTimeoutUserTurnStopStrategy())
    ours = await _measure(bot_manager.build_user_turn_strategies().stop[0])
    assert ours > default + 1.0
