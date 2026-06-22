"""Structured extraction + evaluation for non-technical early-screening interviews.

The live screening interview (role_config_service._screening_config) gathers a fixed
set of qualifying details conversationally. This module turns the resulting transcript
into two things via a single Groq call:
  1. the hiring team's structured FACT summary (experience, salary, stack, …);
  2. an EVALUATION of the candidate — vocabulary, technical terminology, answer quality,
     and tone — judged against the job they applied for.

Called post-call from GoalTrackingProcessor.finalize_session_goals for screening
sessions; the result is attached to the persisted final analysis under
``screening_summary`` so HR reads it alongside the assessment.
"""

import os

from groq import AsyncGroq
from loguru import logger

from database import db_manager
from services.goal_tracking_service import _safe_json_loads

# Extraction is a simple structured-output task, so use the fast (8b) model: it is
# cheaper and sits under a separate, higher rate limit than the 70b conversational model.
_MODEL = os.getenv("GROQ_FAST_MODEL") or "llama-3.1-8b-instant"

# The factual fields the hiring team expects, in reporting order. Keep keys stable: the
# backend/HR surface and any report rendering read these.
_FIELDS = [
    "total_experience",          # e.g. "7 years" / "< 1 year"
    "current_salary",
    "expected_salary",
    "notice_period",
    "schedule_location_agreement",  # "Yes"/"No" + notes
    "tech_stack",                # list of technologies
    "achievements",              # summary; highlight game-related work
    "game_related",              # bool: did any achievement/experience involve games?
    "final_year_project",
    "project_choice_motivation",
    "confirmation_status",       # "Confirmed"/"Unconfirmed"
]

# Evaluation dimensions: each scored 1-5 with a one-line justification, judged against
# the job the candidate applied for.
_EVAL_DIMS = [
    "vocabulary",             # range/precision of language
    "technical_terminology",  # correct, relevant use of domain terms for the role
    "answer_quality",         # relevance, specificity, completeness of answers
    "tone",                   # professionalism, confidence, warmth
    "overall_fit",            # communication fit for THIS job overall
]

_PROMPT = """You are an HR analyst reviewing a NON-TECHNICAL screening call (transcript \
below) between an AI interviewer (agent) and a candidate who applied for the role described \
under JOB. Produce JSON with two parts: factual details, and an evaluation of the candidate.

JOB (what they applied for):
Title: {job_title}
Description: {job_description}

PART 1 — FACTS. Use ONLY what the candidate actually said; if a detail was never given, \
use "Not provided" (or [] for tech_stack, false for game_related):
- "total_experience": total years of professional experience (e.g. "5 years").
- "current_salary", "expected_salary", "notice_period": as stated.
- "schedule_location_agreement": start "Yes" or "No" (on-site Mon-Fri 10am-7pm), then any caveat.
- "tech_stack": JSON array of every language, framework, and tool named.
- "achievements": 1-2 sentence summary; if any achievement/experience involves GAMES, lead with it.
- "game_related": true if any achievement/experience involves games, else false.
- "final_year_project": their final-year/academic project.
- "project_choice_motivation": why they chose it.
- "confirmation_status": "Confirmed" if they confirmed their details, else "Unconfirmed".

PART 2 — EVALUATION. Judge the candidate from HOW they answered, relative to the JOB above. \
Return an "evaluation" object. For each dimension give an integer "score" 1-5 (1=poor, 5=excellent) \
and a one-line "comment" citing evidence from the transcript:
- "vocabulary": range and precision of their language.
- "technical_terminology": correct, relevant use of domain/technical terms for this role.
- "answer_quality": relevance, specificity, and completeness of their answers.
- "tone": professionalism, confidence, and warmth.
- "overall_fit": overall communication fit for THIS job.
Also include "recommendation": one of "Proceed", "Hold", or "Reject", and "evaluation_summary": \
a one-sentence rationale. Score honestly and use the FULL 1-5 range — a junior with vague, \
non-technical answers should score lower than a senior who uses precise domain terms. Base \
every score and comment ONLY on THIS candidate's actual words; do not reuse the template text. \
Every dimension MUST have a non-empty "comment" citing specific evidence from the transcript. \
Use this SHAPE (fill the placeholders with your own assessment of this candidate):
{{"vocabulary": {{"score": <1-5 integer>, "comment": "<evidence from transcript>"}}, \
"technical_terminology": {{"score": <1-5 integer>, "comment": "<evidence>"}}, \
"answer_quality": {{"score": <1-5 integer>, "comment": "<evidence>"}}, \
"tone": {{"score": <1-5 integer>, "comment": "<evidence>"}}, \
"overall_fit": {{"score": <1-5 integer>, "comment": "<evidence>"}}, \
"recommendation": "<Proceed|Hold|Reject>", "evaluation_summary": "<one sentence>"}}

TRANSCRIPT:
{transcript}

Output ONE flat JSON object: put ALL the factual keys (total_experience, current_salary, \
…, confirmation_status) at the TOP LEVEL — do NOT nest them under any wrapper — plus one \
nested "evaluation" object. JSON only."""


def _render_transcript(turns: list[dict]) -> str:
    lines = []
    for t in turns:
        who = "Interviewer" if t.get("speaker") == "agent" else "Candidate"
        text = (t.get("text") or "").strip()
        if text:
            lines.append(f"{who}: {text}")
    return "\n".join(lines)


def _empty_evaluation() -> dict:
    ev = {d: {"score": None, "comment": "Not assessed"} for d in _EVAL_DIMS}
    ev["recommendation"] = "Not assessed"
    ev["evaluation_summary"] = "Not assessed"
    return ev


