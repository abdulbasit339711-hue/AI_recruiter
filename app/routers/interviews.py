import json
import logging
import os
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from fastapi.responses import FileResponse, PlainTextResponse, StreamingResponse
from sqlalchemy import text
from sqlalchemy.orm import Session

from ..core.auth import token_is_valid
from ..core.utils import _utcnow
from ..database import get_db
from ..models import Candidate, Job

logger = logging.getLogger(__name__)

router = APIRouter()

_FILLER_WORDS = ("um", "uh", "uhh", "umm", "hmm", "erm", "er", "ah", "like", "you know")


def _recordings_dir() -> str:
    return os.getenv("RECORDINGS_DIR", "/mnt/muaaz/AI_recruiter/data/recordings")


def _safe_path(path: str) -> Optional[str]:
    """Return path only if it resolves within RECORDINGS_DIR; prevents path traversal."""
    root = os.path.realpath(_recordings_dir())
    resolved = os.path.realpath(path)
    if resolved.startswith(root + os.sep) or resolved == root:
        return path
    logger.warning("Path traversal attempt blocked: %s", path)
    return None


def _session_media(session_id: str) -> dict:
    """Resolve a session's on-disk media by the ``{session_id}.{ext}`` naming
    convention the voice agent uses. We deliberately do NOT rely on the
    interview_sessions.audio_path column — it is frequently empty even when the
    files exist on disk, which previously hid the recording from HR."""
    d = _recordings_dir()
    paths = {
        "audio": _safe_path(os.path.join(d, f"{session_id}.wav")),
        "video": _safe_path(os.path.join(d, f"{session_id}.mp4")),
        "annotated": _safe_path(os.path.join(d, f"{session_id}.annotated.mp4")),
        "vision": _safe_path(os.path.join(d, f"{session_id}.vision.json")),
        "comm": _safe_path(os.path.join(d, f"{session_id}.comm.json")),
    }
    return {k: (v if v and os.path.isfile(v) else None) for k, v in paths.items()}


def _vision_overall_summary(aggregate: dict, observations: list) -> str:
    """Synthesize a video-LEVEL narrative from the per-frame observations.

    The VLM emits one caption per sampled frame ("a person at a desk…"); on their
    own those are just image descriptions. This rolls them up into a few sentences
    describing the candidate's on-camera presentation across the whole interview."""
    agg = aggregate or {}
    obs = observations or []
    n = agg.get("frames_analyzed") or len(obs)
    if not n:
        return ""
    parts: list[str] = []

    present = agg.get("present_ratio")
    if present is not None:
        pct = round(present * 100)
        if pct >= 90:
            parts.append("The candidate was on camera for essentially the entire interview")
        elif pct >= 60:
            parts.append(f"The candidate was visible for about {pct}% of the interview")
        else:
            parts.append(f"The candidate was visible for only about {pct}% of the interview (frequently off-camera)")

    eng = agg.get("avg_engagement")
    if eng is not None:
        # engagement is reported 0–5 by the VLM
        if eng >= 3.5:
            desc = "high, sustained attentiveness"
        elif eng >= 2:
            desc = "moderate attentiveness"
        else:
            desc = "low or inconsistent attentiveness"
        parts.append(f"showing {desc} (avg {eng}/5)")

    looking_away = sum(1 for o in obs if o.get("looking_away"))
    if obs and looking_away:
        parts.append(f"appeared to look off-screen in {looking_away} of {len(obs)} sampled moments")

    # Distinct delivery notes, de-duplicated, as a flavour of how they presented.
    notes = []
    seen = set()
    for o in obs:
        dn = (o.get("delivery_notes") or "").strip().rstrip(".")
        key = dn.lower()
        if dn and key not in seen:
            seen.add(key)
            notes.append(dn)
    summary = ". ".join(p for p in [", ".join(parts[:1] + parts[1:])] if p)
    if summary:
        summary += "."
    if notes:
        summary += " Delivery cues observed: " + "; ".join(notes[:5]) + "."

    flags = agg.get("integrity_flags") or []
    if flags:
        labels = {"candidate_absent": "candidate absent at times",
                  "phone_visible": "a phone was visible", "multiple_people": "more than one person seen"}
        summary += " Integrity notes: " + ", ".join(labels.get(f, f) for f in flags) + "."
    return summary.strip()


