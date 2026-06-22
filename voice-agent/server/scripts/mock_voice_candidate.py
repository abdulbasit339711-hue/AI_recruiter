#!/usr/bin/env python3
"""FULL-VOICE mock candidate — joins the interview's LiveKit room as a real participant
and SPEAKS scripted answers as published audio.

Unlike scripts/mock_interview.py (which injects candidate text via /chat), this drives
the true voice loop: each answer is synthesized with Deepgram TTS and published as the
candidate's microphone track, so the bot hears it through Deepgram STT and the saved
recording captures BOTH voices. Pacing is turn-aware via the /events SSE stream.

Prereqs: runner.py up (:7860); DEEPGRAM_API_KEY set (same key the bot uses).

Usage:
    # mint a link (admin), then pass its JWT:
    uv run python scripts/mock_voice_candidate.py --token <interview-jwt>
    uv run python scripts/mock_voice_candidate.py --token <jwt> --file answers.json --gap 10
"""
import argparse
import asyncio
import json
import os
import struct
import sys
import threading
import urllib.request

from dotenv import load_dotenv
from livekit import rtc

load_dotenv()  # read DEEPGRAM_API_KEY etc. from voice-agent/server/.env

SR = 24000           # Deepgram Aura linear16 sample rate
FRAME_MS = 20        # publish in 20ms frames for real-time pacing
DG_MODEL = os.getenv("DEEPGRAM_VOICE", "aura-2-thalia-en")

SAMPLE_ANSWERS = [
    "Hi! Yes, I'm ready to start.",
    "Most recently I built a churn-prediction model that lifted retention by about eight percent.",
    "I started with gradient-boosted trees as a baseline, then compared against logistic regression for interpretability.",
    "For missing values I look at why they're missing, then use median or model-based imputation.",
    "I guard against overfitting with cross-validation and by watching the train-validation gap.",
]


def _synth_pcm(text: str, api_key: str) -> bytes:
    """Deepgram TTS → 16-bit mono PCM at SR. Strips a WAV header if one is returned."""
    req = urllib.request.Request(
        f"https://api.deepgram.com/v1/speak?model={DG_MODEL}&encoding=linear16&sample_rate={SR}",
        data=json.dumps({"text": text}).encode(),
        headers={"Authorization": f"Token {api_key}", "Content-Type": "application/json"},
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=30) as resp:
        audio = resp.read()
    if audio[:4] == b"RIFF":  # find the 'data' chunk and return the PCM after it
        idx = audio.find(b"data")
        if idx != -1:
            return audio[idx + 8:]
    return audio


async def _speak(source: rtc.AudioSource, pcm: bytes):
    """Publish PCM as real-time-paced audio frames."""
    samples_per_frame = SR * FRAME_MS // 1000
    bytes_per_frame = samples_per_frame * 2  # 16-bit mono
    for i in range(0, len(pcm), bytes_per_frame):
        chunk = pcm[i:i + bytes_per_frame]
        if len(chunk) < bytes_per_frame:
            chunk = chunk + b"\x00" * (bytes_per_frame - len(chunk))  # pad last frame
        frame = rtc.AudioFrame(chunk, SR, 1, samples_per_frame)
        await source.capture_frame(frame)


def _validate(url: str, token: str) -> dict:
    with urllib.request.urlopen(f"{url}/interview/validate?token={token}", timeout=30) as r:
        return json.loads(r.read())


def _sse_listener(url: str, session: str, replied: threading.Event, stop: threading.Event):
    """Set `replied` whenever the interviewer produces a turn on the event stream."""
    try:
        with urllib.request.urlopen(f"{url}/events?session={session}", timeout=600) as resp:
            for raw in resp:
                if stop.is_set():
                    return
                line = raw.decode(errors="replace").strip()
                if not line.startswith("data:"):
                    continue
                try:
                    evt = json.loads(line[5:].strip())
                except ValueError:
                    continue
                if evt.get("speaker") == "agent" and evt.get("text"):
                    print(f"\n  🤖 INTERVIEWER: {evt['text'].strip()}\n")
                    replied.set()
    except Exception as e:  # noqa: BLE001
        if not stop.is_set():
            print(f"[events closed: {e}]", file=sys.stderr)


async def main():
    ap = argparse.ArgumentParser(description="Full-voice mock candidate (publishes spoken answers).")
    ap.add_argument("--token", required=True, help="interview link JWT (from a minted /interview link)")
    ap.add_argument("--url", default="http://127.0.0.1:7860", help="runner.py base URL")
    ap.add_argument("--file", help="JSON list of candidate answer strings")
    ap.add_argument("--gap", type=float, default=10.0, help="max seconds to wait for each interviewer reply")
    args = ap.parse_args()

    api_key = os.getenv("DEEPGRAM_API_KEY")
    if not api_key:
        sys.exit("DEEPGRAM_API_KEY not set")
    answers = json.loads(open(args.file).read()) if args.file else SAMPLE_ANSWERS

    v = _validate(args.url, args.token)
    if not v.get("valid"):
        sys.exit(f"link invalid: {v.get('error')}")
    session = v["session_id"]
    print(f"== Full-voice mock — room {v.get('room_name')} (session {session}) ==")

    room = rtc.Room()
    await room.connect(v["livekit_url"], v["livekit_token"])
    source = rtc.AudioSource(SR, 1)
    track = rtc.LocalAudioTrack.create_audio_track("candidate-voice", source)
    await room.local_participant.publish_track(track, rtc.TrackPublishOptions())
    print("  published candidate audio track")

    replied, stop = threading.Event(), threading.Event()
    threading.Thread(target=_sse_listener, args=(args.url, session, replied, stop), daemon=True).start()

    # Let the bot greet (it greets once it subscribes to our track).
    replied.clear()
    await asyncio.sleep(1.0)
    replied.wait(timeout=args.gap)
    await asyncio.sleep(2.0)

    for i, text in enumerate(answers, 1):
        print(f"  🧑 CANDIDATE [{i}/{len(answers)}]: {text}")
        pcm = await asyncio.get_event_loop().run_in_executor(None, _synth_pcm, text, api_key)
        replied.clear()
        await _speak(source, pcm)
        # Wait for the interviewer's spoken reply before the next answer.
        await asyncio.get_event_loop().run_in_executor(None, replied.wait, args.gap)
        await asyncio.sleep(2.0)

    await asyncio.sleep(2.0)
    stop.set()
    await room.disconnect()
    print("== done — disconnecting finalizes the interview (recording has both voices) ==")


if __name__ == "__main__":
    asyncio.run(main())
