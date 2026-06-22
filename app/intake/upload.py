import io
import logging
import re
import pdfplumber

logger = logging.getLogger(__name__)

MAX_FILE_SIZE_BYTES = 5 * 1024 * 1024  # 5 MB
MIN_TEXT_LENGTH = 20  # Accept shorter text extracts (still require some content)

class IngestionError(Exception):
    def __init__(self, message: str, status_code: int = 400):
        super().__init__(message)
        self.message = message
        self.status_code = status_code

def extract_text_from_pdf(file_bytes: bytes) -> str:
    """Extracts text from PDF bytes using pdfplumber."""
    text_content = []
    try:
        with pdfplumber.open(io.BytesIO(file_bytes)) as pdf:
            for page in pdf.pages:
                page_text = page.extract_text()
                if page_text:
                    text_content.append(page_text)
    except Exception as e:
        logger.warning("PDF parse failed: %s", e)
        raise IngestionError("Failed to parse the PDF. The file may be corrupt or unsupported.")

    return "\n".join(text_content).strip()

def is_valid_resume_structure(text: str) -> bool:
    """
    Checks if the document matches standard professional CV/resume patterns.
    Requires an email address and at least two standard sections.
    """
    sections_matched = 0
    # 1. Experience Section
    if re.search(r'\b(experience|employment|work\s+history|career\s+history|professional\s+background|work\s+experience)\b', text, re.IGNORECASE):
        sections_matched += 1
    # 2. Education Section
    if re.search(r'\b(education|academic|university|degree|college|qualifications)\b', text, re.IGNORECASE):
        sections_matched += 1
    # 3. Skills Section
    if re.search(r'\b(skills|technologies|expertise|technical\s+skills|core\s+competenc|specialties)\b', text, re.IGNORECASE):
        sections_matched += 1
        
    # 4. Email check
    has_email = bool(re.search(r'[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}', text))
    
    return sections_matched >= 2 and has_email

def validate_and_extract(file_bytes: bytes, filename: str) -> str:
    """Validates the uploaded file is a valid PDF under 5MB and not image-only.
    Returns the extracted raw text on success.
    """
    # 1. Validate file extension
    if not filename.lower().endswith('.pdf'):
        raise IngestionError("Invalid file type. Only PDF files are allowed.", 400)

    # 2. Validate file size
    if len(file_bytes) > MAX_FILE_SIZE_BYTES:
        raise IngestionError("File size exceeds the 5MB limit.", 400)

    # 3. Extract text
    raw_text = extract_text_from_pdf(file_bytes)

    # 4. Reject image-only PDFs (empty or too short extracted text)
    if not raw_text or len(raw_text) < MIN_TEXT_LENGTH:
        raise IngestionError(
            "Scanned or image-only PDF detected. Please upload a PDF containing searchable text.",
        )

    # 5. Strict professional CV/resume structure validation
    if not is_valid_resume_structure(raw_text):
        raise IngestionError(
            "Please upload a valid professional CV/resume with standard sections (Experience, Education, Skills) and a contact email.",
            400,
        )

    return raw_text
