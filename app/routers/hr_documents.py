"""
hr_documents.py  –  HR Document Upload & Auto-Profile Pipeline
═══════════════════════════════════════════════════════════════
Endpoints:
  POST   /candidates/{id}/documents          Upload a document (PDF text/image, JPG, PNG …)
  GET    /candidates/{id}/documents          List all documents for a candidate
  GET    /candidates/{id}/documents/{doc_id} Fetch document metadata + extracted fields
  DELETE /candidates/{id}/documents/{doc_id} Remove a document
  POST   /candidates/{id}/documents/{doc_id}/apply-to-profile
                                             Merge extracted fields → candidate profile

The pipeline:
  1. Accept file (PDF / image)
  2. Extract text (pdfplumber for text PDFs, OCR fallback for scanned / image files)
  3. Call LLM (Groq) to extract structured profile fields
  4. Persist as EmployeeDocument
  5. Optionally auto-apply extracted fields to the parent Candidate row
"""

from __future__ import annotations

import json
import logging
from datetime import timezone
from typing import Optional

from fastapi import APIRouter, Depends, File, Form, HTTPException, Query, UploadFile
from sqlalchemy.orm import Session

from ..core.utils import _utcnow
from ..database import get_db
from ..intake.document_processor import (
    DocumentIngestionError,
    extract_text,
    extract_profile_fields,
)
from ..models import Candidate, EmployeeDocument

logger = logging.getLogger(__name__)

router = APIRouter(tags=["hr-documents"])

# ── Allowed MIME types / extensions ──────────────────────────────────────────
_ALLOWED_EXTENSIONS = {"pdf", "jpg", "jpeg", "png", "tiff", "tif", "bmp", "webp", "txt"}

DOCUMENT_TYPES = [
    "CV", "Offer Letter", "Contract", "ID Document",
    "Certificate", "Medical", "Reference Letter", "Other",
]


def _ext(filename: str) -> str:
    return filename.rsplit(".", 1)[-1].lower() if "." in filename else "unknown"


# ─────────────────────────────────────────────────────────────────────────────
# POST  /candidates/{candidate_id}/documents
# ─────────────────────────────────────────────────────────────────────────────

