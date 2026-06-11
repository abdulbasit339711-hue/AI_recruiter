import json
import logging
from concurrent.futures import ThreadPoolExecutor

from sqlalchemy.orm import Session

from ..core import status as S
from ..database import config
from ..llm.groq_client import evaluate_with_llm
from ..models import Candidate, Job
from ..core.jd_embedding_cache import invalidate_job
from ..events import publish_candidate_event
from .heuristics import extract_name_heuristic
from .tier1 import score_tier1, IrrelevantDocumentError as Tier1IrrelevantError
from .tier2 import score_tier2, IrrelevantDocumentError as Tier2IrrelevantError

logger = logging.getLogger(__name__)


def _pipeline_cfg() -> dict:
    return config.get("pipeline", {})


def _weighted_total(candidate: Candidate, job) -> float:
    """Final score = tier1*w1 + tier2*w2 + tier3*w3 using the job's per-tier weights.
    Weights default to 1.0 (→ the plain tier sum), so behaviour is unchanged unless HR
    sets custom weights for the role."""
    w1 = (getattr(job, "tier1_weight", None) if job else None) or 1.0
    w2 = (getattr(job, "tier2_weight", None) if job else None) or 1.0
    w3 = (getattr(job, "tier3_weight", None) if job else None) or 1.0
    return round(candidate.tier1 * w1 + candidate.tier2 * w2 + candidate.tier3 * w3, 2)


def _resolve_final_status(total_score: float, llm_status: str | None) -> str:
    cfg = _pipeline_cfg()
    shortlisted_min = float(cfg.get("shortlisted_min_score", 75.0))
    reviewed_min = float(cfg.get("reviewed_min_score", 60.0))

    if total_score >= shortlisted_min:
        return S.SHORTLISTED
    if total_score >= reviewed_min:
        return S.REVIEWED
    if llm_status in (S.SHORTLISTED, S.REVIEWED, S.REJECTED):
        return llm_status
    return S.REJECTED


def _apply_tier1_contact(candidate: Candidate, t1: dict) -> None:
    if t1.get("email") and not candidate.email:
        candidate.email = t1["email"]
    if t1.get("phone") and not candidate.phone:
        candidate.phone = t1["phone"]
    name = extract_name_heuristic(candidate.raw_text or "")
    if not name:
        name = t1.get("name")
    if name and not candidate.name:
        candidate.name = name


def _apply_tier3_fields(candidate: Candidate, t3: dict) -> None:
    if t3.get("name"):
        candidate.name = t3["name"]
    if t3.get("email") and not candidate.email:
        candidate.email = t3["email"]
    if t3.get("phone") and not candidate.phone:
        candidate.phone = t3["phone"]
    candidate.current_role = t3.get("current_role") or candidate.current_role
    candidate.companies = json.dumps(t3.get("companies", []))
    candidate.skills_matched = json.dumps(t3.get("skills_matched", []))
    candidate.skills_missing = json.dumps(t3.get("skills_missing", []))
    candidate.tier3 = float(t3.get("tier3_score", 0.0))
    candidate.summary = t3.get("summary", "")
    candidate.evidence = json.dumps(t3.get("evidence", []))
    candidate.interview_questions = json.dumps(t3.get("interview_questions", []))
    try:
        candidate.years_experience = float(t3.get("total_years_experience", 0) or 0)
    except (TypeError, ValueError):
        candidate.years_experience = None
    candidate.evaluation_data = json.dumps(t3)

    usage = t3.get("usage") or {}
    candidate.llm_prompt_tokens = int(usage.get("prompt_tokens", 0) or 0)
    candidate.llm_completion_tokens = int(usage.get("completion_tokens", 0) or 0)
    candidate.llm_cost_usd = float(usage.get("cost_usd", 0.0) or 0.0)


def _run_tier1(resume_text: str) -> dict:
    return score_tier1(resume_text)


def _run_tier2(resume_text: str, jd_text: str, job_id: int | None) -> dict:
    return score_tier2(resume_text, jd_text, job_id=job_id)


