#!/usr/bin/env python3
"""
SSE Connection Test Script
Tests if Server-Sent Events are properly reaching the client.
"""

import asyncio
import aiohttp
import json
from datetime import datetime


async def test_sse_connection():
    """Test SSE connection and print received events."""

    url = "http://127.0.0.1:7860/events"

    print(f"[{datetime.now().isoformat()}] Connecting to SSE endpoint: {url}")

    async with aiohttp.ClientSession() as session:
        try:
            async with session.get(url) as response:
                print(f"[{datetime.now().isoformat()}] Connected! Status: {response.status}")
                print("-" * 50)

                async for line in response.content:
                    line = line.decode('utf-8').strip()

                    if line.startswith("event:"):
                        event_type = line.split(":", 1)[1].strip()
                        print(f"\n[EVENT] Type: {event_type}")

                    elif line.startswith("data:"):
                        try:
                            data = json.loads(line.split(":", 1)[1].strip())
                            print(f"[DATA] {json.dumps(data, indent=2)}")
                        except json.JSONDecodeError as e:
                            print(f"[DATA] Raw: {line}")

                    elif line == "":
                        print("-" * 30)

        except aiohttp.ClientError as e:
            print(f"[ERROR] Connection failed: {e}")
        except KeyboardInterrupt:
            print("\n[INFO] Test stopped by user")


async def test_session_endpoint():
    """Test the /session endpoint."""

    url = "http://127.0.0.1:7860/session"

    async with aiohttp.ClientSession() as session:
        try:
            async with session.get(url) as response:
                data = await response.json()
                print("\n[SESSION ENDPOINT]")
                print(json.dumps(data, indent=2))
        except Exception as e:
            print(f"[ERROR] Session endpoint failed: {e}")


async def test_health_endpoint():
    """Test the /health endpoint."""

    url = "http://127.0.0.1:7860/health"

    async with aiohttp.ClientSession() as session:
        try:
            async with session.get(url) as response:
                data = await response.json()
                print("\n[HEALTH ENDPOINT]")
                print(json.dumps(data, indent=2))
        except Exception as e:
            print(f"[ERROR] Health endpoint failed: {e}")


async def main():
    print("=" * 60)
    print("SSE Connection Test - Pipecat Voice Agent")
    print("=" * 60)

    # Test health and session first
    await test_health_endpoint()
    await test_session_endpoint()

    print("\n" + "=" * 60)
    print("Starting SSE Event Stream Monitor...")
    print("Press Ctrl+C to stop")
    print("=" * 60)

    # Monitor SSE events
    await test_sse_connection()


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\nTest completed.")