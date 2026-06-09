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

    logger.info(
        f"[RoleConfig] role='{job_role}' slug='{role_slug}' "
        f"goals={len(goals)} questions={len(questions)} source={source}"
    )
    return RecruiterConfig(
        job_role=job_role,
        company_name=company_name,
        interview_type="technical",
        system_prompt=compose_system_prompt(job_role, company_name, "technical", job.get("llm_prompt")),
        questions=questions,
        goals=goals,
    )
