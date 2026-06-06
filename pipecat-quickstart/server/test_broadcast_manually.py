#!/usr/bin/env python3
"""
Manual broadcast test - simulates transcript and metrics events
Run this while the dashboard is open to test if events are received
"""

import asyncio
import aiohttp
import json
from datetime import datetime


async def trigger_test_events():
    """Send test events to the dashboard via the API."""

    base_url = "http://127.0.0.1:7860"

    async with aiohttp.ClientSession() as session:
        print("Testing manual event broadcasting...")
        print("=" * 50)

        # First check if server is running
        try:
            async with session.get(f"{base_url}/health") as resp:
                health = await resp.json()
                print(f"Server Health: {json.dumps(health, indent=2)}")
        except Exception as e:
            print(f"Error: Server not running? {e}")
            return

        # Send a manual chat message to trigger transcript
        print("\n1. Sending test chat message...")
        try:
            async with session.post(
                f"{base_url}/chat",
                json={"text": "Hello, this is a test message"}
            ) as resp:
                result = await resp.json()
                print(f"Chat response: {result}")
        except Exception as e:
            print(f"Chat error: {e}")

        await asyncio.sleep(2)

        print("\n" + "=" * 50)
        print("Check your dashboard - you should see:")
        print("1. The test message in the transcript (if chat endpoint works)")
        print("2. Service status indicators should be green")
        print("\nIf nothing appears, check the server logs for errors.")


async def direct_broadcast_test():
    """Directly test the broadcaster without going through HTTP."""

    print("\n" + "=" * 50)
    print("Direct broadcaster test...")

    import sys
    sys.path.insert(0, '.')

    from events.broadcaster import broadcaster

    # Create a test subscriber
    queue = await broadcaster.subscribe()
    print("✓ Subscribed to broadcaster")

    # Send test events
    test_events = [
        ("transcript", {"speaker": "candidate", "text": "Test candidate message"}),
        ("transcript", {"speaker": "agent", "text": "Test agent response"}),
        ("metrics", {"metrics": {"prompt_tokens": 100, "completion_tokens": 50, "total_tokens": 150}}),
        ("evaluation", {"data": {"score": 8, "critique": "Good answer"}}),
    ]

    for event_type, data in test_events:
        print(f"\nBroadcasting {event_type}: {data}")
        await broadcaster.broadcast(event_type, data)

        # Try to receive our own broadcast
        try:
            message = await asyncio.wait_for(queue.get(), timeout=0.1)
            print(f"✓ Confirmed broadcast: {message[:100]}...")
        except asyncio.TimeoutError:
            print(f"✗ No echo received for {event_type}")

    broadcaster.unsubscribe(queue)


async def main():
    print("=" * 60)
    print("Manual Broadcast Test")
    print("=" * 60)

    # Test via HTTP
    await trigger_test_events()

    # Test direct broadcast
    await direct_broadcast_test()


if __name__ == "__main__":
    asyncio.run(main())