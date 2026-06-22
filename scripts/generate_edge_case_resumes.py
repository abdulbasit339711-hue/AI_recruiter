from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.pdfgen import canvas
from PIL import Image, ImageDraw
import os

# Create output directory
os.makedirs("edge_case_resumes", exist_ok=True)

styles = getSampleStyleSheet()


def create_text_pdf(filename, content):
    pdf = SimpleDocTemplate(filename)
    story = []
    for line in content.split("\n"):
        line = line.strip()
        if line:
            story.append(Paragraph(line, styles["Normal"]))
            story.append(Spacer(1, 6))
    pdf.build(story)

# 1. EMPTY PDF
create_text_pdf("edge_case_resumes/empty_resume.pdf", "")
print("Created empty_resume.pdf")

# 2. MISSING PHONE
create_text_pdf(
    "edge_case_resumes/missing_phone.pdf",
    """
    John Doe

    Email: john@example.com

    Education
    BS Computer Science

    Experience
    Python Developer

    Skills
    Python
    FastAPI
    SQL
    """
)
print("Created missing_phone.pdf")

# 3. MISSING EMAIL
create_text_pdf(
    "edge_case_resumes/missing_email.pdf",
    """
    John Doe

    Phone: 1234567890

    Education
    BS Computer Science

    Experience
    Backend Developer

    Skills
    Python
    FastAPI
    PostgreSQL
    """
)
print("Created missing_email.pdf")

# 4. MISSING SKILLS SECTION
create_text_pdf(
    "edge_case_resumes/missing_skills_section.pdf",
    """
    John Doe

    Email: john@example.com
    Phone: 1234567890

    Education
    BS Computer Science

    Experience

    Software Engineer

    Developed APIs using FastAPI.
    """
)
print("Created missing_skills_section.pdf")

# 5. UNRELATED SKILLS (Graphic Designer)
create_text_pdf(
    "edge_case_resumes/unrelated_graphic_designer.pdf",
    """
    Sarah Khan

    Email: sarah@example.com
    Phone: 1234567890

    Education
    BFA Graphic Design

    Experience
    Senior Graphic Designer

    Skills
    Photoshop
    Illustrator
    Figma
    Branding
    UI Mockups
    Print Design
    """
)
print("Created unrelated_graphic_designer.pdf")

# 6. IMAGE-ONLY PDF
img = Image.new("RGB", (1000, 1400), color="white")
draw = ImageDraw.Draw(img)
draw.text((50, 50), "This is a scanned resume image.", fill="black")
img_path = "edge_case_resumes/temp_scan.png"
img.save(img_path)
pdf_path = "edge_case_resumes/image_only_resume.pdf"
c = canvas.Canvas(pdf_path)
c.drawImage(img_path, 0, 0, width=595, height=842)
c.save()
print("Created image_only_resume.pdf")

# 7. CORRUPTED PDF
with open("edge_case_resumes/corrupted_resume.pdf", "wb") as f:
    f.write(b"This is not a valid PDF file.")
print("Created corrupted_resume.pdf")

# 8. OVERSIZED PDF (>5MB)
large_text = ("Python FastAPI Docker AWS Kubernetes\n" * 1000)
oversized_path = "edge_case_resumes/oversized_resume.pdf"
c = canvas.Canvas(oversized_path)
for page in range(250):
    c.drawString(20, 800, large_text[:3000])
    c.showPage()
c.save()
# Ensure size >5MB
actual_size = os.path.getsize(oversized_path)
while actual_size < (6 * 1024 * 1024):
    with open(oversized_path, "ab") as f:
        f.write(os.urandom(500000))
    actual_size = os.path.getsize(oversized_path)
print(f"Created oversized_resume.pdf ({actual_size / (1024*1024):.2f} MB)")

# 9. GARBLED OCR PDF
garbled_text = """
Ø¥Ø§Ù„Ù„Ù‡Ù…Ù†ÙˆØ§Ø±Ø¯Ø§Ù„Ø¨ÙŠØ§Ù†
Ã±Ã§Ã¥ÃµÃ¸Ã¶Ã¤Ã¥
Ð°Ð±Ð²Ð³Ð´ÐµÐ¶Ð·
"""
create_text_pdf("edge_case_resumes/garbled_ocr_resume.pdf", garbled_text)
print("Created garbled_ocr_resume.pdf")

# 10. VERY SHORT RESUME
create_text_pdf(
    "edge_case_resumes/very_short_resume.pdf",
    """
    John

    Need job.
    """
)
print("Created very_short_resume.pdf")

print("\nAll edge-case resumes generated.")
