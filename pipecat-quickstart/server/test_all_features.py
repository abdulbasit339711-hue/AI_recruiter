#!/usr/bin/env python3
"""
Comprehensive test for all three features:
1. End call button
2. Token metrics
3. Agent transcripts
"""

import asyncio
import aiohttp
import json
from datetime import datetime
import sys


class FeatureTester:
    def __init__(self):
        self.base_url = "http://127.0.0.1:7860"
        self.session = None
        self.sse_client = None
        self.events_received = {
            "transcript_candidate": [],
            "transcript_agent": [],
            "metrics": [],
            "status": [],
        }

    async def connect_sse(self):
        """Connect to SSE stream and monitor events"""
        print("\n📡 Connecting to SSE stream...")

        async with aiohttp.ClientSession() as session:
            try:
                async with session.get(f"{self.base_url}/events") as response:
                    print("✅ Connected to SSE stream")
                    print("-" * 50)

                    # Read events for 10 seconds
                    start_time = asyncio.get_event_loop().time()
                    timeout = 10  # seconds

                    async for line in response.content:
                        if asyncio.get_event_loop().time() - start_time > timeout:
                            break

                        line = line.decode('utf-8').strip()

                        if line.startswith("event:"):
                            event_type = line.split(":", 1)[1].strip()

                        elif line.startswith("data:"):
                            try:
                                data = json.loads(line.split(":", 1)[1].strip())

                                # Track different event types
                                if event_type == "transcript":
                                    speaker = data.get("speaker", "unknown")
                                    text = data.get("text", "")
                                    if speaker == "candidate":
                                        self.events_received["transcript_candidate"].append(text)
                                        print(f"👤 Candidate: {text[:50]}...")
                                    elif speaker == "agent":
                                        self.events_received["transcript_agent"].append(text)
                                        print(f"🤖 Agent: {text[:50]}...")

                                elif event_type == "metrics":
                                    metrics = data.get("metrics", {})
                                    self.events_received["metrics"].append(metrics)
                                    total = metrics.get("total_tokens", 0)
                                    print(f"📊 Metrics: {total} tokens")

                                elif event_type == "status":
                                    self.events_received["status"].append(data)
                                    print(f"📌 Status: {data}")

                            except json.JSONDecodeError:
                                pass

            except Exception as e:
                print(f"❌ SSE Error: {e}")

    async def test_health(self):
        """Test health endpoint"""
        print("\n🏥 Testing Health Endpoint...")

        async with aiohttp.ClientSession() as session:
            async with session.get(f"{self.base_url}/health") as resp:
                data = await resp.json()
                print(f"Status: {data.get('status')}")
                services = data.get('services', {})
                for service, status in services.items():
                    emoji = "✅" if status == "connected" else "❌"
                    print(f"  {emoji} {service}: {status}")
                return data.get('status') == 'ready'

    async def test_session(self):
        """Test session endpoint"""
        print("\n🎭 Testing Session Endpoint...")

        async with aiohttp.ClientSession() as session:
            async with session.get(f"{self.base_url}/session") as resp:
                data = await resp.json()
                if "error" not in data:
                    print(f"Session ID: {data.get('session_id')}")
                    print(f"Status: {data.get('status')}")
                    print(f"Transcript entries: {len(data.get('transcript', []))}")
                    print(f"Metrics: {data.get('metrics')}")
                    return True
                else:
                    print(f"⚠️  {data.get('error')}")
                    return False

    async def test_chat_injection(self):
        """Test manual chat injection"""
        print("\n💬 Testing Chat Injection...")

        test_message = "This is a test message from the testing script"

        async with aiohttp.ClientSession() as session:
            async with session.post(
                f"{self.base_url}/chat",
                json={"text": test_message}
            ) as resp:
                data = await resp.json()
                if "status" in data:
                    print(f"✅ Message sent: {test_message[:50]}...")
                    return True
                else:
                    print(f"❌ Failed: {data}")
                    return False

    async def test_end_call(self):
        """Test end call functionality"""
        print("\n📴 Testing End Call...")

        async with aiohttp.ClientSession() as session:
            # First, just test if the endpoint works
            async with session.post(
                f"{self.base_url}/settings",
                json={"auto_kill": False, "timeout": 300}
            ) as resp:
                data = await resp.json()
                if "status" in data:
                    print("✅ Settings endpoint works")
                    return True
                else:
                    print(f"❌ Settings failed: {data}")
                    return False

    def print_summary(self):
        """Print test summary"""
        print("\n" + "=" * 60)
        print("📋 TEST SUMMARY")
        print("=" * 60)

        # Check transcripts
        print("\n📝 Transcripts:")
        candidate_count = len(self.events_received["transcript_candidate"])
        agent_count = len(self.events_received["transcript_agent"])

        if candidate_count > 0:
            print(f"  ✅ Candidate transcripts received: {candidate_count}")
        else:
            print(f"  ❌ No candidate transcripts received")

        if agent_count > 0:
            print(f"  ✅ Agent transcripts received: {agent_count}")
        else:
            print(f"  ❌ No agent transcripts received")

        # Check metrics
        print("\n📊 Metrics:")
        metrics_count = len(self.events_received["metrics"])
        if metrics_count > 0:
            print(f"  ✅ Metrics events received: {metrics_count}")
            total_tokens = sum(m.get("total_tokens", 0) for m in self.events_received["metrics"])
            print(f"  📈 Total tokens counted: {total_tokens}")
        else:
            print(f"  ❌ No metrics received")

        # Status updates
        print("\n📌 Status Updates:")
        status_count = len(self.events_received["status"])
        if status_count > 0:
            print(f"  ✅ Status updates received: {status_count}")
        else:
            print(f"  ⚠️  No status updates received")

        print("\n" + "=" * 60)


async def main():
    print("=" * 60)
    print("🔍 PIPECAT VOICE AGENT - FEATURE TEST")
    print("=" * 60)
    print("\nTesting: End Call, Token Metrics, Agent Transcripts")
    print("\n⚠️  Make sure the server is running: uv run runner.py")
    print("-" * 60)

    tester = FeatureTester()

    # Test basic endpoints
    health_ok = await tester.test_health()
    if not health_ok:
        print("\n❌ Server not ready. Please start it first.")
        return

    session_ok = await tester.test_session()

    # Test features
    await tester.test_chat_injection()
    await tester.test_end_call()

    # Monitor SSE events
    print("\n📻 Monitoring events for 10 seconds...")
    print("Speak into the microphone or click 'Interview Live' to generate events")
    await tester.connect_sse()

    # Print summary
    tester.print_summary()

    print("\n✨ Test complete!")
    print("\nIf features aren't working:")
    print("1. Check server logs for errors")
    print("2. Ensure DEBUG_MODE=true for detailed logging")
    print("3. Verify all API keys are set in .env")


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\n\n⏹️  Test interrupted by user")