def evaluate_candidate_pipeline(
    candidate_id: int,
    db: Session,
    jd_text: str | None = None,
) -> Candidate:
    """
    Three-tier pipeline: Tier 1 + Tier 2 in parallel, Tier 3 if combined threshold met.
    Status flow: Queued → Processing → terminal status.
    """
    candidate = db.query(Candidate).filter(Candidate.id == candidate_id).first()
    if not candidate:
        raise ValueError(f"Candidate with ID {candidate_id} not found.")

    target_jd = jd_text
    custom_prompt = None
    job_id = candidate.job_id
    job = None

    if candidate.job_id:
        job = db.query(Job).filter(Job.id == candidate.job_id).first()
        if job:
            target_jd = job.job_description
            custom_prompt = job.llm_prompt

    if not target_jd:
        target_jd = "Senior Python Developer with FastAPI and AWS experience."

    candidate.status = S.PROCESSING
    db.commit()
    publish_candidate_event(
        candidate.id,
        S.PROCESSING,
        job_id=candidate.job_id,
    )

    try:
        resume_text = candidate.raw_text or ""
        t1_result: dict | None = None
        t2_result: dict | None = None
        all_warnings: list[str] = []

        with ThreadPoolExecutor(max_workers=2) as executor:
            f1 = executor.submit(_run_tier1, resume_text)
            f2 = executor.submit(_run_tier2, resume_text, target_jd, job_id)
            t1_result = f1.result()
            t2_result = f2.result()

        candidate.tier1 = t1_result["tier1_total"]
        _apply_tier1_contact(candidate, t1_result)
        all_warnings.extend(t1_result.get("warnings", []))

        candidate.tier2 = t2_result["tier2_score"]
        all_warnings.extend(t2_result.get("warnings", []))
        candidate.warnings = json.dumps(all_warnings)

        combined = candidate.tier1 + candidate.tier2
        tier3_threshold = float(_pipeline_cfg().get("tier3_combined_threshold", 25.0))

        if combined < tier3_threshold:
            candidate.tier3 = 0.0
            candidate.total_score = _weighted_total(candidate, job)
            candidate.status = S.UNGRADED
            candidate.summary = (
                f"Automated screening completed without LLM evaluation "
                f"(combined Tier 1+2 score {combined:.1f} below threshold {tier3_threshold:.1f})."
            )
            db.commit()
            db.refresh(candidate)
            publish_candidate_event(
                candidate.id,
                candidate.status,
                job_id=candidate.job_id,
                total_score=candidate.total_score,
            )
            logger.info(
                "Candidate %d ungraded (combined=%.1f)",
                candidate.id,
                combined,
            )
            return candidate

        t3 = evaluate_with_llm(resume_text, target_jd, custom_prompt=custom_prompt)
        _apply_tier3_fields(candidate, t3)

        candidate.total_score = _weighted_total(candidate, job)
        candidate.status = _resolve_final_status(
            candidate.total_score,
            t3.get("status"),
        )

        db.commit()
        db.refresh(candidate)
        publish_candidate_event(
            candidate.id,
            candidate.status,
            job_id=candidate.job_id,
            total_score=candidate.total_score,
        )
        logger.info(
            "Candidate %d evaluated: total=%.1f status=%s",
            candidate.id,
            candidate.total_score,
            candidate.status,
        )
        return candidate

    except (Tier1IrrelevantError, Tier2IrrelevantError) as doc_err:
        db.rollback()
        candidate = db.query(Candidate).filter(Candidate.id == candidate_id).first()
        candidate.status = S.REJECTED
        candidate.summary = f"Document rejected: {doc_err}"
        candidate.tier3 = 0.0
        candidate.total_score = round(
            (candidate.tier1 or 0) + (candidate.tier2 or 0),
            2,
        )
        db.commit()
        publish_candidate_event(
            candidate.id,
            candidate.status,
            job_id=candidate.job_id,
            total_score=candidate.total_score,
        )
        logger.warning("Candidate %d rejected: %s", candidate_id, doc_err)
        return candidate

    except Exception as e:
        db.rollback()
        candidate = db.query(Candidate).filter(Candidate.id == candidate_id).first()
        if candidate:
            candidate.status = S.ERROR
            candidate.summary = f"Processing error: {e}"
            db.commit()
            publish_candidate_event(
                candidate.id,
                S.ERROR,
                job_id=candidate.job_id,
            )
        logger.exception("Pipeline error for candidate %d", candidate_id)
        raise
