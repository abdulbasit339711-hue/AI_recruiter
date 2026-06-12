"""Build a role-specific RecruiterConfig for any job.

Strategy: TEMPLATES + LLM FALLBACK.
  1. Normalize the job into a role slug (fixes the "Backend Engineer" vs
     "backend_engineer" mismatch).
  2. If curated `goal_templates` exist for that slug, map them to goals/questions.
  3. Otherwise generate goals/questions from the job description via Groq, cache
     them back into goal_templates (so the next candidate for the same role reuses
     them), and use those.
  4. If everything fails, fall back to a small generic config.
"""

import json
import os

from loguru import logger
from groq import AsyncGroq

from database import db_manager
from interview_session import (
    RecruiterConfig,
    InterviewGoal,
    InterviewQuestion,
    AnswerDepth,
)
from bot import compose_system_prompt
from services.goal_tracking_service import _safe_json_loads
from recruiter_shared import normalize_role_type

_GEN_MODEL = "llama-3.1-8b-instant"


def _as_list(value):
    if isinstance(value, list):
        return value
    if isinstance(value, str) and value.strip():
        try:
            parsed = json.loads(value)
            return parsed if isinstance(parsed, list) else [value]
        except (json.JSONDecodeError, ValueError):
            return [value]
    return []


def _templates_to_config(templates: list[dict]) -> tuple[list[InterviewGoal], list[InterviewQuestion]]:
    goals: list[InterviewGoal] = []
    questions: list[InterviewQuestion] = []
    seen: set[str] = set()

    for t in templates:
        title = (t.get("title") or "Competency").strip()
        gid = normalize_role_type(title) or title.lower().replace(" ", "_")
        if gid in seen:  # de-dupe legacy duplicate templates
            continue
        seen.add(gid)

        goals.append(
            InterviewGoal(
                id=gid,
                label=title,
                description=t.get("description") or title,
                weight=float(t.get("priority_weight") or 0.5),
            )
        )
        criteria = _as_list(t.get("success_criteria"))
        theme = " ".join(str(c) for c in criteria)[:200]
        qs = _as_list(t.get("question_templates"))
        if not qs:
            qs = [f"Tell me about your experience relevant to {title.lower()}."]
        for i, q in enumerate(qs):
            questions.append(
                InterviewQuestion(
                    id=f"{gid}_{i}",
                    text=str(q),
                    goal_id=gid,
                    expected_depth=AnswerDepth.MEDIUM,
                    expected_theme=theme,
                )
            )

    # Normalize weights to sum ~1 so downstream scoring is comparable across roles.
    total = sum(g.weight for g in goals) or 1.0
    for g in goals:
        g.weight = round(g.weight / total, 3)
    return goals, questions


def _generic_config() -> tuple[list[InterviewGoal], list[InterviewQuestion]]:
    goals = [
        InterviewGoal(id="technical_depth", label="Technical Depth",
                      description="Depth and correctness of technical reasoning for the role", weight=0.5),
        InterviewGoal(id="communication", label="Communication",
                      description="Clear, structured communication", weight=0.3),
        InterviewGoal(id="role_fit", label="Role Fit",
                      description="Relevant experience and motivation for this role", weight=0.2),
    ]
    questions = [
        InterviewQuestion(id="q1", text="Tell me about a recent project most relevant to this role and your specific contribution.",
                          goal_id="role_fit", expected_depth=AnswerDepth.LONG, expected_theme="project contribution outcome"),
        InterviewQuestion(id="q2", text="Walk me through a technically challenging problem you solved and how you approached it.",
                          goal_id="technical_depth", expected_depth=AnswerDepth.LONG, expected_theme="problem approach solution"),
        InterviewQuestion(id="q3", text="How do you communicate trade-offs or handle disagreements with your team?",
                          goal_id="communication", expected_depth=AnswerDepth.MEDIUM, expected_theme="communication conflict"),
    ]
    return goals, questions


# ── Non-technical early-screening interview ─────────────────────────────────────
# A role-agnostic HR screening call that gathers qualifying details rather than
# probing technical depth. A job opts in via role_type='screening'. The interviewer
# asks the fixed list below one question at a time; the structured summary of the
# answers is produced post-call by services.screening_extraction.

SCREENING_ROLE_SLUG = "screening"
SCREENING_INTERVIEW_TYPE = "non-technical screening"

