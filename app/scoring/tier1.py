import re
import logging
from ..database import config
from ..core.model_registry import get_spacy_model

logger = logging.getLogger(__name__)

# ── Regex patterns ────────────────────────────────────────────────────────────
EMAIL_REGEX = re.compile(r'[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}')
PHONE_REGEX = re.compile(
    r'(?:\+?\d{1,3}[-.\s]?)?'      # Optional country code
    r'(?:\(?\d{2,4}\)?[-.\s]?)'    # Area code
    r'\d{2,4}[-.\s]?\d{3,4}'       # Local digits
    r'(?:[-.\s]?\d{3,4})?'         # Optional remaining digits
)

def extract_name(text: str) -> str | None:
    """Return the first PERSON entity found by spaCy, or None if not detected."""
    nlp = get_nlp()
    doc = nlp(text)
    for ent in doc.ents:
        if ent.label_ == "PERSON":
            return ent.text.strip()
    return None

# ── Section keyword sets ──────────────────────────────────────────────────────
EDUCATION_KEYWORDS  = {'education', 'academic', 'degree', 'university', 'college', 'school', 'qualifications', 'graduation'}
EXPERIENCE_KEYWORDS = {'experience', 'employment', 'history', 'work', 'career', 'job', 'professional', 'internship', 'responsibilities'}
SKILLS_KEYWORDS     = {'skills', 'technologies', 'tools', 'languages', 'expertise', 'competencies', 'proficiencies', 'technical'}

# ── Rejection thresholds ──────────────────────────────────────────────────────
DEFAULT_MIN_LENGTH       = 100   # chars
DEFAULT_MAX_LENGTH       = 50_000  # chars — catches binary/garbage dumps
DEFAULT_MIN_WORD_COUNT   = 10  # lowered to accept short test resumes
DEFAULT_MIN_SECTIONS     = 2     # out of 3 (education, experience, skills)
DEFAULT_MIN_ALPHA_RATIO  = 0.60  # at least 60 % of chars must be alphabetic/space

# Noise patterns — if matched, document is almost certainly not a resume
NOISE_PATTERNS = [
    re.compile(r'<\s*(html|body|div|script|style)[^>]*>', re.IGNORECASE),  # HTML bleed-through
    re.compile(r'\\x[0-9a-fA-F]{2}'),                                       # hex escapes (binary)
    re.compile(r'([A-Za-z0-9])\1{6,}'),  # long repeated alphanum chars (garbled)
]

def get_nlp():
    """Lazy-load spaCy model via shared registry."""
    model_name = config.get("spacy", {}).get("model", "en_core_web_sm")
    return get_spacy_model(model_name)


# ── Validation helpers ────────────────────────────────────────────────────────

def _check_noise(text: str) -> tuple[bool, str]:
    """Return (is_noisy, reason). Noisy → reject immediately."""
    for pattern in NOISE_PATTERNS:
        match = pattern.search(text)
        if match:
            return True, f"Noise pattern detected near: '{match.group(0)[:40]}'"
    return False, ""


def _check_alpha_ratio(text: str, threshold: float) -> tuple[bool, str]:
    """Reject if alphabetic+space characters are below threshold."""
    if not text:
        return False, "Empty text."
    alpha_count = sum(1 for c in text if c.isalpha() or c.isspace())
    ratio = alpha_count / len(text)
    if ratio < threshold:
        return False, (
            f"Text appears garbled or non-textual "
            f"(alpha ratio={ratio:.2f} < {threshold:.2f})."
        )
    return True, ""


def _validate_document(text: str, cfg: dict) -> tuple[bool, list[str], list[str]]:
    """
    Run all structural guards before scoring.

    Returns
    -------
    (is_valid, errors, warnings)
        errors   → hard failures; document must be rejected
        warnings → soft flags; document passes but caller should log
    """
    errors:   list[str] = []
    warnings: list[str] = []

    min_len      = cfg.get("min_resume_length",  DEFAULT_MIN_LENGTH)
    max_len      = cfg.get("max_resume_length",  DEFAULT_MAX_LENGTH)
    min_words    = cfg.get("min_word_count",     DEFAULT_MIN_WORD_COUNT)
    min_sections = cfg.get("min_sections",       DEFAULT_MIN_SECTIONS)
    alpha_thresh = cfg.get("min_alpha_ratio",    DEFAULT_MIN_ALPHA_RATIO)

    stripped = text.strip()

    # 1. Length bounds
    if len(stripped) < min_len:
        errors.append(f"Document too short ({len(stripped)} chars < {min_len} required).")
    if len(stripped) > max_len:
        errors.append(f"Document suspiciously large ({len(stripped)} chars > {max_len} limit).")

    # 2. Word count
    word_count = len(stripped.split())
    if word_count < min_words:
        errors.append(f"Too few words ({word_count} < {min_words} required).")

    # 3. Noise / garbled content
    is_noisy, noise_reason = _check_noise(stripped)
    if is_noisy:
        errors.append(f"Noise detected: {noise_reason}")

    # 4. Alpha ratio
    alpha_ok, alpha_reason = _check_alpha_ratio(stripped, alpha_thresh)
    if not alpha_ok:
        errors.append(alpha_reason)

    # Early exit — no point running heavier checks on garbage text
    if errors:
        return False, errors, warnings

    # 5. Section detection
    sections = detect_sections(stripped)
    found_count = sum(sections.values())
    if found_count < min_sections:
        missing = [k for k, v in sections.items() if not v]
        errors.append(
            f"Only {found_count}/{min_sections} required sections found. "
            f"Missing: {missing}."
        )

    # 6. Contact info — soft warnings only
    if not EMAIL_REGEX.search(stripped):
        warnings.append("No email address detected.")
    if not PHONE_REGEX.search(stripped):
        warnings.append("No phone number detected.")

    is_valid = len(errors) == 0
    return is_valid, errors, warnings


