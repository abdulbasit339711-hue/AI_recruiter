#!/usr/bin/env python3
"""Replay a saved interview conversation against the running bot to test goal tracking.

Sends each candidate (applicant) turn to the bot's POST /chat endpoint with a delay
between turns so the bot can reply and the goal-tracking analysis (throttled to one
analysis per ~5s) can run. Watch the dashboard or the bot logs to see goals progress.

Usage:
    uv run python tests/test_conversations/replay_conversation.py
    uv run python tests/test_conversations/replay_conversation.py --file tests/test_conversations/backend_engineer_interview.json --delay 9
    uv run python tests/test_conversations/replay_conversation.py --url http://127.0.0.1:7860
"""
import argparse
import json
import time
import urllib.request
from pathlib import Path

DEFAULT_FILE = Path(__file__).with_name("backend_engineer_interview.json")


def post_chat(base_url: str, text: str) -> dict:
    data = json.dumps({"text": text}).encode("utf-8")
    req = urllib.request.Request(
        f"{base_url.rstrip('/')}/chat",
        data=data,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=30) as resp:
        return json.loads(resp.read().decode("utf-8"))


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--url", default="http://127.0.0.1:7860", help="Bot server base URL")
    parser.add_argument("--file", default=str(DEFAULT_FILE), help="Conversation JSON file")
    parser.add_argument(
        "--delay",
        type=float,
        default=25.0,
        help=(
            "Seconds to wait between turns. The bot speaks each reply via TTS and a new "
            "message sent mid-reply INTERRUPTS it, so keep this longer than the bot takes "
            "to finish talking (TTS here is slow). Lower it if you disable/speed up TTS."
        ),
    )
    args = parser.parse_args()

    convo = json.loads(Path(args.file).read_text())
    turns = [t for t in convo.get("turns", []) if t.get("speaker") == "candidate"]
    print(f"Replaying {len(turns)} candidate turn(s) to {args.url}/chat "
          f"(delay {args.delay}s between turns)\n")

    for i, turn in enumerate(turns, 1):
        text = turn["text"]
        targets = turn.get("targets", "")
        preview = text if len(text) <= 80 else text[:77] + "..."
        print(f"[{i}/{len(turns)}] (goal: {targets}) -> {preview}")
        try:
            result = post_chat(args.url, text)
            print(f"      server: {result}")
        except Exception as e:  # noqa: BLE001
            print(f"      ERROR: {e} — is the bot running on {args.url}?")
            return
        if i < len(turns):
            time.sleep(args.delay)

    print("\nDone. Check the dashboard transcript and goal panel, or query the DB:")
    print("  PGPASSWORD=secure_password psql -h localhost -U ai_user -d ai_recruiter \\")
    print("    -c \"SELECT gt.title, sg.completion_status, sg.progress_score \"")
    print("       \"FROM session_goals sg JOIN goal_templates gt ON sg.goal_template_id=gt.id \"")
    print("       \"ORDER BY sg.created_at DESC;\"")


if __name__ == "__main__":
    main()