def _vision_data_quality(aggregate: dict) -> dict:
    """Gate the subjective video read on how much usable footage we actually had.
    Prevents a confident-sounding summary built on 2 frames of an off-camera candidate."""
    agg = aggregate or {}
    frames = agg.get("frames_analyzed") or 0
    present = agg.get("present_ratio")
    present = present if present is not None else 0.0
    if frames < 2 or present < 0.25:
        level, note = "insufficient", "Too little on-camera footage to assess delivery reliably."
    elif frames < 4 or present < 0.6:
        level, note = "limited", "Limited on-camera footage — read delivery cues with caution."
    else:
        level, note = "good", "Sufficient on-camera footage for an advisory read."
    return {"level": level, "note": note, "frames_analyzed": frames,
            "present_ratio": round(present, 2)}


def _speaking_metrics(transcript, session: dict) -> dict:
    """Objective communication signals from the transcript + session duration:
    talk-time balance (candidate vs interviewer) and an approximate speaking pace."""
    import re as _re

    def _words(s: str) -> int:
        return len(_re.findall(r"[A-Za-z0-9']+", s or ""))

    cand_turns = [t for t in transcript if t.get("speaker") == "candidate"]
    agent_turns = [t for t in transcript if t.get("speaker") == "agent"]
    cand_words = sum(_words(t.get("text", "")) for t in cand_turns)
    agent_words = sum(_words(t.get("text", "")) for t in agent_turns)
    total = cand_words + agent_words

    duration_s = None
    started, ended = session.get("started_at"), session.get("ended_at")
    if started and ended:
        try:
            duration_s = max(0.0, (ended - started).total_seconds())
        except Exception:
            duration_s = None

    # Approximate pace over the whole interview (not just speaking time), clearly labelled.
    wpm = round(cand_words / (duration_s / 60), 1) if duration_s and duration_s > 0 else None
    return {
        "candidate_words": cand_words,
        "interviewer_words": agent_words,
        "candidate_talk_ratio_pct": round(100 * cand_words / total, 1) if total else 0.0,
        "candidate_turns": len(cand_turns),
        "interviewer_turns": len(agent_turns),
        "avg_words_per_answer": round(cand_words / len(cand_turns), 1) if cand_turns else 0.0,
        "duration_seconds": round(duration_s) if duration_s is not None else None,
        "approx_words_per_min": wpm,
    }


def _latest_session_id(db: Session, candidate_id: int):
    from sqlalchemy import text
    return db.execute(text(
        "SELECT session_id FROM interview_sessions WHERE candidate_id = :cid "
        "ORDER BY created_at DESC LIMIT 1"
    ), {"cid": candidate_id}).scalar()


def _count_fillers(turns) -> dict:
    """Deterministic filler-word tally over the candidate's transcript turns
    (Deepgram filler_words=true surfaces um/uh/hmm in the text)."""
    import re as _re
    total_words = 0
    counts = {f: 0 for f in _FILLER_WORDS}
    for t in turns:
        if t.get("speaker") != "candidate":
            continue
        words = _re.findall(r"[a-zA-Z']+", (t.get("text") or "").lower())
        total_words += len(words)
        for w in words:
            if w in counts:
                counts[w] += 1
    used = {k: v for k, v in counts.items() if v}
    n_fillers = sum(used.values())
    return {
        "total_words": total_words,
        "filler_count": n_fillers,
        "filler_rate_pct": round(100 * n_fillers / total_words, 1) if total_words else 0.0,
        "by_filler": used,
    }


