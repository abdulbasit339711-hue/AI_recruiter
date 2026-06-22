"""
End-to-end interview pipeline test / demo.

Runs the WHOLE flow against the live system, with real services:
  1. Create a job (HR)
  2. Apply as a candidate (upload a resume PDF) -> 3-tier scoring runs
  3. Spawn the interview bot from the candidate's link, join the LiveKit room
  4. Hold a chat+audio interview (real LLM + TTS; real-time judge per answer)
  5. Disconnect -> finalize (audio WAV + per-service tokens + final assessment)
  6. Print the complete evaluation (scores, transcript w/ per-message evals,
     token breakdown, goals, final assessment) and the HR dashboard URL.

Run it (from this directory, so the voice venv + livekit client are available):
    uv run python e2e_interview_pipeline.py
Optional: pass a resume PDF path as the first argument.
"""
import asyncio
import json
import os
import sys
import time
import urllib.request
import urllib.error

from livekit import rtc

VOICE = os.getenv("VOICE_URL", "http://127.0.0.1:7860")
BACKEND = os.getenv("BACKEND_URL", "http://127.0.0.1:8000")
ADMIN_TOKEN = os.getenv("ADMIN_API_TOKEN", "dev-admin-token-change-me-to-a-long-random-secret")
FRONTEND = os.getenv("FRONTEND_URL", "http://localhost:3000")
DEFAULT_RESUME = "/mnt/muaaz/AI_recruiter/test_resumes/07_ats_score_100.pdf"

JOB = {
    "title": "Senior DevOps Engineer",
    "department": "Platform Engineering",
    "job_description": (
        "We are hiring a Senior DevOps Engineer to own our Kubernetes platform on AWS. "
        "You will manage infrastructure as code (Terraform), build CI/CD pipelines, run "
        "observability (Prometheus, Grafana, tracing), and improve deployment reliability "
        "and on-call practices. 5+ years of experience required."
    ),
    "llm_prompt": "Evaluate the candidate on Kubernetes, IaC (Terraform), CI/CD, and observability depth.",
}

# Substantive, varied candidate answers so per-message evaluations are realistic.
CANDIDATE_MESSAGES = [
    "Hi, thanks for having me. I'm a senior DevOps engineer with six years of experience. Most "
    "recently I led the platform team at a fintech startup, owning our Kubernetes infrastructure "
    "across three AWS regions serving about two million daily active users.",

    "We manage everything as code with Terraform and Terragrunt, around forty reusable modules. I "
    "introduced a policy-as-code layer using OPA and Conftest so misconfigurations are caught in CI "
    "before they reach production, which cut our infrastructure-related incidents roughly in half.",

    "When I joined, deployments took about forty minutes and were manual. I rebuilt the pipeline on "
    "GitLab CI with blue-green deploys and automated rollbacks, bringing deploys under five minutes "
    "with zero downtime. That let the team ship roughly four times more often.",

    "For observability we run Prometheus and Grafana with Alertmanager paging into PagerDuty. I built "
    "SLO dashboards with error budgets, and we use distributed tracing with OpenTelemetry and Tempo "
    "to debug cross-service latency, plus Loki for log aggregation.",

    "Honestly for the rest I'm pretty comfortable with most cloud tooling and I tend to figure things "
    "out as I go.",
]


def _req(url, method="GET", data=None, headers=None, timeout=60):
    h = dict(headers or {})
    req = urllib.request.Request(url, data=data, method=method, headers=h)
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            body = r.read().decode()
            return json.loads(body) if body else {}
    except urllib.error.HTTPError as e:
        raise RuntimeError(f"{method} {url} -> {e.code}: {e.read().decode()[:300]}")


def admin_headers():
    return {"Authorization": f"Bearer {ADMIN_TOKEN}"}


def post_multipart_pdf(url, filepath, headers=None):
    boundary = "----e2eInterviewBoundary"
    with open(filepath, "rb") as f:
        filebytes = f.read()
    fname = os.path.basename(filepath)
    body = (
        f"--{boundary}\r\n".encode()
        + f'Content-Disposition: form-data; name="file"; filename="{fname}"\r\n'.encode()
        + b"Content-Type: application/pdf\r\n\r\n"
        + filebytes
        + f"\r\n--{boundary}--\r\n".encode()
    )
    h = dict(headers or {})
    h["Content-Type"] = f"multipart/form-data; boundary={boundary}"
    return _req(url, method="POST", data=body, headers=h)


def banner(msg):
    print(f"\n{'='*70}\n{msg}\n{'='*70}")


