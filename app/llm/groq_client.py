import os
import json
import logging
import re
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field, ValidationError, field_validator
from dotenv import load_dotenv

from ..database import config
from ..core.circuit_breaker import CircuitBreaker
from .json_parser import parse_llm_json

load_dotenv(
    os.path.join(
        os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))),
        ".env",
    )
)

logger = logging.getLogger(__name__)

_groq_client: Any = None
_circuit: CircuitBreaker | None = None

# Rough Groq pricing (USD per token), matching the voice agent's estimates:
# ~$0.20 / 1M input tokens, ~$1.00 / 1M output tokens.
GROQ_INPUT_COST_PER_TOKEN = 0.20 / 1_000_000
GROQ_OUTPUT_COST_PER_TOKEN = 1.00 / 1_000_000


def _usage_to_cost(prompt_tokens: int, completion_tokens: int) -> float:
    return round(
        prompt_tokens * GROQ_INPUT_COST_PER_TOKEN
        + completion_tokens * GROQ_OUTPUT_COST_PER_TOKEN,
        6,
    )


class EducationModel(BaseModel):
    degree: str = ""
    institution: str = ""
    year: Optional[int] = None


class Tier3Evaluation(BaseModel):
    name: str = ""
    email: str = ""
    phone: str = ""
    companies: List[str] = Field(default_factory=list)
    current_role: str = ""
    total_years_experience: float = 0.0
    education: EducationModel = Field(default_factory=EducationModel)
    skills_matched: List[str] = Field(default_factory=list)
    skills_missing: List[str] = Field(default_factory=list)
    tier3_score: float = Field(ge=0)
    status: str = ""
    summary: str = ""
    evidence: List[str] = Field(default_factory=list)

    @field_validator("summary")
    @classmethod
    def summary_word_limit(cls, v: str) -> str:
        words = v.split()
        if len(words) > 150:
            return " ".join(words[:150])
        return v


def get_circuit_breaker() -> CircuitBreaker:
    global _circuit
    if _circuit is None:
        cb_cfg = config.get("llm", {}).get("circuit_breaker", {})
        _circuit = CircuitBreaker(
            name="groq",
            failure_threshold=int(cb_cfg.get("failure_threshold", 5)),
            recovery_timeout=float(cb_cfg.get("recovery_timeout_seconds", 60)),
        )
    return _circuit


def get_groq_client() -> Optional[Any]:
    """Singleton Groq client."""
    global _groq_client
    api_key = os.getenv("GROQ_API_KEY")
    if not api_key or api_key == "your_groq_api_key_here":
        logger.warning("GROQ_API_KEY not set; Tier 3 will use fallback.")
        return None

    if _groq_client is not None:
        return _groq_client

    for var in ["HTTP_PROXY", "HTTPS_PROXY", "http_proxy", "https_proxy", "NO_PROXY", "no_proxy"]:
        os.environ.pop(var, None)
    try:
        from groq import Groq

        _groq_client = Groq(api_key=api_key)
        logger.info("Groq client initialized (singleton)")
        return _groq_client
    except Exception as e:
        logger.error("Failed to initialize Groq client: %s", e)
        return None


def groq_circuit_state() -> str:
    return get_circuit_breaker().state.value


def _build_system_prompt(custom_prompt: Optional[str], llm_wt: int) -> str:
    schema = (
        "{\n"
        '  "name": "<candidate full name>",\n'
        '  "email": "<email or empty string>",\n'
        '  "phone": "<phone or empty string>",\n'
        '  "companies": ["<company1>", "..."],\n'
        '  "current_role": "<most recent job title>",\n'
        '  "total_years_experience": <number>,\n'
        '  "education": {"degree": "", "institution": "", "year": null},\n'
        '  "skills_matched": ["<skill>", "..."],\n'
        '  "skills_missing": ["<skill>", "..."],\n'
        f'  "tier3_score": <integer 0-{llm_wt}>,\n'
        '  "status": "<Shortlisted|Reviewed|Rejected>",\n'
        '  "summary": "<100-150 word recruiter-style summary>",\n'
        '  "evidence": ["<concrete evidence>", "..."]\n'
        "}"
    )
    output_rules = (
        "RESPONSE FORMAT (STRICT):\n"
        f"- Return ONLY valid JSON matching:\n{schema}\n"
        "- No markdown, code fences, or text outside JSON.\n"
        "- summary MUST be 100-150 words: direct recruiter tone, strongest positive signal, "
        "biggest gap, experience relevance, role alignment."
    )

    if custom_prompt and custom_prompt.strip():
        return (
            f"{custom_prompt.strip()}\n\n"
            f"SCORING: 0-{llm_wt} on technical fit, experience depth, accomplishments.\n"
            f"{output_rules}"
        )
    return (
        "You are a senior technical recruiter conducting structured resume evaluation.\n"
        "Evaluate resume vs Job Description on technical fit, experience depth, and impact.\n"
        f"Assign tier3_score 0-{llm_wt}. Set status to Shortlisted, Reviewed, or Rejected.\n"
        f"{output_rules}"
    )


