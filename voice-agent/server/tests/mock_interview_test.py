"""Headless mock interview: spawn a real interview bot, join the LiveKit room as the
candidate, send text 'messages' (driving real LLM + TTS), then disconnect to trigger
finalize. Verifies transcript, goals, token metrics, audio recording, and assessment.
"""
import asyncio
import json
import os
import urllib.request
from livekit import rtc

VOICE = "http://127.0.0.1:7860"
BACKEND = "http://127.0.0.1:8000"
ADMIN_TOKEN = "dev-admin-token-change-me-to-a-long-random-secret"
CANDIDATE_ID = 48


def http_json(url, method="GET", data=None, headers=None):
    h = dict(headers or {})
    body = None
    if data is not None:
        body = json.dumps(data).encode()
        h["Content-Type"] = "application/json"
    req = urllib.request.Request(url, data=body, method=method, headers=h)
    with urllib.request.urlopen(req, timeout=30) as r:
        return json.loads(r.read().decode())


async def main():
    # 1) mint a fresh interview link for candidate 48
    invite = http_json(
        f"{BACKEND}/candidates/{CANDIDATE_ID}/interview-invite",
        method="POST",
        headers={"Authorization": f"Bearer {ADMIN_TOKEN}"},
    )
    token = invite["link"].split("/interview/")[-1]
    print(f"[1] minted interview link (token len={len(token)})")

    # 2) validate -> spawns a dedicated real interview bot, returns join creds
    v = http_json(f"{VOICE}/interview/validate?token={token}")
    assert v.get("valid"), f"validate failed: {v}"
    session_id = v["session_id"]
    print(f"[2] interview bot ready: room={v['room_name']} session={session_id}")

    # 3) join the room as the candidate participant (fires the bot's greeting)
    room = rtc.Room()
    await room.connect(v["livekit_url"], v["livekit_token"])
    print(f"[3] joined LiveKit room as candidate-{CANDIDATE_ID}")
    await asyncio.sleep(8)  # let the bot greet (first TTS output)

    # 4) send candidate 'messages' -> real LLM response + TTS audio per turn
    messages = [
        "Hi, thanks for having me. I have six years of experience as a DevOps engineer.",
        "I've worked heavily with Kubernetes, Terraform, AWS and CI/CD pipelines on GitLab.",
        "At my last job I cut deployment time by about seventy percent by automating releases.",
        "I run monitoring with Prometheus and Grafana and I'm comfortable with on-call rotations.",
    ]
    for i, m in enumerate(messages, 1):
        r = http_json(f"{VOICE}/chat", method="POST", data={"text": m, "session": session_id})
        print(f"[4.{i}] sent candidate msg -> {r}")
        await asyncio.sleep(10)  # wait for LLM + TTS to complete

    # 5) disconnect -> on_participant_disconnected cancels worker -> finalize_session()
    await room.disconnect()
    print("[5] candidate disconnected; waiting for finalize (audio save + assessment)...")
    await asyncio.sleep(15)
    print(f"[done] session_id={session_id}")


if __name__ == "__main__":
    asyncio.run(main())