async def main():
    resume = sys.argv[1] if len(sys.argv) > 1 else DEFAULT_RESUME
    if not os.path.isfile(resume):
        print(f"Resume not found: {resume}")
        sys.exit(1)

    banner("STEP 1 — HR creates a job")
    from urllib.parse import urlencode
    q = urlencode({"title": JOB["title"], "department": JOB["department"],
                   "job_description": JOB["job_description"], "llm_prompt": JOB["llm_prompt"]})
    job = _req(f"{BACKEND}/jobs?{q}", method="POST", headers=admin_headers())
    job_id = job["id"]
    print(f"  created job #{job_id}: {job['title']}")

    banner("STEP 2 — Candidate applies (resume upload) + 3-tier scoring")
    up = post_multipart_pdf(f"{BACKEND}/upload?job_id={job_id}", resume, headers=admin_headers())
    cand_id = up["id"]
    token = up["interview_token"]
    print(f"  uploaded '{os.path.basename(resume)}' -> candidate #{cand_id} ({up['status']})")
    print("  waiting for scoring...")
    status = None
    for _ in range(30):
        await asyncio.sleep(3)
        c = _req(f"{BACKEND}/candidates/{cand_id}", headers=admin_headers())
        status = c.get("status")
        if status in ("Shortlisted", "Reviewed", "Rejected", "Ungraded", "Error"):
            print(f"  scored: status={status} "
                  f"tier1={c.get('tier1')} tier2={c.get('tier2')} tier3={c.get('tier3')} total={c.get('total_score')}")
            break
    else:
        print("  (scoring did not finish in time; continuing anyway)")

    banner("STEP 3 — Spawn interview bot from the candidate's link")
    v = _req(f"{VOICE}/interview/validate?token={token}")
    if not v.get("valid"):
        print(f"  validate failed: {v}")
        sys.exit(1)
    session_id = v["session_id"]
    print(f"  bot ready in room {v['room_name']} (session {session_id})")

    banner("STEP 4 — Candidate joins + chat/audio interview (real LLM + TTS + judge)")
    room = rtc.Room()
    await room.connect(v["livekit_url"], v["livekit_token"])
    print("  joined LiveKit room; letting the bot greet...")
    await asyncio.sleep(8)
    for i, m in enumerate(CANDIDATE_MESSAGES, 1):
        _req(f"{VOICE}/chat", method="POST",
             data=json.dumps({"text": m, "session": session_id}).encode(),
             headers={"Content-Type": "application/json"})
        print(f"  [{i}/{len(CANDIDATE_MESSAGES)}] candidate: {m[:60]}...")
        await asyncio.sleep(10)

    banner("STEP 5 — Candidate leaves -> finalize (audio + tokens + assessment)")
    await room.disconnect()
    print("  disconnected; finalizing...")
    await asyncio.sleep(16)

    banner("STEP 6 — FULL EVALUATION (what HR sees)")
    d = _req(f"{BACKEND}/candidates/{cand_id}/interview", headers=admin_headers())
    if not d.get("has_interview"):
        print("  no interview data found.")
        sys.exit(1)

    m = d["metrics"]["interview"]
    s = d["metrics"]["scoring"]
    print("\n— Token usage —")
    print(f"  Interview: STT(est) {m['stt_tokens']} | LLM in {m['llm_input_tokens']} | "
          f"LLM out {m['llm_output_tokens']} | TTS(est) {m['tts_tokens']} | TOTAL {m['total_tokens']} "
          f"| cost ${m['cost_usd']:.6f}")
    print(f"  Resume scoring: in {s['prompt_tokens']} / out {s['completion_tokens']} | cost ${s['cost_usd']:.6f}")

    print("\n— Transcript with per-message candidate evaluation —")
    for t in d["transcript"]:
        who = "BOT " if t["speaker"] == "agent" else "CAND"
        line = f"  {who}: {t['text'][:75]}"
        ev = t.get("evaluation")
        if t["speaker"] != "agent" and ev:
            line += f"\n        ↳ score {ev.get('score')}/10 · {ev.get('depth')}"
            if ev.get("strengths"):
                line += f" · 👍 {ev['strengths'][0]}"
            if ev.get("weaknesses"):
                line += f" · 👎 {ev['weaknesses'][0]}"
        print(line)

    print("\n— Goals —")
    for g in d["goals"]:
        print(f"  {g['title']}: {g['completion_status']} ({round(float(g['progress_score'] or 0)*100)}%)")

    print("\n— Final evaluation —")
    oa = d["session"].get("overall_assessment")
    try:
        j = json.loads(oa)
        ov = j.get("overall_assessment", {})
        print(f"  Hiring recommendation: {ov.get('hiring_recommendation')}")
        print(f"  Candidate performance: {round(float(ov.get('candidate_performance', 0))*100)}%")
        print(f"  Strengths: {ov.get('strengths', [])}")
        print(f"  Areas for improvement: {ov.get('areas_for_improvement', [])}")
    except Exception:
        print(f"  {oa}")

    print(f"\n  Audio recording available: {d.get('has_audio')}")
    banner("DONE")
    print(f"  Open in the dashboard: {FRONTEND}/admin/candidates/{cand_id}/interview")
    print(f"  (login token: {ADMIN_TOKEN})")
    print(f"  Job #{job_id} · Candidate #{cand_id} · Session {session_id}")


if __name__ == "__main__":
    asyncio.run(main())
