#!/usr/bin/env python3
"""Live end-to-end driver: IQ screen -> resume upload -> AUDIO interview -> finalize.

Drives the RUNNING backend (:8000) and voice server (:7860) with real services
(Groq LLM, Deepgram STT/TTS, LiveKit Cloud). The bot speaks each turn (TTS audio,
recorded); the candidate's turns are injected as text via /chat; the judge scores
each answer and goals progress. Prints the candidate interview link + HR dashboard
link, then the full evaluation HR sees.

Prereqs (start these first):
    # backend (repo root, main venv):
    python -m uvicorn app.main:app --host 127.0.0.1 --port 8000
    # voice (voice-agent/server, uv venv):
    uv run python runner.py

Run:
    # with audio presence (needs livekit -> run from the voice venv):
    cd voice-agent/server && uv run python ../../scripts/live_interview_e2e.py
    # text-only turns (no LiveKit join; works from the main venv):
    python scripts/live_interview_e2e.py --no-audio

Env / .env used: ADMIN_API_TOKEN, INTERVIEW_LINK_SECRET, WEB_BASE_URL.
"""
import argparse
import asyncio
import json
import os
import urllib.error
import urllib.request
from urllib.parse import urlencode

try:  # both .env files are optional; env vars win if already set
    from dotenv import load_dotenv
    load_dotenv("/mnt/muaaz/AI_recruiter/.env")
    load_dotenv("/mnt/muaaz/AI_recruiter/voice-agent/server/.env")
except Exception:
    pass

from recruiter_shared.tokens import mint_invite_token

JOB = {
    "title": "Senior DevOps Engineer",
    "department": "Platform Engineering",
    "job_description": (
        "Senior DevOps Engineer to own our Kubernetes platform on AWS: infrastructure as "
        "code (Terraform), CI/CD pipelines, observability (Prometheus, Grafana, tracing), "
        "deployment reliability and on-call. 5+ years required."
    ),
    "llm_prompt": "Evaluate on Kubernetes, IaC (Terraform), CI/CD, and observability depth.",
}
TURNS = [
    "Hi, thanks for having me. I'm a senior DevOps engineer with six years of experience, most "
    "recently leading the platform team at a fintech startup running Kubernetes across three AWS regions.",
    "We manage everything as code with Terraform and Terragrunt, about forty reusable modules, with an "
    "OPA and Conftest policy layer in CI that cut our infrastructure incidents roughly in half.",
    "I rebuilt our deploys on GitLab CI with blue-green and automated rollbacks, taking deploys from "
    "forty minutes and manual down to under five minutes with zero downtime.",
    "For observability we run Prometheus, Grafana and Alertmanager into PagerDuty, SLO dashboards with "
    "error budgets, and OpenTelemetry tracing with Tempo plus Loki for logs.",
    "Honestly for the rest I'm comfortable with most cloud tooling and tend to figure things out as I go.",
]


def req(url, method="GET", data=None, headers=None, timeout=60):
    r = urllib.request.Request(url, data=data, method=method, headers=dict(headers or {}))
    try:
        with urllib.request.urlopen(r, timeout=timeout) as resp:
            b = resp.read().decode()
            return json.loads(b) if b else {}
    except urllib.error.HTTPError as e:
        raise RuntimeError(f"{method} {url} -> {e.code}: {e.read().decode()[:300]}")


def upload_pdf(url, path, headers, extra=None):
    bnd = "----liveE2EBoundary"
    parts = []
    for k, v in (extra or {}).items():
        parts.append(f"--{bnd}\r\nContent-Disposition: form-data; name=\"{k}\"\r\n\r\n{v}\r\n".encode())
    with open(path, "rb") as f:
        fb = f.read()
    parts.append(
        f"--{bnd}\r\nContent-Disposition: form-data; name=\"file\"; filename=\"{os.path.basename(path)}\"\r\n".encode()
        + b"Content-Type: application/pdf\r\n\r\n" + fb + f"\r\n--{bnd}--\r\n".encode()
    )
    h = dict(headers)
    h["Content-Type"] = f"multipart/form-data; boundary={bnd}"
    return req(url, "POST", b"".join(parts), h)


def banner(m):
    print(f"\n{'=' * 72}\n{m}\n{'=' * 72}")


