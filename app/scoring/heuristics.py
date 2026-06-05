"""Heuristic candidate name extraction before Tier 3 LLM enrichment."""
import re

from .tier1 import EMAIL_REGEX, PHONE_REGEX

SECTION_HEADERS = {
    "experience", "education", "skills", "summary", "objective",
    "profile", "contact", "projects", "certifications", "references",
    "employment", "work history", "professional",
}


def extract_name_heuristic(text: str) -> str | None:
    """
    Extract likely candidate name from resume header lines.
    Avoids section headers and lines containing email/phone.
    """
    lines = [ln.strip() for ln in text.strip().split("\n") if ln.strip()]
    for line in lines[:8]:
        lower = line.lower()
        if EMAIL_REGEX.search(line) or PHONE_REGEX.search(line):
            continue
        if any(h in lower for h in SECTION_HEADERS):
            continue
        if len(line) > 60 or len(line.split()) > 5:
            continue
        if re.search(r"\d{3,}", line):
            continue
        words = line.split()
        if len(words) < 2 or len(words) > 4:
            continue
        if all(w[0].isupper() for w in words if w and w[0].isalpha()):
            cleaned = re.sub(r"[^A-Za-z\s\-\.']", "", line).strip()
            if len(cleaned.split()) >= 2:
                return cleaned
    return None
