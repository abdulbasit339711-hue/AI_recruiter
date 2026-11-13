"""
document_processor.py
─────────────────────
Unified document ingestion pipeline for the ATS HR profiling workflow.

Supports two modes:
  • Text PDF  – fast pdfplumber extraction (existing path, enhanced)
  • Image PDF / scanned docs / raw images – OCR via pytesseract + pdf2image

After raw text is obtained the module runs a lightweight LLM extraction pass
(same Groq client used by Tier-3 scoring) to populate candidate profile fields
automatically, so HR just drops a document and every field is pre-filled.
"""

from __future__ import annotations

import io
import json
import logging
import re
from typing import Any, Optional

import pdfplumber

logger = logging.getLogger(__name__)

# ── Minimum text quality thresholds ──────────────────────────────────────────
_MIN_TEXT_CHARS = 50          # below this → treat PDF as image-only
_MAX_FILE_MB    = 10          # 10 MB for HR documents (larger than candidate limit)
_MAX_FILE_BYTES = _MAX_FILE_MB * 1024 * 1024


# ── OCR availability check (graceful degradation) ─────────────────────────────

def _ocr_available() -> bool:
    """Return True only if both pytesseract *and* pdf2image are importable."""
    try:
        import pytesseract  # noqa: F401
        import pdf2image    # noqa: F401
        return True
    except ImportError:
        return False


# ── Core extraction helpers ───────────────────────────────────────────────────

def _extract_text_pdf(file_bytes: bytes) -> str:
    """Extract selectable text from a PDF using pdfplumber."""
    pages: list[str] = []
    try:
        with pdfplumber.open(io.BytesIO(file_bytes)) as pdf:
            for page in pdf.pages:
                t = page.extract_text()
                if t:
                    pages.append(t)
    except Exception as exc:
        logger.warning("pdfplumber extraction failed: %s", exc)
        return ""
    return "\n".join(pages).strip()


def _extract_text_ocr_pdf(file_bytes: bytes) -> str:
    """OCR every page of a PDF via pdf2image → pytesseract."""
    try:
        import pdf2image
        import pytesseract
    except ImportError:
        logger.warning("OCR dependencies not installed; cannot process image PDF.")
        return ""

    try:
        images = pdf2image.convert_from_bytes(file_bytes, dpi=300)
    except Exception as exc:
        logger.warning("pdf2image conversion failed: %s", exc)
        return ""

    pages: list[str] = []
    for img in images:
        try:
            text = pytesseract.image_to_string(img, lang="eng")
            if text.strip():
                pages.append(text.strip())
        except Exception as exc:
            logger.warning("pytesseract OCR failed on page: %s", exc)

    return "\n".join(pages).strip()


def _extract_text_ocr_image(file_bytes: bytes) -> str:
    """OCR a raw image file (JPEG, PNG, TIFF, BMP, WEBP)."""
    try:
        import pytesseract
        from PIL import Image
    except ImportError:
        logger.warning("OCR/PIL dependencies not installed; cannot process image.")
        return ""

    try:
        img = Image.open(io.BytesIO(file_bytes))
        text = pytesseract.image_to_string(img, lang="eng")
        return text.strip()
    except Exception as exc:
        logger.warning("pytesseract image OCR failed: %s", exc)
        return ""


# ── Public extraction entry-point ─────────────────────────────────────────────

class DocumentIngestionError(Exception):
    """Raised when a document cannot be usefully processed."""
    def __init__(self, message: str, status_code: int = 400):
        super().__init__(message)
        self.message   = message
        self.status_code = status_code