def _call_groq_api(
    client: Any,
    model_name: str,
    system_prompt: str,
    user_prompt: str,
) -> tuple[str, Dict[str, Any]]:
    """Call Groq and return (content, usage) where usage holds token counts + cost."""
    response = client.chat.completions.create(
        model=model_name,
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ],
        temperature=0.2,
        response_format={"type": "json_object"},
    )
    raw_usage = getattr(response, "usage", None)
    prompt_tokens = int(getattr(raw_usage, "prompt_tokens", 0) or 0)
    completion_tokens = int(getattr(raw_usage, "completion_tokens", 0) or 0)
    total_tokens = int(getattr(raw_usage, "total_tokens", prompt_tokens + completion_tokens) or 0)
    usage = {
        "prompt_tokens": prompt_tokens,
        "completion_tokens": completion_tokens,
        "total_tokens": total_tokens,
        "cost_usd": _usage_to_cost(prompt_tokens, completion_tokens),
    }
    return response.choices[0].message.content, usage


def evaluate_with_llm(
    resume_text: str,
    jd_text: str,
    custom_prompt: Optional[str] = None,
    retries: int = 3,
) -> Dict[str, Any]:
    """Tier 3 LLM evaluation with circuit breaker and strict JSON schema."""
    llm_wt = float(config.get("scoring", {}).get("llm_weight", 30))
    client = get_groq_client()
    circuit = get_circuit_breaker()

    if not client:
        return simulate_tier3_evaluation(resume_text, jd_text, int(llm_wt))

    if not circuit.allow_request():
        logger.warning("Groq circuit open; using fallback")
        return simulate_tier3_evaluation(
            resume_text, jd_text, int(llm_wt), "Groq circuit breaker open"
        )

    model_name = config.get("llm", {}).get("model", "llama-3.3-70b-versatile")
    system_prompt = _build_system_prompt(custom_prompt, int(llm_wt))
    user_prompt = (
        "Evaluate this resume against the job description.\n\n"
        f"JOB DESCRIPTION:\n{jd_text}\n\n"
        f"CANDIDATE RESUME:\n{resume_text}\n\n"
        "Respond with JSON only."
    )

    last_error: Optional[str] = None
    for attempt in range(retries):
        try:
            content, usage = _call_groq_api(client, model_name, system_prompt, user_prompt)
            circuit.record_success()
            parsed = parse_llm_json(content)
            score = float(parsed.get("tier3_score", 0))
            parsed["tier3_score"] = max(0.0, min(llm_wt, score))

            validated = Tier3Evaluation(**parsed)
            result = validated.model_dump()
            result["is_fallback"] = False  # genuine LLM evaluation
            result["usage"] = usage  # token counts + estimated cost for HR visibility
            return result

        except (ValidationError, json.JSONDecodeError, KeyError) as parse_err:
            last_error = str(parse_err)
            logger.warning("Attempt %d: JSON parse/validation failed: %s", attempt + 1, parse_err)
        except Exception as e:
            circuit.record_failure()
            last_error = str(e)
            logger.error("Attempt %d: Groq API error: %s", attempt + 1, e)

    return simulate_tier3_evaluation(
        resume_text,
        jd_text,
        int(llm_wt),
        last_error or "LLM evaluation failed after retries",
    )


def simulate_tier3_evaluation(
    resume_text: str,
    jd_text: str,
    max_score: int = 30,
    error_reason: Optional[str] = None,
) -> Dict[str, Any]:
    """Keyword-overlap fallback when Groq is unavailable.

    The result is flagged ``is_fallback: True`` so the score is never mistaken for a
    real LLM evaluation downstream.
    """
    logger.warning("Tier-3 FALLBACK score in use (LLM unavailable): %s", error_reason or "unknown reason")
    resume_lower = resume_text.lower()
    jd_words = set(re.findall(r"\b[a-z]{4,15}\b", jd_text.lower()))
    resume_words = set(re.findall(r"\b[a-z]{4,15}\b", resume_lower))
    common_words = jd_words.intersection(resume_words)
    match_count = len(common_words)
    simulated_score = min(max_score, 10 + int(match_count / 2))

    evidence = []
    for keyword, label in [
        ("python", "Python experience"),
        ("database", "Database/SQL proficiency"),
        ("sql", "Database/SQL proficiency"),
        ("fastapi", "Backend framework experience"),
        ("aws", "Cloud technology experience"),
    ]:
        if keyword in resume_lower:
            evidence.append(f"Resume mentions {label}.")

    if not evidence:
        evidence = ["Baseline keyword overlap with job description."]

    summary = (
        f"Automated screening (LLM unavailable). Candidate shows {match_count} keyword "
        f"overlaps with the role requirements. "
    )
    if error_reason:
        summary += f"Note: {error_reason}. "
    summary += (
        "Review manually for technical depth, role alignment, and experience relevance "
        "before making a hiring decision."
    )

    status = "Reviewed" if simulated_score >= max_score * 0.6 else "Rejected"

    return {
        "name": "",
        "email": "",
        "phone": "",
        "companies": [],
        "current_role": "",
        "total_years_experience": 0.0,
        "education": {"degree": "", "institution": "", "year": None},
        "skills_matched": list(common_words)[:8],
        "skills_missing": [],
        "tier3_score": simulated_score,
        "status": status,
        "summary": summary,
        "evidence": evidence,
        "is_fallback": True,
        "usage": {"prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0, "cost_usd": 0.0},
    }