def _build_candidate_report_md(candidate: Candidate, job_title: str, interview: dict) -> str:
    """Assemble a single Markdown report: résumé tier scores + AI-interview assessment +
    transcript. Reuses the candidate record and the get_candidate_interview payload."""
    def _parse(x):
        if isinstance(x, (dict, list)):
            return x
        try:
            return json.loads(x) if x else None
        except (TypeError, ValueError):
            return None

    name = candidate.name or candidate.filename or f"Candidate {candidate.id}"
    L = [
        f"# Candidate Report — {name}",
        "",
        f"- **Job:** {job_title}",
        f"- **Email:** {candidate.email or 'n/a'}",
        f"- **Status:** {candidate.status}",
        "",
        "## Résumé score",
        f"- Tier 1 (profile rules): {candidate.tier1}/30",
        f"- Tier 2 (semantic match): {candidate.tier2}/40",
        f"- Tier 3 (LLM evaluation): {candidate.tier3}/30",
        f"- **Total: {candidate.total_score}/100**",
    ]
    if candidate.summary:
        L += ["", "### Summary", candidate.summary]
    ev = _parse(candidate.evidence)
    if ev:
        L += ["", "### Evidence"]
        L += [f"- {e if isinstance(e, str) else json.dumps(e)}" for e in (ev if isinstance(ev, list) else [ev])]

    # Candidate profile extracted during scoring (role, companies, experience, skills, IQ).
    companies = _parse(candidate.companies) or []
    matched = _parse(candidate.skills_matched) or []
    missing = _parse(candidate.skills_missing) or []
    profile = []
    if candidate.current_role:
        profile.append(f"- **Current role:** {candidate.current_role}")
    if candidate.years_experience is not None:
        profile.append(f"- **Experience:** {candidate.years_experience} years")
    if companies:
        profile.append("- **Companies:** " + ", ".join(str(c) for c in companies))
    if matched:
        profile.append("- **Matched skills:** " + ", ".join(str(s) for s in matched))
    if missing:
        profile.append("- **Missing skills:** " + ", ".join(str(s) for s in missing))
    if candidate.iq_score is not None:
        iq = f"- **Aptitude (IQ) screen:** {round(candidate.iq_score)}%"
        if candidate.iq_total:
            iq += f" ({candidate.iq_correct}/{candidate.iq_total}"
            iq += f", {candidate.iq_time_seconds}s)" if candidate.iq_time_seconds is not None else ")"
        profile.append(iq)
    if profile:
        L += ["", "## Profile"] + profile

    L += ["", "## AI interview"]
    if not interview.get("has_interview"):
        L.append("_No interview conducted yet._")
    else:
        sess = interview.get("session") or {}
        L += [f"- Role: {sess.get('role_type')}", f"- Status: {sess.get('status')}"]
        oa = _parse(sess.get("overall_assessment"))
        ov = (oa or {}).get("overall_assessment") if isinstance(oa, dict) else None
        fr = (oa or {}).get("final_ai_recommendation") if isinstance(oa, dict) else None
        if isinstance(fr, dict):
            if fr.get("decision"):
                L.append(f"- **AI Recommendation: {fr['decision']}**")
            if fr.get("overall_candidate_score") is not None:
                L.append(f"- Overall Candidate Score: {fr['overall_candidate_score']}/100")
            if fr.get("job_match_percentage") is not None:
                L.append(f"- Job Match: {fr['job_match_percentage']}%")
            if fr.get("decision_rationale"):
                L.append(f"- Rationale: {fr['decision_rationale']}")
            for label, key in (("Key Strengths", "key_strengths"), ("Development Areas", "development_areas")):
                vals = fr.get(key) or []
                if vals:
                    L.append(f"- {label}: " + "; ".join(str(v) for v in vals))
        elif isinstance(ov, dict):
            if ov.get("hiring_recommendation"):
                L.append(f"- **AI Recommendation: {ov['hiring_recommendation']}**")
            if ov.get("overall_candidate_score") is not None:
                L.append(f"- Overall Candidate Score: {ov['overall_candidate_score']}/100")
            if ov.get("job_match_percentage") is not None:
                L.append(f"- Job Match: {ov['job_match_percentage']}%")
            for label, key in (("Strengths", "strengths"), ("Areas for improvement", "areas_for_improvement")):
                vals = ov.get(key) or []
                if vals:
                    L.append(f"- {label}: " + "; ".join(str(v) for v in vals))
        L.append(f"- Recording: {'available' if interview.get('has_audio') else 'none'}")
        transcript = interview.get("transcript") or []
        if transcript:
            L += ["", "### Transcript"]
            for t in transcript:
                who = "Interviewer" if t.get("speaker") == "agent" else "Candidate"
                L.append(f"- **{who}:** {t.get('text')}")
    return "\n".join(L)