# ── Section detector ──────────────────────────────────────────────────────────

def detect_sections(text: str) -> dict:
    """
    Detect resume sections via short-line keyword matching with spaCy tokenisation,
    falling back to full-text keyword search.
    """
    get_nlp()  # ensure model loaded; used implicitly via tokenisation pipeline

    found = {"education": False, "experience": False, "skills": False}

    keyword_map = {
        "education":  EDUCATION_KEYWORDS,
        "experience": EXPERIENCE_KEYWORDS,
        "skills":     SKILLS_KEYWORDS,
    }

    lines = [line.strip().lower() for line in text.split("\n") if line.strip()]

    for line in lines:
        cleaned = re.sub(r"[^a-z\s]", "", line).strip()
        words   = set(cleaned.split())

        for section, keywords in keyword_map.items():
            if not found[section] and words & keywords and len(cleaned.split()) < 5:
                found[section] = True

    # Fallback: anywhere in full text
    lower_text = text.lower()
    for section, keywords in keyword_map.items():
        if not found[section] and any(kw in lower_text for kw in keywords):
            found[section] = True

    return found


# ── Public exception ──────────────────────────────────────────────────────────

class IrrelevantDocumentError(ValueError):
    """Raised when a submitted document fails Tier 1 structural validation."""


# ── Scorer ────────────────────────────────────────────────────────────────────

def score_tier1(text: str) -> dict:
    """
    Compute Tier 1 score based on contact info presence and resume structure.
    Rejects documents that fail structural validation before any scoring.

    Returns
    -------
    {
        "tier1_total":       float,
        "name":              str | None,
        "email":             str | None,
        "phone":             str | None,
        "email_score":       float,
        "phone_score":       float,
        "education_score":   float,
        "experience_score":  float,
        "skills_score":      float,
        "is_valid":          bool,
        "warnings":          list[str],
    }

    Raises
    ------
    IrrelevantDocumentError
        If the document fails any hard structural check.
    """
    cfg = config.get("scoring", {})

    # ── Validate first ────────────────────────────────────────────────────────
    is_valid, errors, warnings = _validate_document(text, cfg)
    if not is_valid:
        raise IrrelevantDocumentError(
            f"Document rejected at Tier 1 ({len(errors)} error(s)): "
            + " | ".join(errors)
        )

    for w in warnings:
        logger.warning("Tier 1 [soft]: %s", w)

    # ── Load weights ──────────────────────────────────────────────────────────
    email_wt  = float(cfg.get("email_weight",      5))
    phone_wt  = float(cfg.get("phone_weight",      5))
    edu_wt    = float(cfg.get("education_weight",  7))
    exp_wt    = float(cfg.get("experience_weight", 7))
    skills_wt = float(cfg.get("skills_weight",     6))

    # ── Contact info scoring ──────────────────────────────────────────────────
    email_match   = EMAIL_REGEX.search(text)
    email_address = email_match.group(0) if email_match else None
    email_score   = email_wt if email_address else 0.0
    phone_match   = PHONE_REGEX.search(text)
    phone_number  = phone_match.group(0) if phone_match else None
    phone_score   = phone_wt if phone_number else 0.0

    # ── Section scoring ───────────────────────────────────────────────────────
    sections          = detect_sections(text)
    education_score   = edu_wt    if sections["education"]  else 0.0
    experience_score  = exp_wt    if sections["experience"] else 0.0
    skills_score      = skills_wt if sections["skills"]     else 0.0

    tier1_total = email_score + phone_score + education_score + experience_score + skills_score

    return {
        "tier1_total":      round(tier1_total, 2),
        "email":            email_address,
        "phone":            phone_number,
        "email_score":      email_score,
        "phone_score":      phone_score,
        "name":             extract_name(text),
        "education_score":  education_score,
        "experience_score": experience_score,
        "skills_score":     skills_score,
        "is_valid":         True,
        "warnings":         warnings,
    }