def extract_text(file_bytes: bytes, filename: str, *, allow_ocr: bool = True) -> str:
    """
    Extract raw text from *any* supported document format.

    Strategy (in order):
      1. If PDF → try pdfplumber text extraction.
      2. If text is too short (scanned/image PDF) and OCR is available → OCR.
      3. If image file (jpg/png/tiff/bmp/webp) → OCR directly.

    Parameters
    ----------
    file_bytes : raw file content
    filename   : original filename (used for extension detection)
    allow_ocr  : set False to skip OCR even for image PDFs (unit-test helper)

    Returns
    -------
    Extracted text, never empty (raises DocumentIngestionError otherwise).
    """
    if len(file_bytes) > _MAX_FILE_BYTES:
        raise DocumentIngestionError(
            f"File exceeds the {_MAX_FILE_MB} MB limit.", 400
        )

    ext = filename.rsplit(".", 1)[-1].lower() if "." in filename else ""
    text = ""

    if ext == "pdf":
        text = _extract_text_pdf(file_bytes)
        if len(text) < _MIN_TEXT_CHARS and allow_ocr:
            logger.info("PDF '%s' has little selectable text (%d chars) – falling back to OCR.", filename, len(text))
            if _ocr_available():
                text = _extract_text_ocr_pdf(file_bytes)
            else:
                raise DocumentIngestionError(
                    "Scanned/image PDF detected. Install 'pytesseract' and 'pdf2image' "
                    "on the server to enable OCR for image-based PDFs.",
                    422,
                )

    elif ext in {"jpg", "jpeg", "png", "tiff", "tif", "bmp", "webp"}:
        if not allow_ocr:
            raise DocumentIngestionError("OCR is disabled.", 400)
        if not _ocr_available():
            raise DocumentIngestionError(
                "Image files require OCR. Install 'pytesseract' and 'Pillow' on the server.",
                422,
            )
        text = _extract_text_ocr_image(file_bytes)

    elif ext in {"txt", "text"}:
        try:
            text = file_bytes.decode("utf-8", errors="replace")
        except Exception:
            text = ""

    else:
        raise DocumentIngestionError(
            f"Unsupported file type '.{ext}'. Accepted: PDF, JPG, PNG, TIFF, BMP, WEBP, TXT.",
            400,
        )

    if not text or len(text.strip()) < _MIN_TEXT_CHARS:
        raise DocumentIngestionError(
            "Could not extract readable text from the document. "
            "Ensure the file is not corrupt and, for scanned documents, that "
            "OCR dependencies are installed.",
            422,
        )

    return text


# ── LLM-powered field extraction for candidate profiling ─────────────────────

_PROFILE_SCHEMA = """{
  "name":               "<full name or empty string>",
  "email":              "<email or empty string>",
  "phone":              "<phone number or empty string>",
  "date_of_birth":      "<YYYY-MM-DD or empty string>",
  "national_id":        "<ID number or empty string>",
  "address":            "<full address or empty string>",
  "current_role":       "<job title or empty string>",
  "department":         "<department or empty string>",
  "employee_id":        "<employee/staff ID or empty string>",
  "companies":          ["<company1>", "..."],
  "total_years_experience": <number or 0>,
  "education": {"degree": "", "institution": "", "year": null},
  "skills":             ["<skill1>", "..."],
  "certifications":     ["<cert1>", "..."],
  "emergency_contact":  "<name + phone or empty string>",
  "document_type":      "<CV|Offer Letter|Contract|ID Document|Certificate|Medical|Other>",
  "document_summary":   "<2-3 sentence plain-English summary of the document>"
}"""

_PROFILE_SYSTEM_PROMPT = (
    "You are an expert HR document parser. Extract structured information from the "
    "provided document text and return ONLY valid JSON matching the schema below. "
    "Do not include markdown, code fences, or any text outside the JSON object. "
    "Leave a field as its default empty value if the information is not present in the document.\n\n"
    "SCHEMA:\n" + _PROFILE_SCHEMA
)