def _markdown_to_pdf_bytes(md: str, title: str) -> bytes:
    """Render the report Markdown to a simple PDF via reportlab (headings + bullets)."""
    import io, re, html
    from reportlab.lib.pagesizes import LETTER
    from reportlab.lib.styles import getSampleStyleSheet
    from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer

    buf = io.BytesIO()
    doc = SimpleDocTemplate(buf, pagesize=LETTER, title=title)
    styles = getSampleStyleSheet()
    flow = []
    for raw in md.split("\n"):
        line = raw.rstrip()
        if not line:
            flow.append(Spacer(1, 6))
            continue
        if line.startswith("### "):
            style, line = styles["Heading3"], line[4:]
        elif line.startswith("## "):
            style, line = styles["Heading2"], line[3:]
        elif line.startswith("# "):
            style, line = styles["Title"], line[2:]
        else:
            style = styles["BodyText"]
        text = html.escape(line.lstrip("- ") if line.startswith("- ") else line)
        text = re.sub(r"\*\*(.+?)\*\*", r"<b>\1</b>", text)
        if raw.startswith("- "):
            text = "• " + text
        flow.append(Paragraph(text, style))
    doc.build(flow)
    return buf.getvalue()


def _norm_goal(g) -> dict:
    """Flatten a goal row into {title, status, scores, questions[], evidence[{text}]}.
    question_templates / evidence are jsonb whose items may be plain strings or dicts."""
    d = dict(g)
    qt = d.pop("question_templates", None) or []
    d["questions"] = [
        (q if isinstance(q, str) else (q.get("text") or q.get("question") or "")).strip()
        for q in (qt if isinstance(qt, list) else [])
    ]
    d["questions"] = [q for q in d["questions"] if q]
    ev = d.get("evidence") or []
    d["evidence"] = [
        {"text": (e if isinstance(e, str)
                  else (e.get("text") or e.get("quote") or e.get("evidence_text") or "")).strip()}
        for e in (ev if isinstance(ev, list) else [])
    ]
    d["evidence"] = [e for e in d["evidence"] if e["text"]]
    return d