def _empty_summary(reason: str) -> dict:
    out = {f: ("Not provided" if f not in ("tech_stack", "game_related") else ([] if f == "tech_stack" else False))
           for f in _FIELDS}
    out["evaluation"] = _empty_evaluation()
    out["_note"] = reason
    return out


async def _fetch_job_context(session_id: str) -> tuple[str, str]:
    """Return (job_title, job_description) for the session's candidate, for evaluation
    context. Best-effort: returns generic placeholders if the lookup fails."""
    try:
        row = await db_manager.fetch_one(
            "SELECT j.title AS title, j.job_description AS jd "
            "FROM interview_sessions s "
            "JOIN candidates c ON c.id = s.candidate_id "
            "JOIN jobs j ON j.id = c.job_id "
            "WHERE s.session_id = $1",
            session_id,
        )
    except Exception as e:  # noqa: BLE001
        logger.warning(f"[Screening] job context lookup failed for {session_id}: {e}")
        row = None
    if not row:
        return "the role they applied for", "(no job description available)"
    return (row.get("title") or "the role they applied for",
            (row.get("jd") or "(no job description available)")[:1500])


async def extract_screening_summary(session_id: str) -> dict:
    """Read a screening session's transcript and return the structured summary +
    evaluation dict.

    Never raises: on any failure returns an empty summary with a "_note" explaining why,
    so finalization persists a record rather than crashing.
    """
    try:
        turns = await db_manager.get_transcript(session_id)
    except Exception as e:  # noqa: BLE001
        logger.error(f"[Screening] transcript read failed for {session_id}: {e}")
        return _empty_summary(f"transcript read failed: {e}")

    rendered = _render_transcript(turns)
    if not rendered:
        return _empty_summary("empty transcript")

    api_key = os.getenv("GROQ_API_KEY")
    if not api_key:
        return _empty_summary("GROQ_API_KEY not set")

    job_title, job_description = await _fetch_job_context(session_id)

    try:
        client = AsyncGroq(api_key=api_key)
        resp = await client.chat.completions.create(
            model=_MODEL,
            messages=[{"role": "user", "content": _PROMPT.format(
                job_title=job_title, job_description=job_description,
                transcript=rendered[:8000])}],
            temperature=0.1,
            max_tokens=1200,
            response_format={"type": "json_object"},
        )
        data = _safe_json_loads(resp.choices[0].message.content)
    except Exception as e:  # noqa: BLE001
        logger.error(f"[Screening] extraction LLM call failed for {session_id}: {e}")
        return _empty_summary(f"extraction failed: {e}")

    # The model sometimes returns a JSON array instead of an object — and often SPLITS
    # the response across elements (e.g. [{facts…}, {"evaluation": …}]). Merge every
    # dict element so neither the facts nor the evaluation half is dropped (taking only
    # the first element silently lost the evaluation).
    if isinstance(data, list):
        merged: dict = {}
        for x in data:
            if isinstance(x, dict):
                merged.update(x)
        data = merged
    if not isinstance(data, dict):
        return _empty_summary("extraction returned non-object JSON")

    # The model occasionally nests the facts under a wrapper (e.g. "facts"/"part_1")
    # despite being told to keep them flat — recover by merging in any nested dict that
    # actually carries the fact keys.
    facts = data
    if "total_experience" not in facts:
        for v in data.values():
            if isinstance(v, dict) and "total_experience" in v:
                facts = {**data, **v}
                break

    # Normalize facts: guarantee every expected key exists and types are sane.
    summary = _empty_summary("")
    summary.pop("_note", None)
    for f in _FIELDS:
        if f in facts and facts[f] not in (None, ""):
            summary[f] = facts[f]
    if not isinstance(summary.get("tech_stack"), list):
        summary["tech_stack"] = [s.strip() for s in str(summary["tech_stack"]).split(",") if s.strip()]
    summary["game_related"] = bool(summary.get("game_related"))

    # Normalize evaluation: keep only known dimensions, coerce scores to 1-5 ints.
    # The model is inconsistent about where it puts the evaluation: usually under an
    # "evaluation" object, but sometimes it flattens the dimensions (and the
    # recommendation/summary) to the TOP LEVEL alongside the facts. Build a single
    # lookup that checks the nested object first, then falls back to the top level, so
    # the scores are captured whichever shape the model chose this call.
    ev_in = data.get("evaluation") if isinstance(data.get("evaluation"), dict) else facts.get("evaluation", {})
    if not isinstance(ev_in, dict):
        ev_in = {}

    def _ev_lookup(key):
        if key in ev_in:
            return ev_in[key]
        if key in data:
            return data[key]
        return facts.get(key)

    evaluation = _empty_evaluation()
    for d in _EVAL_DIMS:
        cell = _ev_lookup(d)
        score, comment = None, ""
        if isinstance(cell, dict):          # {"score": 4, "comment": "..."}
            score, comment = cell.get("score"), cell.get("comment", "")
        elif isinstance(cell, (int, float)):  # bare 4
            score = cell
        elif isinstance(cell, str):          # "4" or a comment
            comment = cell
        try:
            score = max(1, min(5, int(score)))
        except (TypeError, ValueError):
            score = None
        if score is not None or comment:
            evaluation[d] = {"score": score, "comment": str(comment).strip() or "—"}
    # recommendation/evaluation_summary follow the same nested-or-flat ambiguity.
    rec = _ev_lookup("recommendation")
    if rec:
        evaluation["recommendation"] = str(rec).strip()
    summ = _ev_lookup("evaluation_summary")
    if summ:
        evaluation["evaluation_summary"] = str(summ).strip()
    summary["evaluation"] = evaluation

    logger.info(
        f"[Screening] summary for {session_id}: exp={summary['total_experience']!r} "
        f"stack={len(summary['tech_stack'])} game={summary['game_related']} "
        f"rec={evaluation['recommendation']!r}"
    )
    return summary
