import logging
from typing import Optional

import numpy as np

from ..database import config
from ..core.jd_embedding_cache import get_jd_embedding
from ..core.model_registry import get_embedding_model
from .tier1 import detect_sections, EMAIL_REGEX, PHONE_REGEX

logger = logging.getLogger(__name__)

DEFAULT_SIMILARITY_THRESHOLD = 0.20
DEFAULT_MIN_RESUME_LENGTH = 100
DEFAULT_MIN_JD_LENGTH = 50

RESUME_SIGNAL_KEYWORDS = {
    "experience", "education", "skills", "work", "employment",
    "responsibilities", "achievements", "projects", "certifications",
    "summary", "objective", "profile", "references",
}
MIN_RESUME_SIGNALS = 2


def calculate_cosine_similarity(vec1: np.ndarray, vec2: np.ndarray) -> float:
    norm_a = np.linalg.norm(vec1)
    norm_b = np.linalg.norm(vec2)
    if norm_a == 0.0 or norm_b == 0.0:
        return 0.0
    return float(np.dot(vec1, vec2) / (norm_a * norm_b))


def _looks_like_resume(text: str) -> tuple[bool, str]:
    cfg = config.get("scoring", {})
    min_chars = cfg.get("min_resume_length", DEFAULT_MIN_RESUME_LENGTH)
    stripped = text.strip()

    if len(stripped) < min_chars:
        return False, f"Document too short ({len(stripped)} chars < {min_chars})."

    lower = stripped.lower()
    found_signals = {kw for kw in RESUME_SIGNAL_KEYWORDS if kw in lower}
    if len(found_signals) < MIN_RESUME_SIGNALS:
        return False, (
            f"Too few resume signals ({len(found_signals)}/{MIN_RESUME_SIGNALS} required). "
            f"Found: {found_signals or 'none'}."
        )

    sections = detect_sections(stripped)
    if not any(sections.values()):
        return False, "No recognisable resume sections (Education / Experience / Skills) detected."

    has_email = bool(EMAIL_REGEX.search(stripped))
    has_phone = bool(PHONE_REGEX.search(stripped))
    if not has_email and not has_phone:
        return True, "Warning: no contact information (email/phone) detected."

    return True, ""


def _looks_like_jd(text: str) -> tuple[bool, str]:
    cfg = config.get("scoring", {})
    min_chars = cfg.get("min_jd_length", DEFAULT_MIN_JD_LENGTH)
    min_signals = cfg.get("min_jd_signals", 1)

    stripped = text.strip()

    # A short or thin job description is the recruiter's input, not the candidate's
    # fault — it must never cause the resume to be rejected. Warn (so HR can flesh out
    # the posting) but always let scoring proceed. Genuinely empty JDs are still caught
    # by the explicit emptiness check in score_tier2.
    warnings: list[str] = []
    if len(stripped) < min_chars:
        warnings.append(
            f"Warning: job description is very short ({len(stripped)} chars < {min_chars}); "
            f"similarity and LLM scoring may be less reliable."
        )

    jd_signals = {
        "responsibilities", "requirements", "qualifications",
        "experience", "skills", "role", "position", "job", "duties",
    }
    lower = stripped.lower()
    found = {kw for kw in jd_signals if kw in lower}
    if len(found) < min_signals:
        warnings.append(f"Warning: only {len(found)}/{min_signals} JD signals found: {found or 'none'}.")

    return True, " ".join(warnings)


class IrrelevantDocumentError(ValueError):
    """Raised when the document fails structural or semantic checks."""


def score_tier2(
    resume_text: str,
    jd_text: str,
    job_id: Optional[int] = None,
) -> dict:
    """
    Semantic similarity between resume and JD using cached JD embeddings.
    """
    cfg = config.get("scoring", {})
    semantic_wt = float(cfg.get("semantic_weight", 40.0))
    sim_threshold = float(cfg.get("similarity_threshold", DEFAULT_SIMILARITY_THRESHOLD))
    warnings: list[str] = []

    if not resume_text.strip():
        raise IrrelevantDocumentError("Resume text is empty.")
    if not jd_text.strip():
        raise IrrelevantDocumentError("Job Description text is empty.")

    resume_valid, resume_reason = _looks_like_resume(resume_text)
    if not resume_valid:
        raise IrrelevantDocumentError(f"Resume rejected: {resume_reason}")
    if resume_reason.startswith("Warning"):
        warnings.append(resume_reason)

    jd_valid, jd_reason = _looks_like_jd(jd_text)
    if not jd_valid:
        raise IrrelevantDocumentError(f"Job Description rejected: {jd_reason}")
    if jd_reason.startswith("Warning"):
        warnings.append(jd_reason)

    model = get_embedding_model()
    resume_embedding = model.encode(resume_text, show_progress_bar=False)
    if hasattr(resume_embedding, "numpy"):
        resume_embedding = resume_embedding.numpy()
    resume_vec = np.asarray(resume_embedding, dtype=np.float32)

    jd_vec = get_jd_embedding(jd_text, job_id=job_id)
    similarity = calculate_cosine_similarity(resume_vec, jd_vec)

    if similarity < sim_threshold:
        raise IrrelevantDocumentError(
            f"Resume appears unrelated to the Job Description "
            f"(similarity={similarity:.3f} < threshold={sim_threshold:.3f})."
        )

    score = round(max(0.0, min(semantic_wt, similarity * semantic_wt)), 2)

    return {
        "tier2_score": score,
        "similarity": round(similarity, 4),
        "is_valid": True,
        "warnings": warnings,
    }