async def main(a):
    admin = {"Authorization": f"Bearer {a.admin_token}"}
    secret = os.environ.get("INTERVIEW_LINK_SECRET")
    if not secret:
        raise SystemExit("INTERVIEW_LINK_SECRET not set (needed to mint the interview link).")

    banner("STEP 1 — HR creates a job")
    job = req(f"{a.backend}/jobs?{urlencode(JOB)}", "POST", headers=admin)
    jid = job["id"]
    print(f"  job #{jid}: {job['title']}")

    banner("STEP 2 — Candidate takes the IQ screen (generic MCQs, server-scored)")
    test = req(f"{a.backend}/iq-test?job_id={jid}")
    answers = {q["id"]: (i % 4) for i, q in enumerate(test["questions"])}  # deterministic mixed answers
    iq = req(f"{a.backend}/iq-test/submit", "POST",
             json.dumps({"test_token": test["test_token"], "answers": answers}).encode(),
             {"Content-Type": "application/json"})
    print(f"  IQ result: {iq['correct']}/{iq['total']} = {iq['score']}%  (token issued)")

    banner("STEP 3 — Candidate uploads resume WITH the IQ token attached")
    up = upload_pdf(f"{a.backend}/upload?job_id={jid}", a.resume, admin, extra={"iq_token": iq["result_token"]})
    cid = up["id"]
    print(f"  candidate #{cid} ({up['status']})  resume={os.path.basename(a.resume)}")
    print("  waiting for 3-tier scoring...")
    for _ in range(40):
        await asyncio.sleep(3)
        c = req(f"{a.backend}/candidates/{cid}", headers=admin)
        if c.get("status") in ("Shortlisted", "Reviewed", "Rejected", "Ungraded", "Error"):
            print(f"  scored: {c['status']}  T1={c['tier1']} T2={c['tier2']} T3={c['tier3']} "
                  f"total={c['total_score']}  |  IQ={c.get('iq_score')}% ({c.get('iq_correct')}/{c.get('iq_total')})")
            break

    banner("STEP 4 — Mint interview link + spawn bot")
    token = mint_invite_token(cid, jid, secret)
    web_base = os.environ.get("WEB_BASE_URL", "http://localhost:3000").rstrip("/")
    interview_link = f"{web_base}/interview/{token}"
    dashboard_link = f"{web_base}/admin/candidates/{cid}/interview"
    print(f"  CANDIDATE INTERVIEW LINK: {interview_link}")
    print(f"  HR DASHBOARD LINK:        {dashboard_link}")
    v = req(f"{a.voice}/interview/validate?token={token}")
    if not v.get("valid"):
        raise SystemExit(f"  validate failed: {v}")
    sid = v["session_id"]
    print(f"  bot ready in room {v['room_name']} (session {sid})")

    banner("STEP 5 — Candidate joins + audio interview (bot speaks each turn)")
    room = None
    if not a.no_audio:
        try:
            from livekit import rtc
            room = rtc.Room()
            await room.connect(v["livekit_url"], v["livekit_token"])
            print("  joined LiveKit room; letting the bot greet (audio)...")
        except Exception as e:
            print(f"  (livekit unavailable: {e}; continuing text-only)")
            room = None
    await asyncio.sleep(9 if room else 4)
    for i, t in enumerate(TURNS, 1):
        req(f"{a.voice}/chat", "POST", json.dumps({"text": t, "session": sid}).encode(),
            {"Content-Type": "application/json"})
        print(f"  [{i}/{len(TURNS)}] candidate: {t[:64]}...")
        await asyncio.sleep(a.turn_delay)

    banner("STEP 6 — Candidate leaves -> finalize (audio + tokens + assessment)")
    if room:
        await room.disconnect()
    print("  finalizing...")
    await asyncio.sleep(18)

    banner("STEP 7 — FULL EVALUATION (what HR sees)")
    d = req(f"{a.backend}/candidates/{cid}/interview", headers=admin)
    if not d.get("has_interview"):
        raise SystemExit(f"  no interview data: {json.dumps(d)[:300]}")
    m = d["metrics"]["interview"]
    print(f"  IQ screen: {iq['score']}%  (recorded pre-application)")
    print(f"  Tokens: STT~{m['stt_tokens']} LLMin {m['llm_input_tokens']} LLMout {m['llm_output_tokens']} "
          f"TTS~{m['tts_tokens']} | total {m['total_tokens']} | ${m['cost_usd']:.5f}")
    print("\n— Transcript (with per-answer judge scores) —")
    for t in d["transcript"]:
        who = "BOT " if t["speaker"] == "agent" else "CAND"
        line = f"  {who}: {t['text'][:78]}"
        ev = t.get("evaluation")
        if t["speaker"] != "agent" and ev:
            line += f"\n        > judge {ev.get('score')}/10 - {ev.get('depth')}"
        print(line)
    print("\n— Goals —")
    for g in d["goals"]:
        print(f"  {g['title']}: {g['completion_status']} ({round(float(g['progress_score'] or 0) * 100)}%)")
    print("\n— Final assessment —")
    try:
        ov = json.loads(d["session"]["overall_assessment"]).get("overall_assessment", {})
        print(f"  recommendation: {ov.get('hiring_recommendation')} | "
              f"performance: {round(float(ov.get('candidate_performance', 0)) * 100)}%")
        print(f"  strengths: {ov.get('strengths', [])}")
        print(f"  improve:   {ov.get('areas_for_improvement', [])}")
    except Exception:
        print("  ", str(d["session"].get("overall_assessment"))[:300])
    print(f"\n  audio recorded: {d.get('has_audio')}")
    banner("DONE")
    print(f"  CANDIDATE INTERVIEW LINK: {interview_link}")
    print(f"  HR DASHBOARD LINK:        {dashboard_link}")
    print(f"  job #{jid} · candidate #{cid} · session {sid}")


if __name__ == "__main__":
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--backend", default=os.getenv("BACKEND_URL", "http://127.0.0.1:8000"))
    p.add_argument("--voice", default=os.getenv("VOICE_URL", "http://127.0.0.1:7860"))
    p.add_argument("--admin-token", default=os.getenv("ADMIN_API_TOKEN", ""))
    p.add_argument("--resume", default="/mnt/muaaz/AI_recruiter/test_resumes/07_ats_score_100.pdf")
    p.add_argument("--turn-delay", type=float, default=11.0, help="seconds between candidate turns")
    p.add_argument("--no-audio", action="store_true", help="don't join the LiveKit room (text turns only)")
    args = p.parse_args()
    if not args.admin_token:
        raise SystemExit("Set ADMIN_API_TOKEN (env or --admin-token).")
    asyncio.run(main(args))
