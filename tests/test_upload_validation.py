"""Tests for app/intake/upload.py after the dead-code cleanup.

The filename and size guards run BEFORE pdfplumber, so they're testable without a
real PDF. We also cover is_valid_resume_structure directly.
"""

import pytest

from app.intake.upload import (
    IngestionError,
    is_valid_resume_structure,
    validate_and_extract,
)

GOOD_RESUME = """
John Doe
john.doe@example.com

Work Experience
Senior Engineer at Acme, 2019-2024

Education
BSc Computer Science, State University

Skills
Python, FastAPI, PostgreSQL
"""


def test_rejects_non_pdf_extension():
    with pytest.raises(IngestionError) as ei:
        validate_and_extract(b"whatever", "resume.txt")
    assert ei.value.status_code == 400
    assert "PDF" in str(ei.value)


def test_rejects_oversized_file():
    big = b"x" * (5 * 1024 * 1024 + 1)
    with pytest.raises(IngestionError) as ei:
        validate_and_extract(big, "resume.pdf")
    assert "size" in str(ei.value).lower()


def test_valid_resume_structure_accepts_real_resume():
    assert is_valid_resume_structure(GOOD_RESUME) is True


def test_valid_resume_structure_requires_email():
    no_email = GOOD_RESUME.replace("john.doe@example.com", "")
    assert is_valid_resume_structure(no_email) is False


def test_valid_resume_structure_rejects_junk():
    assert is_valid_resume_structure("just some random text with no sections") is False