@router.post("/candidates/{candidate_id}/documents")
async def upload_hr_document(
    candidate_id: int,
    file: UploadFile = File(..., description="PDF, JPG, PNG, TIFF, BMP or TXT"),
    document_type: Optional[str] = Form(
        None,
        description=(
            "Document category hint: CV | Offer Letter | Contract | ID Document | "
            "Certificate | Medical | Reference Letter | Other"
        ),
    ),
    uploaded_by: Optional[str] = Form(None, description="HR user performing the upload"),
    auto_apply: bool = Form(
        True,
        description=(
            "When True, extracted profile fields are immediately merged into the "
            "candidate's profile row (non-destructive: only fills empty fields)."
        ),
    ),
    db: Session = Depends(get_db),
):
    """
    Upload any supporting document for a candidate.

    The server automatically:
      • Detects whether the file is a text PDF or an image/scanned PDF
      • Falls back to OCR (pytesseract) for image-based documents
      • Runs an LLM extraction pass to populate profile fields
      • Optionally merges the extracted data into the candidate profile

    Returns the created EmployeeDocument record with extracted fields.
    """
    candidate = db.query(Candidate).filter(Candidate.id == candidate_id).first()
    if not candidate:
        raise HTTPException(status_code=404, detail="Candidate not found.")

    filename = file.filename or "document"
    ext = _ext(filename)

    if ext not in _ALLOWED_EXTENSIONS:
        raise HTTPException(
            status_code=400,
            detail=(
                f"Unsupported file type '.{ext}'. "
                f"Allowed: {', '.join(sorted(_ALLOWED_EXTENSIONS))}"
            ),
        )

    file_bytes = await file.read()
    file_size_kb = max(1, len(file_bytes) // 1024)

    # ── Extract raw text ──────────────────────────────────────────────────────
    ocr_used = False
    try:
        raw_text = extract_text(file_bytes, filename, allow_ocr=True)
        # Detect OCR: if the PDF had little pdfplumber text but we still got content
        if ext == "pdf":
            import pdfplumber, io as _io
            direct_chars = 0
            try:
                with pdfplumber.open(_io.BytesIO(file_bytes)) as _pdf:
                    for _p in _pdf.pages:
                        t = _p.extract_text()
                        if t:
                            direct_chars += len(t)
            except Exception:
                pass
            ocr_used = direct_chars < 50 and len(raw_text) >= 50
        elif ext in {"jpg", "jpeg", "png", "tiff", "tif", "bmp", "webp"}:
            ocr_used = True
    except DocumentIngestionError as die:
        raise HTTPException(status_code=die.status_code, detail=die.message)
    except Exception as exc:
        logger.exception("Unexpected error during text extraction")
        raise HTTPException(status_code=500, detail=f"Text extraction failed: {exc}")

    # ── LLM extraction of profile fields ─────────────────────────────────────
    try:
        extracted = extract_profile_fields(raw_text)
    except Exception as exc:
        logger.warning("Profile field extraction failed: %s – continuing with empty fields.", exc)
        extracted = {}

    # Use LLM-detected document type if HR did not specify one
    detected_doc_type = extracted.get("document_type") or document_type or "Other"

    extracted_json = json.dumps(extracted, ensure_ascii=False)

    # ── Persist EmployeeDocument ──────────────────────────────────────────────
    doc = EmployeeDocument(
        candidate_id     = candidate_id,
        filename         = filename,
        file_type        = ext,
        file_size_kb     = file_size_kb,
        ocr_used         = ocr_used,
        document_type    = detected_doc_type,
        raw_text         = raw_text,
        extracted_fields = extracted_json,
        file_data        = file_bytes,   # stored in DB; swap to object-store path if desired
        uploaded_by      = uploaded_by,
        uploaded_at      = _utcnow().isoformat(),
    )
    db.add(doc)
    db.flush()   # get doc.id before potential profile update

    # ── Auto-apply profile fields to Candidate ────────────────────────────────
    applied: dict = {}
    if auto_apply and extracted:
        applied = _merge_profile(candidate, extracted)
        db.add(candidate)

    db.commit()
    db.refresh(doc)

    return {
        "id":              doc.id,
        "candidate_id":    doc.candidate_id,
        "filename":        doc.filename,
        "file_type":       doc.file_type,
        "file_size_kb":    doc.file_size_kb,
        "ocr_used":        doc.ocr_used,
        "document_type":   doc.document_type,
        "uploaded_by":     doc.uploaded_by,
        "uploaded_at":     doc.uploaded_at,
        "extracted_fields": extracted,
        "fields_applied_to_profile": applied,
        "message": (
            "Document processed successfully. "
            + (f"{len(applied)} profile fields auto-filled." if applied else "No new profile fields extracted.")
        ),
    }


# ─────────────────────────────────────────────────────────────────────────────
# GET  /candidates/{candidate_id}/documents
# ─────────────────────────────────────────────────────────────────────────────

@router.get("/candidates/{candidate_id}/documents")
def list_hr_documents(
    candidate_id: int,
    db: Session = Depends(get_db),
):
    """List all HR-uploaded documents for a candidate (metadata only, no file bytes)."""
    candidate = db.query(Candidate).filter(Candidate.id == candidate_id).first()
    if not candidate:
        raise HTTPException(status_code=404, detail="Candidate not found.")

    docs = (
        db.query(EmployeeDocument)
        .filter(EmployeeDocument.candidate_id == candidate_id)
        .order_by(EmployeeDocument.id.desc())
        .all()
    )

    return {
        "candidate_id": candidate_id,
        "total":        len(docs),
        "documents":    [_doc_summary(d) for d in docs],
    }


# ─────────────────────────────────────────────────────────────────────────────
# GET  /candidates/{candidate_id}/documents/{doc_id}
# ─────────────────────────────────────────────────────────────────────────────

@router.get("/candidates/{candidate_id}/documents/{doc_id}")
def get_hr_document(
    candidate_id: int,
    doc_id: int,
    include_text: bool = Query(False, description="Include the full extracted raw_text"),
    db: Session = Depends(get_db),
):
    """Fetch a single document's metadata and extracted fields."""
    doc = _get_doc_or_404(db, candidate_id, doc_id)
    data = _doc_summary(doc)
    if include_text:
        data["raw_text"] = doc.raw_text
    return data


# ─────────────────────────────────────────────────────────────────────────────
# DELETE  /candidates/{candidate_id}/documents/{doc_id}
# ─────────────────────────────────────────────────────────────────────────────

@router.delete("/candidates/{candidate_id}/documents/{doc_id}")
def delete_hr_document(
    candidate_id: int,
    doc_id: int,
    db: Session = Depends(get_db),
):
    """Permanently delete a document record."""
    doc = _get_doc_or_404(db, candidate_id, doc_id)
    db.delete(doc)
    db.commit()
    return {"message": f"Document {doc_id} deleted."}


# ─────────────────────────────────────────────────────────────────────────────
# POST  /candidates/{candidate_id}/documents/{doc_id}/apply-to-profile
# ─────────────────────────────────────────────────────────────────────────────

@router.post("/candidates/{candidate_id}/documents/{doc_id}/apply-to-profile")
def apply_document_to_profile(
    candidate_id: int,
    doc_id: int,
    overwrite: bool = Query(
        False,
        description="When True, overwrite existing profile values. Default: only fill blank fields.",
    ),
    db: Session = Depends(get_db),
):
    """
    (Re-)apply the extracted fields from a specific document to the candidate profile.
    Useful if auto_apply was False at upload time, or if the LLM re-run produced better data.
    """
    doc = _get_doc_or_404(db, candidate_id, doc_id)
    candidate = db.query(Candidate).filter(Candidate.id == candidate_id).first()
    if not candidate:
        raise HTTPException(status_code=404, detail="Candidate not found.")

    try:
        extracted = json.loads(doc.extracted_fields or "{}")
    except json.JSONDecodeError:
        extracted = {}

    applied = _merge_profile(candidate, extracted, overwrite=overwrite)
    db.add(candidate)
    db.commit()
    db.refresh(candidate)

    return {
        "candidate_id": candidate_id,
        "doc_id":       doc_id,
        "fields_applied": applied,
        "message": f"{len(applied)} profile fields updated.",
    }


# ─────────────────────────────────────────────────────────────────────────────
# Helpers
# ─────────────────────────────────────────────────────────────────────────────

def _get_doc_or_404(db: Session, candidate_id: int, doc_id: int) -> EmployeeDocument:
    doc = (
        db.query(EmployeeDocument)
        .filter(
            EmployeeDocument.id == doc_id,
            EmployeeDocument.candidate_id == candidate_id,
        )
        .first()
    )
    if not doc:
        raise HTTPException(status_code=404, detail="Document not found.")
    return doc


def _doc_summary(doc: EmployeeDocument) -> dict:
    """Serialize an EmployeeDocument without the (potentially large) file_data bytes."""
    try:
        fields = json.loads(doc.extracted_fields or "{}")
    except Exception:
        fields = {}
    return {
        "id":              doc.id,
        "candidate_id":    doc.candidate_id,
        "filename":        doc.filename,
        "file_type":       doc.file_type,
        "file_size_kb":    doc.file_size_kb,
        "ocr_used":        doc.ocr_used,
        "document_type":   doc.document_type,
        "uploaded_by":     doc.uploaded_by,
        "uploaded_at":     doc.uploaded_at,
        "extracted_fields": fields,
    }


# Field mapping: JSON key from LLM → Candidate column name
_FIELD_MAP: dict[str, str] = {
    "name":               "name",
    "email":              "email",
    "phone":              "phone",
    "date_of_birth":      "date_of_birth",
    "national_id":        "national_id",
    "address":            "address",
    "current_role":       "current_role",
    "department":         "department",
    "employee_id":        "employee_id",
    "emergency_contact":  "emergency_contact",
    "document_summary":   "profile_summary",
}

# JSON-serialised list fields
_LIST_FIELD_MAP: dict[str, str] = {
    "skills":         "profile_skills",
    "certifications": "profile_certifications",
    "companies":      "companies",
}


def _merge_profile(
    candidate: Candidate,
    extracted: dict,
    *,
    overwrite: bool = False,
) -> dict:
    """
    Copy extracted fields onto the Candidate model.

    By default only fills fields that are currently empty/None (non-destructive).
    Pass overwrite=True to replace existing values.

    Returns a dict of {field: new_value} for everything that was actually updated.
    """
    applied: dict = {}

    for src_key, col_name in _FIELD_MAP.items():
        value = extracted.get(src_key)
        if not value or (isinstance(value, str) and not value.strip()):
            continue
        existing = getattr(candidate, col_name, None)
        if overwrite or not existing:
            setattr(candidate, col_name, value)
            applied[col_name] = value

    for src_key, col_name in _LIST_FIELD_MAP.items():
        items = extracted.get(src_key)
        if not isinstance(items, list) or not items:
            continue
        existing = getattr(candidate, col_name, None)
        if overwrite or not existing:
            setattr(candidate, col_name, json.dumps(items, ensure_ascii=False))
            applied[col_name] = items

    # Merge education → skills_matched / certifications paths are separate;
    # profile_summary gets document_summary even when name/email are blank.
    doc_summary = extracted.get("document_summary", "")
    if doc_summary and (overwrite or not candidate.profile_summary):
        candidate.profile_summary = doc_summary
        applied["profile_summary"] = doc_summary

    return applied