def extract_profile_fields(raw_text: str) -> dict[str, Any]:
    """
    Use the Groq LLM to extract structured profile fields from raw document text.

    Returns a dict with keys matching _PROFILE_SCHEMA.  On any LLM failure the
    function returns a best-effort dict produced by simple regex heuristics so
    the pipeline never hard-fails on a missing API key or quota issue.
    """
    from ..llm.groq_client import get_groq_client
    from ..llm.json_parser import parse_llm_json
    from ..database import config as app_config

    client = get_groq_client()
    if client is None:
        logger.warning("Groq client unavailable; using regex fallback for profile extraction.")
        return _regex_fallback(raw_text)

    model = (
        app_config.get("llm", {}).get("model", "llama3-8b-8192")
    )
    # Truncate to ~6000 chars to stay within token limits
    truncated = raw_text[:6000]

    try:
        response = client.chat.completions.create(
            model=model,
            messages=[
                {"role": "system", "content": _PROFILE_SYSTEM_PROMPT},
                {"role": "user",   "content": f"Document text:\n\n{truncated}"},
            ],
            temperature=0.0,
            max_tokens=1024,
        )
        raw_json = response.choices[0].message.content or "{}"
        data = parse_llm_json(raw_json)
        if isinstance(data, dict):
            return data
        logger.warning("LLM returned non-dict JSON; falling back to regex.")
    except Exception as exc:
        logger.warning("LLM profile extraction failed (%s); using regex fallback.", exc)

    return _regex_fallback(raw_text)


# ── Regex-based fallback extractor ─────────────────────────────────────────────

_RE_EMAIL   = re.compile(r'[a-zA-Z0-9._%+\-]+@[a-zA-Z0-9.\-]+\.[a-zA-Z]{2,}')
_RE_PHONE   = re.compile(
    r'(?:\+?[\d]{1,3}[\s\-.]?)?(?:\(?\d{2,4}\)?[\s\-.]?)?\d{3,4}[\s\-.]?\d{3,4}(?:[\s\-.]?\d{2,4})?'
)
_RE_DOB     = re.compile(
    r'\b(?:DOB|Date of Birth|Born)[:\s]*(\d{1,2}[/\-]\d{1,2}[/\-]\d{2,4}|\d{4}[/\-]\d{2}[/\-]\d{2})\b',
    re.IGNORECASE,
)
_RE_EMP_ID  = re.compile(
    r'\b(?:Employee\s+(?:ID|No\.?|Number)|Staff\s+(?:ID|No\.?)|EMP[#\-]?)[:\s]*([A-Z0-9\-]{3,20})\b',
    re.IGNORECASE,
)
_RE_NATID   = re.compile(
    r'\b(?:National\s+ID|NIC|CNIC|Passport\s+No\.?|ID\s+No\.?)[:\s]*([A-Z0-9\-]{5,25})\b',
    re.IGNORECASE,
)
_RE_GITHUB  = re.compile(r'(?:https?://)?(?:www\.)?github\.com/([A-Za-z0-9_.\-]+)', re.IGNORECASE)
_RE_LINKEDIN= re.compile(r'(?:https?://)?(?:www\.)?linkedin\.com/in/([A-Za-z0-9_.\-]+)', re.IGNORECASE)


def _regex_fallback(text: str) -> dict[str, Any]:
    """Extract the most common fields using regex when the LLM is unavailable."""
    email_m  = _RE_EMAIL.search(text)
    phone_m  = _RE_PHONE.search(text)
    dob_m    = _RE_DOB.search(text)
    empid_m  = _RE_EMP_ID.search(text)
    natid_m  = _RE_NATID.search(text)

    return {
        "name":               "",
        "email":              email_m.group(0) if email_m else "",
        "phone":              phone_m.group(0).strip() if phone_m else "",
        "date_of_birth":      dob_m.group(1) if dob_m else "",
        "national_id":        natid_m.group(1) if natid_m else "",
        "address":            "",
        "current_role":       "",
        "department":         "",
        "employee_id":        empid_m.group(1) if empid_m else "",
        "companies":          [],
        "total_years_experience": 0,
        "education":          {"degree": "", "institution": "", "year": None},
        "skills":             [],
        "certifications":     [],
        "emergency_contact":  "",
        "document_type":      "Other",
        "document_summary":   text[:300].replace("\n", " ").strip() + "…",
    }