@router.get("/candidates/{candidate_id}/interview")
def get_candidate_interview(candidate_id: int, db: Session = Depends(get_db)):
    """Return the candidate's AI interview results (transcript + goals + assessment).

    Reads the voice agent's tables, which live in the same PostgreSQL database.
    """
    from sqlalchemy import text

    # Per-candidate resume-scoring (Tier 3) token usage + cost, captured at scoring time.
    cand = db.query(Candidate).filter(Candidate.id == candidate_id).first()
    scoring_metrics = {
        "prompt_tokens": (cand.llm_prompt_tokens or 0) if cand else 0,
        "completion_tokens": (cand.llm_completion_tokens or 0) if cand else 0,
        "cost_usd": round(float(cand.llm_cost_usd or 0.0), 6) if cand else 0.0,
    }

    sess = db.execute(text(
        "SELECT session_id, role_type, status, started_at, ended_at, total_goals, "
        "completed_goals, average_progress, overall_assessment, audio_path "
        "FROM interview_sessions WHERE candidate_id = :cid "
        "ORDER BY created_at DESC LIMIT 1"
    ), {"cid": candidate_id}).mappings().first()
    if not sess:
        return {
            "has_interview": False,
            "metrics": {
                "interview": {
                    "stt_tokens": 0, "llm_input_tokens": 0, "llm_output_tokens": 0,
                    "tts_tokens": 0, "total_tokens": 0, "cost_usd": 0.0,
                },
                "scoring": scoring_metrics,
            },
        }

    sid = sess["session_id"]
    transcript = db.execute(text(
        "SELECT speaker, text, sequence_number, evaluation FROM session_transcripts "
        "WHERE session_id = :sid ORDER BY sequence_number"
    ), {"sid": sid}).mappings().all()
    # Include each goal's planned questions (goal_templates.question_templates) and the
    # candidate-answer evidence gathered for it (session_goals.evidence), so HR can see
    # the goal-related questions and the candidate's answers alongside the goal score.
    goals = db.execute(text(
        "SELECT gt.title, sg.completion_status, sg.progress_score, sg.confidence_level, "
        "gt.question_templates, sg.evidence "
        "FROM session_goals sg JOIN goal_templates gt ON sg.goal_template_id = gt.id "
        "WHERE sg.session_id = :sid ORDER BY gt.priority_weight DESC"
    ), {"sid": sid}).mappings().all()

    # Aggregate the interview token usage by service/type (LLM in/out, TTS) from
    # session_metrics; cost is only the real LLM cost (goal_analysis rows carry a
    # placeholder cost and are excluded).
    by_type = db.execute(text(
        "SELECT metric_type, COALESCE(SUM(token_count), 0) AS tokens, "
        "COALESCE(SUM(cost_usd), 0) AS cost "
        "FROM session_metrics WHERE session_id = :sid GROUP BY metric_type"
    ), {"sid": sid}).mappings().all()
    tok = {r["metric_type"]: int(r["tokens"]) for r in by_type}
    cost_by = {r["metric_type"]: float(r["cost"]) for r in by_type}
    interview_cost = round(cost_by.get("llm_input", 0.0) + cost_by.get("llm_output", 0.0), 6)
    # STT tokens come from the candidate transcript word counts (the metrics processor
    # sits after the user-aggregator and never sees the raw transcription frames).
    stt_t = int(db.execute(text(
        "SELECT COALESCE(SUM(tokens_estimated), 0) FROM session_transcripts "
        "WHERE session_id = :sid AND speaker = 'candidate'"
    ), {"sid": sid}).scalar() or 0)
    llm_in = tok.get("llm_input", 0)
    llm_out = tok.get("llm_output", 0)
    tts_t = tok.get("tts_tokens", 0)
    interview_metrics = {
        "stt_tokens": stt_t,
        "llm_input_tokens": llm_in,
        "llm_output_tokens": llm_out,
        "tts_tokens": tts_t,
        "total_tokens": stt_t + llm_in + llm_out + tts_t,
        "cost_usd": interview_cost,
    }

    session_dict = dict(sess)
    db_audio = session_dict.pop("audio_path", None)
    # Resolve media from disk by session_id (audio_path is often empty).
    media = _session_media(sid)
    has_audio = bool(db_audio) or media["audio"] is not None

    # Advisory video-evaluation report (semantic VLM observations + local YOLO
    # proctoring detections), written as a sidecar JSON by the voice agent.
    vision_report = None
    if media["vision"]:
        try:
            import json as _json
            with open(media["vision"]) as _vf:
                _vj = _json.load(_vf)
            _agg = _vj.get("aggregate", {})
            _obs = _vj.get("observations", [])
            _quality = _vision_data_quality(_agg)
            vision_report = {
                "backend": _vj.get("semantic_backend"),
                "advisory_only": _vj.get("advisory_only", True),
                "data_quality": _quality,
                "aggregate": _agg,
                # Suppress the subjective narrative when there isn't enough footage to back it.
                "overall_summary": (_vision_overall_summary(_agg, _obs)
                                    if _quality["level"] != "insufficient" else ""),
                "observations": _obs,
                "detections": _vj.get("detections", []),
            }
        except Exception:
            vision_report = None

    oa = session_dict.get("overall_assessment")
    _oa_parsed = None
    if oa:
        try:
            import json as _j
            _oa_parsed = _j.loads(oa) if isinstance(oa, str) else oa
        except Exception:
            pass
    phase1_score = (_oa_parsed or {}).get("phase1_score") if isinstance(_oa_parsed, dict) else None
    current_phase = (_oa_parsed or {}).get("current_phase") if isinstance(_oa_parsed, dict) else None

    session_dict["phase1_score"] = phase1_score
    session_dict["current_phase"] = current_phase

    return {
        "has_interview": True,
        "has_audio": has_audio,
        "has_video": media["video"] is not None,
        "has_annotated_video": media["annotated"] is not None,
        "has_communication": media["comm"] is not None,
        "vision": vision_report,
        "speaking": _speaking_metrics([dict(t) for t in transcript], session_dict),
        "session": session_dict,
        "transcript": [dict(t) for t in transcript],
        "goals": [_norm_goal(g) for g in goals],
        "metrics": {
            "interview": interview_metrics,
            "scoring": scoring_metrics,
        },
    }


