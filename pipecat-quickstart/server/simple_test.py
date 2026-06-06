#!/usr/bin/env python3
"""
Simple test to check if components load correctly
"""

import sys
import os

print("=" * 60)
print("TESTING PIPECAT COMPONENTS")
print("=" * 60)

# Test imports
print("\n1. Testing imports...")

errors = []

try:
    from events.broadcaster import broadcaster
    print("✓ broadcaster imported")
except Exception as e:
    errors.append(f"broadcaster: {e}")
    print(f"✗ broadcaster: {e}")

try:
    from simple_processors import (
        SimpleTranscriptAccumulator,
        SimpleLLMResponseHandler,
        SimpleMetricsTracker,
        SimpleQuestionFlow
    )
    print("✓ simple_processors imported")
except Exception as e:
    errors.append(f"simple_processors: {e}")
    print(f"✗ simple_processors: {e}")

try:
    from bot_manager_simple import BotManager
    print("✓ bot_manager_simple imported")
except Exception as e:
    errors.append(f"bot_manager_simple: {e}")
    print(f"✗ bot_manager_simple: {e}")

# Test session creation
print("\n2. Testing session creation...")

try:
    from bot import create_interview_session
    session = create_interview_session()
    print(f"✓ Session created: {session.session_id}")
    print(f"  - Job role: {session.config.job_role}")
    print(f"  - Questions: {len(session.config.questions)}")
    print(f"  - Goals: {len(session.config.goals)}")
except Exception as e:
    errors.append(f"session: {e}")
    print(f"✗ Session creation failed: {e}")

# Test broadcaster functionality
print("\n3. Testing broadcaster...")

try:
    from events.broadcaster import broadcaster
    import asyncio

    async def test_broadcast():
        # Subscribe
        queue = await broadcaster.subscribe()

        # Broadcast test event
        await broadcaster.broadcast("test", {"message": "test"})

        # Try to receive
        try:
            msg = await asyncio.wait_for(queue.get(), timeout=0.1)
            print(f"✓ Broadcast works: received message")
            return True
        except asyncio.TimeoutError:
            print("✗ Broadcast timeout")
            return False

    result = asyncio.run(test_broadcast())

except Exception as e:
    errors.append(f"broadcast test: {e}")
    print(f"✗ Broadcast test failed: {e}")

# Summary
print("\n" + "=" * 60)
print("SUMMARY")
print("=" * 60)

if errors:
    print(f"\n❌ {len(errors)} errors found:")
    for err in errors:
        print(f"  - {err}")
else:
    print("\n✅ All components loaded successfully!")
    print("\nYou can now run: uv run runner.py")

print("\n" + "=" * 60)