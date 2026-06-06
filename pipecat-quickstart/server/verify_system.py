#!/usr/bin/env python3
"""
Verify the entire system is working correctly
"""

import asyncio
import aiohttp
import json
import time
from datetime import datetime
from colorama import init, Fore, Style

init(autoreset=True)


def print_header(text):
    print(f"\n{Fore.CYAN}{'=' * 60}")
    print(f"{Fore.CYAN}{text:^60}")
    print(f"{Fore.CYAN}{'=' * 60}{Style.RESET_ALL}")


def print_test(name, passed, details=""):
    if passed:
        print(f"{Fore.GREEN}✅ {name}{Style.RESET_ALL}")
        if details:
            print(f"   {Fore.WHITE}{details}{Style.RESET_ALL}")
    else:
        print(f"{Fore.RED}❌ {name}{Style.RESET_ALL}")
        if details:
            print(f"   {Fore.YELLOW}{details}{Style.RESET_ALL}")


async def check_server():
    """Check if server is running"""
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get("http://127.0.0.1:7860/health") as resp:
                if resp.status == 200:
                    data = await resp.json()
                    return True, data
    except:
        return False, None
    return False, None


async def monitor_sse_events(duration=5):
    """Monitor SSE events for a duration"""
    events = {
        "transcript_candidate": [],
        "transcript_agent": [],
        "metrics": [],
        "evaluation": [],
        "status": [],
        "service": [],
    }

    try:
        async with aiohttp.ClientSession() as session:
            async with session.get("http://127.0.0.1:7860/events") as response:
                start_time = time.time()

                async for line in response.content:
                    if time.time() - start_time > duration:
                        break

                    line = line.decode('utf-8').strip()

                    if line.startswith("event:"):
                        event_type = line.split(":", 1)[1].strip()

                    elif line.startswith("data:"):
                        try:
                            data = json.loads(line.split(":", 1)[1].strip())

                            if event_type == "transcript":
                                speaker = data.get("speaker", "unknown")
                                text = data.get("text", "")
                                if speaker == "candidate":
                                    events["transcript_candidate"].append(text)
                                elif speaker == "agent":
                                    events["transcript_agent"].append(text)

                            elif event_type == "metrics":
                                events["metrics"].append(data.get("metrics", {}))

                            elif event_type == "evaluation":
                                events["evaluation"].append(data)

                            elif event_type == "status":
                                events["status"].append(data)

                            elif event_type == "service":
                                events["service"].append(data)

                        except:
                            pass

    except Exception as e:
        print(f"{Fore.RED}SSE Error: {e}{Style.RESET_ALL}")

    return events


async def test_manual_injection():
    """Test manual text injection"""
    try:
        async with aiohttp.ClientSession() as session:
            # Inject a test message
            test_msg = "Hello, this is a test message"
            async with session.post(
                "http://127.0.0.1:7860/chat",
                json={"text": test_msg}
            ) as resp:
                if resp.status == 200:
                    return True, test_msg
    except:
        pass
    return False, None


async def test_settings_endpoint():
    """Test settings/end call endpoint"""
    try:
        async with aiohttp.ClientSession() as session:
            async with session.post(
                "http://127.0.0.1:7860/settings",
                json={"timeout": 300, "auto_kill": False}
            ) as resp:
                if resp.status == 200:
                    data = await resp.json()
                    return data.get("status") == "success"
    except:
        pass
    return False


async def main():
    print_header("PIPECAT VOICE AGENT - SYSTEM VERIFICATION")

    # 1. Check server
    print(f"\n{Fore.YELLOW}1. Checking server status...{Style.RESET_ALL}")
    is_running, health_data = await check_server()

    if not is_running:
        print_test("Server Running", False, "Server not reachable at http://127.0.0.1:7860")
        print(f"\n{Fore.RED}Please start the server first:{Style.RESET_ALL}")
        print(f"  cd pipecat-quickstart/server")
        print(f"  uv run runner.py")
        return

    print_test("Server Running", True)

    # Check services
    services = health_data.get("services", {})
    for service, status in services.items():
        print_test(f"  {service} Service", status == "connected", status)

    # 2. Test settings endpoint (for end call button)
    print(f"\n{Fore.YELLOW}2. Testing end call functionality...{Style.RESET_ALL}")
    settings_ok = await test_settings_endpoint()
    print_test("Settings Endpoint", settings_ok, "Required for end call button")

    # 3. Test manual injection
    print(f"\n{Fore.YELLOW}3. Testing manual text injection...{Style.RESET_ALL}")
    inject_ok, test_msg = await test_manual_injection()
    print_test("Chat Injection", inject_ok, f"Sent: {test_msg}" if inject_ok else "Failed to inject")

    # 4. Monitor events
    print(f"\n{Fore.YELLOW}4. Monitoring SSE events (5 seconds)...{Style.RESET_ALL}")
    print(f"{Fore.WHITE}   Please speak or click 'Interview Live' to generate events{Style.RESET_ALL}")

    events = await monitor_sse_events(5)

    # Check results
    print(f"\n{Fore.YELLOW}5. Event Summary:{Style.RESET_ALL}")

    # Transcripts
    candidate_count = len(events["transcript_candidate"])
    agent_count = len(events["transcript_agent"])

    print_test(
        "Candidate Transcripts",
        candidate_count > 0,
        f"Received: {candidate_count} messages" if candidate_count > 0 else "No messages received"
    )

    print_test(
        "Agent Transcripts",
        agent_count > 0,
        f"Received: {agent_count} messages" if agent_count > 0 else "No messages received"
    )

    # Metrics
    metrics_count = len(events["metrics"])
    total_tokens = sum(m.get("total_tokens", 0) for m in events["metrics"])

    print_test(
        "Token Metrics",
        metrics_count > 0,
        f"Events: {metrics_count}, Total tokens: {total_tokens}" if metrics_count > 0 else "No metrics received"
    )

    # Service status
    service_count = len(events["service"])
    print_test(
        "Service Events",
        service_count > 0,
        f"Received: {service_count} updates" if service_count > 0 else "No service updates"
    )

    # Overall assessment
    print_header("VERIFICATION RESULTS")

    all_working = (
        is_running and
        settings_ok and
        inject_ok
    )

    if all_working:
        print(f"{Fore.GREEN}✅ Core systems are operational{Style.RESET_ALL}")

        if candidate_count == 0 and agent_count == 0 and metrics_count == 0:
            print(f"\n{Fore.YELLOW}⚠️  No live events detected{Style.RESET_ALL}")
            print("This is normal if no conversation is active.")
            print("\nTo generate events:")
            print("1. Open the dashboard in browser: http://127.0.0.1:7860")
            print("2. Click 'Interview Live' button")
            print("3. Speak into your microphone")
            print("4. The agent should respond and events should appear")
    else:
        print(f"{Fore.RED}❌ Some systems are not working properly{Style.RESET_ALL}")
        print("\nTroubleshooting:")
        print("1. Check server logs for errors")
        print("2. Verify all API keys in .env")
        print("3. Set DEBUG_MODE=true for detailed logging")

    print(f"\n{Fore.CYAN}Test complete!{Style.RESET_ALL}")


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print(f"\n{Fore.YELLOW}Test interrupted{Style.RESET_ALL}")