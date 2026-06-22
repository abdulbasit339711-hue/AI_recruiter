"""Regression tests for the per-loop / cross-thread isolation that lets two
interviews run concurrently (each bot on its own event loop in its own thread).

These guard the concrete bugs fixed in P2:
- a single module-global aiohttp.ClientSession bound to one loop broke the 2nd
  concurrent interview's TTS ("Event loop is closed");
- an asyncio.Lock used to serialize finalize across bots gave false mutual
  exclusion (asyncio.Lock only excludes coroutines on its own loop).
"""
import asyncio
import threading

import runner
import bot_manager


def test_aiohttp_session_is_per_loop_and_cleaned_up():
    """Each event loop must get its OWN aiohttp session, and closing drops it."""
    results = {}

    def run_on_new_loop(key):
        loop = asyncio.new_event_loop()
        try:
            results[key] = loop.run_until_complete(runner._get_aiohttp_session())
            loop.run_until_complete(runner._close_aiohttp_session())
        finally:
            loop.close()

    t1 = threading.Thread(target=run_on_new_loop, args=("a",))
    t2 = threading.Thread(target=run_on_new_loop, args=("b",))
    t1.start(); t2.start(); t1.join(); t2.join()

    assert results["a"] is not results["b"], "two loops must get distinct sessions"
    assert runner._aiohttp_sessions == {}, "sessions must be closed + dropped per loop"


def test_finalize_lock_is_threadsafe_and_stable():
    """The per-session finalize lock must be a threading.Lock (cross-thread safe)
    and the SAME instance for a given session_id."""
    lock_type = type(threading.Lock())
    lk = bot_manager._finalize_lock_for("session-xyz")
    assert isinstance(lk, lock_type), "finalize lock must be a threading.Lock"
    assert bot_manager._finalize_lock_for("session-xyz") is lk, "same lock per session_id"
    assert bot_manager._finalize_lock_for("other") is not lk, "distinct lock per session_id"
