from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer
from reportlab.lib.styles import getSampleStyleSheet
import os

os.makedirs("test_resumes", exist_ok=True)

styles = getSampleStyleSheet()

resumes = [
    {
        "filename": "01_ats_score_10.pdf",
        "content": """
        John

        Looking for job.

        Worked somewhere.

        Good communication skills.
        """
    },
    {
        "filename": "02_ats_score_25.pdf",
        "content": """
        John Doe

        Email: john@example.com

        Experience
        Worked as support executive.

        Skills
        MS Office
        Communication
        """
    },
    {
        "filename": "03_ats_score_40.pdf",
        "content": """
        John Doe
        Email: john@example.com
        Phone: 1234567890

        Education
        BS Computer Science

        Experience
        Technical Support Engineer

        Skills
        Linux
        Networking
        Python
        """
    },
    {
        "filename": "04_ats_score_55.pdf",
        "content": """
        John Doe
        Email: john@example.com
        Phone: 1234567890

        Education
        BS Computer Science

        Experience
        Software Engineer - 2 Years

        Skills
        Python
        FastAPI
        SQL
        Docker
        Git
        """
    },
    {
        "filename": "05_ats_score_70.pdf",
        "content": """
        John Doe
        Email: john@example.com
        Phone: 1234567890

        Education
        BS Computer Science

        Experience
        Backend Developer

        Built REST APIs using FastAPI.
        Reduced API response time by 40%.

        Skills
        Python
        FastAPI
        PostgreSQL
        Docker
        Git
        Linux
        CI/CD
        """
    },
    {
        "filename": "06_ats_score_85.pdf",
        "content": """
        John Doe
        Email: john@example.com
        Phone: 1234567890

        Education
        BS Computer Science

        Experience

        Senior Backend Engineer

        Designed microservices architecture.

        Increased system throughput by 60%.

        Built CI/CD pipelines.

        Managed cloud infrastructure.

        Skills

        Python
        FastAPI
        PostgreSQL
        Docker
        Kubernetes
        AWS
        Terraform
        GitHub Actions
        """
    },
    {
        "filename": "07_ats_score_100.pdf",
        "content": """
        John Doe
        Email: john@example.com
        Phone: 1234567890

        Education

        BS Computer Science
        AWS Certified Solutions Architect
        CKA Certified Kubernetes Administrator

        Experience

        Lead Platform Engineer

        Architected distributed systems serving 5M users.

        Reduced cloud costs by 35%.

        Implemented Kubernetes clusters.

        Built CI/CD pipelines using GitHub Actions.

        Created Infrastructure as Code using Terraform.

        Skills

        Python
        FastAPI
        PostgreSQL
        Docker
        Kubernetes
        AWS
        Terraform
        GitHub Actions
        Microservices
        DevOps
        Cloud Architecture
        """
    }
]

for resume in resumes:
    pdf = SimpleDocTemplate(
        f"test_resumes/{resume['filename']}"
    )

    story = []

    for line in resume["content"].split("\n"):
        line = line.strip()
        if line:
            story.append(Paragraph(line, styles["Normal"]))
            story.append(Spacer(1, 6))

    pdf.build(story)

print("Generated test resumes successfully.")