@router.get("/candidates/{candidate_id}/interview-audio")
def get_candidate_interview_audio(candidate_id: int, db: Session = Depends(get_db)):
    """Stream the recorded interview audio (merged WAV) for HR playback.

    The voice agent writes recordings to RECORDINGS_DIR and stores the path on the
    interview_sessions row; this serves that file back through the admin proxy.
    """
    from sqlalchemy import text

    audio_path = db.execute(text(
        "SELECT audio_path FROM interview_sessions WHERE candidate_id = :cid "
        "ORDER BY created_at DESC LIMIT 1"
    ), {"cid": candidate_id}).scalar()

    # Clamp the DB-stored path to RECORDINGS_DIR to prevent path traversal if
    # a stored audio_path ever points outside the expected directory.
    if audio_path:
        audio_path = _safe_path(audio_path)

    # Fall back to the session_id-derived path on disk (audio_path is often empty).
    if not audio_path or not os.path.isfile(audio_path):
        sid = _latest_session_id(db, candidate_id)
        audio_path = _session_media(sid)["audio"] if sid else None

    if not audio_path or not os.path.isfile(audio_path):
        raise HTTPException(status_code=404, detail="Interview audio not found.")

    return FileResponse(audio_path, media_type="audio/wav", filename=os.path.basename(audio_path))


@router.get("/candidates/{candidate_id}/interview-video")
def get_candidate_interview_video(
    candidate_id: int, annotated: bool = False, db: Session = Depends(get_db)
):
    """Stream the recorded interview video for HR playback.

    ``annotated=true`` serves the YOLO-annotated copy (bounding boxes over the
    candidate / detected objects) if it has been generated; otherwise the raw
    muxed MP4. Files are resolved by session_id from RECORDINGS_DIR.
    """
    sid = _latest_session_id(db, candidate_id)
    if not sid:
        raise HTTPException(status_code=404, detail="No interview for this candidate.")
    media = _session_media(sid)
    path = media["annotated"] if annotated else media["video"]
    if not path:
        raise HTTPException(
            status_code=404,
            detail="Annotated video not generated yet." if annotated else "Interview video not found.",
        )
    return FileResponse(path, media_type="video/mp4", filename=os.path.basename(path))