# Default driving instructions (the interviewer's persona + the ordered questions and
# conditional follow-ups). Used as the system-prompt guidance when a screening job has
# no custom llm_prompt, so screening works out of the box.
SCREENING_INSTRUCTIONS = (
    "You are conducting an INITIAL NON-TECHNICAL SCREENING call. Do NOT ask technical "
    "or coding questions — your job is to gather qualifying details and note the "
    "answers. Be professional, welcoming, and objective. Ask ONE question at a time and "
    "wait for the answer before moving on. If an answer is vague, gently ask a short "
    "follow-up for the exact detail (e.g. a specific number for salary, or concrete "
    "tool names for their stack).\n\n"
    "Cover these points in order, one per turn:\n"
    "1. Total years of professional experience.\n"
    "2. Current salary.\n"
    "3. Expected salary.\n"
    "4. Notice period / availability.\n"
    "5. Can they work Monday-Friday, 10:00 AM to 7:00 PM, on-site at this location?\n"
    "6. Their technical stack (note every language, framework, and tool they mention).\n"
    "7. Their key professional achievements. If any achievement or their experience is "
    "related to GAMES, explicitly ask them to tell you the details of that game work.\n"
    "8. Their final year project (what it was).\n"
    "9. Why they chose that specific project.\n"
    "10. Finally, briefly verify and confirm the key details back to them before "
    "concluding, then thank them and end the call.\n\n"
    "If the candidate has less than one year of experience, make sure you ask about "
    "their final year project."
)


def _resume_questions(candidate: dict | None) -> list[str]:
    """The candidate's Tier-3 résumé-tailored interview questions, if any."""
    if not (candidate and candidate.get("interview_questions")):
        return []
    try:
        return [q for q in json.loads(candidate["interview_questions"])
                if isinstance(q, str) and q.strip()]
    except (TypeError, ValueError):
        return []


def _candidate_briefing(candidate: dict | None) -> str:
    """Brief the interviewer with the candidate's Tier-3 résumé evaluation and the
    résumé-tailored questions, so the bot probes from the scored profile. Returns an
    empty string when the candidate has not been scored (e.g. seeded screening demos)."""
    if not candidate:
        return ""
    lines: list[str] = []
    summary = (candidate.get("summary") or "").strip()
    total = candidate.get("total_score")
    tier3 = candidate.get("tier3")
    matched = _as_list(candidate.get("skills_matched"))
    missing = _as_list(candidate.get("skills_missing"))
    if summary:
        lines.append(f"- Résumé summary: {summary}")
    if total not in (None, "", 0) or tier3 not in (None, ""):
        lines.append(f"- Résumé screening score: {total}/100 (Tier-3 LLM evaluation: {tier3}/30).")
    if matched:
        lines.append(f"- Strengths matched to the role: {', '.join(map(str, matched[:12]))}.")
    if missing:
        lines.append(f"- Potential gaps to probe: {', '.join(map(str, missing[:12]))}.")
    resume_qs = _resume_questions(candidate)
    if resume_qs:
        lines.append("- Résumé-tailored questions to weave in and probe:")
        lines.extend(f"    {i+1}. {q}" for i, q in enumerate(resume_qs))
    if not lines:
        return ""
    return (
        "\n\nCANDIDATE BRIEFING (from the résumé Tier-3 evaluation — for your awareness; "
        "use it to ask sharper, evidence-based follow-ups, but keep the conversation "
        "natural):\n" + "\n".join(lines)
    )


def _screening_config() -> tuple[list[InterviewGoal], list[InterviewQuestion]]:
    """The fixed 10-point early-screening goal/question set (role-agnostic)."""
    specs = [
        ("experience", "Total Experience", "Total years of professional experience",
         "What is your total experience in years?", "years experience total", AnswerDepth.SHORT),
        ("current_comp", "Current Compensation", "Current salary",
         "What is your current salary?", "salary current compensation", AnswerDepth.SHORT),
        ("salary_expectation", "Salary Expectations", "Expected salary",
         "What is your expected salary?", "salary expected expectation", AnswerDepth.SHORT),
        ("availability", "Availability", "Notice period before they can start",
         "What is your notice period?", "notice period availability start", AnswerDepth.SHORT),
        ("schedule_location", "Schedule & Location", "Agreement to on-site Mon-Fri 10-7 schedule",
         "Can you work Monday through Friday, 10:00 AM to 7:00 PM, on-site at this location?",
         "schedule location timing onsite", AnswerDepth.SHORT),
        ("tech_stack", "Technical Stack", "Languages, frameworks, and tools they use",
         "What is your technical stack?", "stack languages frameworks tools", AnswerDepth.MEDIUM),
        ("achievements", "Key Achievements", "Notable professional achievements (game work flagged)",
         "What are your key professional achievements?", "achievement project impact game", AnswerDepth.MEDIUM),
        ("final_year_project", "Final Year Project", "Their academic final year project",
         "What was your final year project?", "final year project academic", AnswerDepth.MEDIUM),
        ("project_motivation", "Project Motivation", "Why they chose that project",
         "Why did you choose that specific project?", "motivation reason chose project", AnswerDepth.SHORT),
        ("confirmation", "Confirmation", "Confirmation that the gathered details are accurate",
         "Can you confirm all the details you've shared are accurate?", "confirm accurate correct yes", AnswerDepth.SHORT),
    ]
    goals = [InterviewGoal(id=gid, label=label, description=desc, weight=round(1.0 / len(specs), 3))
             for gid, label, desc, _q, _t, _d in specs]
    questions = [InterviewQuestion(id=f"sq{i+1}", text=q, goal_id=gid,
                                   expected_depth=depth, expected_theme=theme)
                 for i, (gid, _label, _desc, q, theme, depth) in enumerate(specs)]
    return goals, questions


async def _generate_templates(job: dict, role_slug: str) -> list[dict]:
    """LLM fallback: derive interview goals/questions from the job description."""
    client = AsyncGroq(api_key=os.environ["GROQ_API_KEY"])
    prompt = f"""You design structured interviews. Output JSON only.

ROLE: {job.get('title')}
DEPARTMENT: {job.get('department')}
JOB DESCRIPTION:
{(job.get('job_description') or '').strip()[:2000]}

Produce 3-5 interview GOALS (competencies to assess) for this role. For each goal:
- "title": short competency name
- "description": one sentence on what a strong candidate shows
- "priority_weight": 0.0-1.0 (higher = more important)
- "success_criteria": 2-4 short strings describing a strong answer
- "questions": 1-2 specific interview questions for this goal

Return exactly: {{"goals": [{{"title": "...", "description": "...", "priority_weight": 0.0, "success_criteria": ["..."], "questions": ["..."]}}]}}"""

    resp = await client.chat.completions.create(
        model=_GEN_MODEL,
        messages=[{"role": "user", "content": prompt}],
        temperature=0.3,
        max_tokens=1200,
        response_format={"type": "json_object"},
    )
    data = _safe_json_loads(resp.choices[0].message.content)
    templates = []
    for g in (data.get("goals") or [])[:6]:
        if not g.get("title"):
            continue
        templates.append({
            "role_type": role_slug,
            "category": "general",
            "title": str(g["title"])[:200],
            "description": str(g.get("description", ""))[:1000],
            "success_criteria": _as_list(g.get("success_criteria")),
            "priority_weight": float(g.get("priority_weight", 0.5) or 0.5),
            "estimated_time_minutes": 6,
            "question_templates": _as_list(g.get("questions")),
        })
    return templates


async def build_recruiter_config(job: dict, candidate: dict | None = None) -> RecruiterConfig:
    """Assemble a role-specific RecruiterConfig for a job."""
    job_role = (job.get("title") or "this role").strip()
    company_name = (job.get("department") or "our company").strip()
    role_slug = normalize_role_type(job.get("role_type") or job_role)

    # Non-technical early-screening interview: a fixed, role-agnostic set of
    # qualifying questions. Bypasses role templates AND the résumé deep-dive — this is
    # a screening call, not a technical probe. The structured summary of the answers is
    # produced post-call (see services.screening_extraction).
    if role_slug == SCREENING_ROLE_SLUG:
        goals, questions = _screening_config()
        instructions = (job.get("llm_prompt") or "").strip() or SCREENING_INSTRUCTIONS
        logger.info(
            f"[RoleConfig] role='{job_role}' SCREENING "
            f"goals={len(goals)} questions={len(questions)} source=screening"
        )
        return RecruiterConfig(
            job_role=job_role,
            company_name=company_name,
            interview_type=SCREENING_INTERVIEW_TYPE,
            system_prompt=compose_system_prompt(
                job_role, company_name, SCREENING_INTERVIEW_TYPE, instructions)
            + _candidate_briefing(candidate),
            questions=questions,
            goals=goals,
        )

    source = "templates"
    templates = await db_manager.get_goal_templates(role_slug)
    if not templates:
        try:
            templates = await _generate_templates(job, role_slug)
            if templates:
                for t in templates:
                    try:
                        await db_manager.add_goal_template(t)
                    except Exception as e:
                        logger.warning(f"[RoleConfig] could not cache template: {e}")
                source = "llm"
        except Exception as e:
            logger.error(f"[RoleConfig] LLM fallback failed: {e}")
            templates = []

    if templates:
        goals, questions = _templates_to_config(templates)
    else:
        goals, questions = _generic_config()
        source = "generic"

    # Résumé-tailored preset questions (generated during Tier-3 scoring) — ask these
    # FIRST so the interviewer probes this candidate's specific experience before the
    # generic role questions.
    resume_qs = _resume_questions(candidate)
    if resume_qs:
        goals = [InterviewGoal(id="resume_specific", label="Résumé deep-dive",
                               description="Probe the candidate's specific résumé claims and experience.",
                               weight=0.5)] + goals
        questions = [
            InterviewQuestion(id=f"rq{i+1}", text=q, goal_id="resume_specific",
                              expected_depth=AnswerDepth.MEDIUM, expected_theme="resume experience")
            for i, q in enumerate(resume_qs)
        ] + questions
        source += "+resume"

    logger.info(
        f"[RoleConfig] role='{job_role}' slug='{role_slug}' "
        f"goals={len(goals)} questions={len(questions)} source={source}"
    )
    return RecruiterConfig(
        job_role=job_role,
        company_name=company_name,
        interview_type="technical",
        system_prompt=compose_system_prompt(job_role, company_name, "technical", job.get("llm_prompt"))
        + _candidate_briefing(candidate),
        questions=questions,
        goals=goals,
    )