@router.post("/candidates/{candidate_id}/annotate-video")
def annotate_candidate_video(candidate_id: int, db: Session = Depends(get_db)):
    """Kick off offline YOLO annotation of the recorded interview video.

    Runs the annotator under the conda python that has ultralytics/supervision/cv2
    (the voice uv venv does not). Returns immediately; the annotated MP4 appears as
    ``{session_id}.annotated.mp4`` and is then served via interview-video?annotated=true.
    """
    import subprocess

    sid = _latest_session_id(db, candidate_id)
    if not sid:
        raise HTTPException(status_code=404, detail="No interview for this candidate.")
    media = _session_media(sid)
    if not media["video"]:
        raise HTTPException(status_code=404, detail="No interview video to annotate.")
    if media["annotated"]:
        return {"status": "ready", "session_id": sid, "already": True}

    script = os.path.join(
        os.path.dirname(os.path.dirname(os.path.dirname(__file__))),
        "voice-agent", "server", "scripts", "annotate_video.py",
    )
    py = os.getenv("DETECTOR_PYTHON", "/home/aoi/miniconda3/bin/python")
    if not os.path.isfile(script):
        raise HTTPException(status_code=500, detail="Annotator script missing.")
    try:
        # Detached background job; annotation of a few-minute clip is CPU-heavy.
        subprocess.Popen(
            [py, script, "--session", sid, "--recordings-dir", _recordings_dir()],
            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
            start_new_session=True,
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to start annotator: {e}")
    return {"status": "started", "session_id": sid}


@router.get("/candidates/{candidate_id}/communication-analysis")
def get_communication_analysis(candidate_id: int, refresh: bool = False, db: Session = Depends(get_db)):
    """Detailed delivery/communication assessment over the interview transcript:
    talking style, fluency, pace, clarity, confidence, and a language/phrasing note.

    Cached to a ``{session}.comm.json`` sidecar. NOTE: this is a TEXT analysis — it
    reads the transcript, so it characterises talking style and phrasing, not audio
    accent (true accent classification needs an audio model and is flagged as such).
    """
    from sqlalchemy import text
    import json as _json

    sid = _latest_session_id(db, candidate_id)
    if not sid:
        raise HTTPException(status_code=404, detail="No interview for this candidate.")

    cache = os.path.join(_recordings_dir(), f"{sid}.comm.json")
    if os.path.isfile(cache) and not refresh:
        try:
            with open(cache) as f:
                cached = _json.load(f)
            # Regenerate stale caches written before the content-analysis was added.
            if "content" in cached:
                return cached
        except Exception:
            pass

    turns = db.execute(text(
        "SELECT speaker, text FROM session_transcripts WHERE session_id = :sid "
        "ORDER BY sequence_number"
    ), {"sid": sid}).mappings().all()
    turns = [dict(t) for t in turns]
    cand_turns = [t for t in turns if t.get("speaker") == "candidate"]
    if not cand_turns:
        raise HTTPException(status_code=404, detail="No candidate speech to analyze.")

    fillers = _count_fillers(turns)

    # Build the transcript text for the LLM (candidate turns carry the delivery signal).
    convo = "\n".join(
        f"{'Interviewer' if t['speaker'] == 'agent' else 'Candidate'}: {t['text']}"
        for t in turns
    )[:8000]

    from app.llm.groq_client import get_groq_client, _call_groq_api
    client = get_groq_client()
    analysis = None
    content_eval = None
    if client is not None:
        system_prompt = (
            "You are an interview analyst. From the transcript, produce TWO assessments and "
            "return STRICT minified JSON with exactly two top-level keys: \"delivery\" and \"content\".\n\n"
            "\"delivery\" (HOW the candidate communicates) — object with keys: talking_style, "
            "fluency, pace, clarity, confidence, conciseness, language_phrasing, accent_note. "
            "For accent_note: you only have TEXT, so DO NOT guess a regional/national accent; "
            "comment on vocabulary/idiom/phrasing and state that audio is required for true accent "
            "assessment. Each value is one short sentence.\n\n"
            "\"content\" (WHAT the candidate said — the primary, most job-relevant signal) — object "
            "with keys: star_usage (do answers follow Situation-Task-Action-Result with a concrete, "
            "measurable result? one sentence), specificity (concrete examples vs vague generalities? "
            "one sentence), ownership (does the candidate say what THEY did, 'I' vs 'we' — note this "
            "can be cultural, don't over-penalise; one sentence), relevance (do answers address the "
            "questions asked? one sentence), red_flags (array of short strings: vagueness, evasiveness, "
            "contradictions, rambling, off-topic, negativity — empty array if none), strengths (array "
            "of short strings). Judge job-relevant substance, not accent or personality."
        )
        user_prompt = (
            f"Filler-word stats (from speech-to-text): {fillers['filler_count']} fillers across "
            f"{fillers['total_words']} words ({fillers['filler_rate_pct']}%), breakdown {fillers['by_filler']}.\n\n"
            f"Transcript:\n{convo}\n\nReturn the JSON now."
        )
        try:
            raw, _usage = _call_groq_api(client, "llama-3.3-70b-versatile", system_prompt, user_prompt)
            raw = raw.strip()
            if raw.startswith("```"):
                raw = raw.strip("`").split("\n", 1)[-1].rsplit("```", 1)[0]
            parsed = _json.loads(raw)
            analysis = parsed.get("delivery", parsed)   # tolerate flat output
            content_eval = parsed.get("content")
        except Exception as e:
            analysis = {"error": f"LLM analysis unavailable: {e}"}

    result = {
        "session_id": sid,
        "fillers": fillers,
        "analysis": analysis,
        "content": content_eval,
        "candidate_turns": len(cand_turns),
    }
    try:
        with open(cache, "w") as f:
            _json.dump(result, f, indent=2)
    except Exception:
        pass
    return result


@router.get("/candidates/{candidate_id}/report")
def candidate_report(candidate_id: int, format: str = Query("md", pattern="^(md|pdf)$"),
                     db: Session = Depends(get_db)):
    """One-click report combining the résumé score and the AI-interview assessment."""
    candidate = db.query(Candidate).filter(Candidate.id == candidate_id).first()
    if not candidate:
        raise HTTPException(status_code=404, detail="Candidate not found.")
    job = db.query(Job).filter(Job.id == candidate.job_id).first()
    interview = get_candidate_interview(candidate_id, db)  # reuse the existing assembler
    md = _build_candidate_report_md(candidate, job.title if job else "n/a", interview)
    stem = f"candidate_{candidate_id}_report"
    if format == "pdf":
        try:
            pdf = _markdown_to_pdf_bytes(md, title=stem)
        except ImportError:
            raise HTTPException(status_code=501, detail="PDF export requires reportlab (pip install reportlab).")
        import io
        return StreamingResponse(
            io.BytesIO(pdf), media_type="application/pdf",
            headers={"Content-Disposition": f'attachment; filename="{stem}.pdf"'},
        )
    return PlainTextResponse(
        md, headers={"Content-Disposition": f'attachment; filename="{stem}.md"'}
    )


@router.post("/candidates/{candidate_id}/interview-invite")
def send_interview_invite_api(candidate_id: int, db: Session = Depends(get_db)):
    """HR action: (re)send the time-limited AI-interview link to a candidate."""
    cand = db.query(Candidate).filter(Candidate.id == candidate_id).first()
    if not cand:
        raise HTTPException(status_code=404, detail="Candidate not found.")
    if not cand.email:
        raise HTTPException(status_code=400, detail="Candidate has no email address.")
    job = db.query(Job).filter(Job.id == cand.job_id).first()
    if not job:
        raise HTTPException(status_code=404, detail="Candidate is not linked to a job.")
    from ..services.interview_invite import invite_candidate
    url = invite_candidate(db, cand, job, force=True)
    return {"status": "sent", "candidate_id": candidate_id, "link": url}


@router.post("/candidates/{candidate_id}/availability-invite")
def send_availability_invite_api(candidate_id: int, db: Session = Depends(get_db)):
    """HR action: send (or resend) the slot-picker availability link to a candidate."""
    cand = db.query(Candidate).filter(Candidate.id == candidate_id).first()
    if not cand:
        raise HTTPException(status_code=404, detail="Candidate not found.")
    if not cand.email:
        raise HTTPException(status_code=400, detail="Candidate has no email address.")
    job = db.query(Job).filter(Job.id == cand.job_id).first()
    if not job:
        raise HTTPException(status_code=400, detail="Candidate is not linked to a job.")

    from ..availability_tokens import mint_availability_token
    from ..services.email import send_availability_invite

    _, avail_url = mint_availability_token(cand.id)
    send_availability_invite(
        to=cand.email,
        candidate_name=cand.name,
        job_title=job.title,
        link=avail_url,
        org_name=job.org.name if job.org else None,
        org_color=job.org.primary_color if job.org else "#1C99BF",
    )

    cand.availability_invited_at = _utcnow().isoformat()
    db.commit()
    db.refresh(cand)
    return {"status": "sent", "candidate_id": candidate_id, "link": avail_url}


@router.post("/candidates/{candidate_id}/interview-result")
def record_interview_result(
    candidate_id: int,
    body: dict,
    request: Request,
    db: Session = Depends(get_db),
):
    """Internal — called by the voice agent after a session ends to store interview scores.

    Expected body keys (all optional):
        phase1_score    float   behavioral phase score (0–60)
        phase2_score    float   technical phase score (0–100)
        overall_score   float   combined final score
        passed          bool    whether the candidate cleared both gates
        completed_at    str     ISO timestamp (defaults to now)
    """
    # Accept calls from the voice agent (uses the same admin token) or an internal
    # service token.  Unauthenticated callers are rejected.
    if not token_is_valid(request.headers.get("authorization")):
        raise HTTPException(status_code=403, detail="Forbidden.")
    cand = db.query(Candidate).filter(Candidate.id == candidate_id).first()
    if not cand:
        raise HTTPException(status_code=404, detail="Candidate not found.")

    cand.interview_completed_at = body.get("completed_at") or _utcnow().isoformat()
    if body.get("phase1_score") is not None:
        cand.interview_phase1_score = float(body["phase1_score"])
    if body.get("phase2_score") is not None:
        cand.interview_phase2_score = float(body["phase2_score"])
    if body.get("overall_score") is not None:
        cand.interview_overall_score = float(body["overall_score"])
    if body.get("passed") is not None:
        cand.interview_passed = bool(body["passed"])

    db.commit()
    db.refresh(cand)
    return {"status": "ok", "candidate_id": candidate_id}
