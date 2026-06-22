import argparse
import os
import sys
import json
from datetime import datetime, timezone

# Add the project root (parent of scripts/) to sys.path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.database import engine, Base, SessionLocal, run_migrations
from app.models import Candidate, Job
from app.scoring.engine import evaluate_candidate_pipeline

# 1. Define High-Fidelity Mock Resumes
MOCK_CANDIDATES = [
    {
        "filename": "Ali_Khan_Resume.pdf",
        "email": "ali.khan@email.com",
        "job_index": 0,  # Assign to Python Job
        "raw_text": """
ALI KHAN
ali.khan@email.com | (555) 123-4567 | San Francisco, CA

EDUCATION
Bachelor of Science in Computer Science, Stanford University (2018 - 2022)

WORK EXPERIENCE
Senior Backend Developer | TechCorp (2022 - Present)
- Designed and maintained high-performance microservices using Python and FastAPI.
- Implemented robust database architectures with SQLAlchemy, PostgreSQL, and SQLite.
- Fully automated deployment pipelines using Docker, Kubernetes, and AWS (S3, EC2, RDS).
- Designed secure RESTful API integrations and optimized database query bottlenecks.

SKILLS
Programming Languages: Python, SQL, Go, JavaScript
Frameworks: FastAPI, Django, PyTest
Tools & Devops: Docker, Kubernetes, AWS, S3, RDS, Lambda, Git
        """
    },
    {
        "filename": "Sara_Ahmed_Resume.pdf",
        "email": "sara.ahmed@email.com",
        "job_index": 0,  # Assign to Python Job
        "raw_text": """
SARA AHMED
sara.ahmed@email.com | +1-202-555-0143 | Austin, TX

PROFESSIONAL SUMMARY
Backend Software Engineer with 3+ years of experience specialized in building clean, scalable backend systems using Python, Django, and Flask.

EDUCATION
Master of Science in Software Engineering, University of Texas (2019 - 2021)

EXPERIENCE
Python Developer | AppForge (2021 - Present)
- Developed and deployed secure REST APIs using Django REST Framework and Python.
- Structured databases with SQLAlchemy and SQLite, reducing retrieval times.
- Managed containerized services with Docker and pushed logs to AWS CloudWatch.
- Conducted unit testing using PyTest, reaching 90% code coverage.

SKILLS
Languages: Python, JavaScript, SQL
Web: Django, Flask, HTML5, CSS3, REST APIs
DevOps & Cloud: Git, Docker, AWS EC2, PostgreSQL
        """
    },
    {
        "filename": "John_Doe_Resume.pdf",
        "email": "john.doe@email.com",
        "job_index": 0,  # Assign to Python Job
        "raw_text": """
JOHN DOE - FRONTEND DEVELOPER
john.doe@email.com | 555-987-6543 | New York, NY

PROFESSIONAL EXPERIENCE
Senior React Engineer | PixelPerfect UI (2020 - Present)
- Built interactive single page applications using React, Next.js, and TypeScript.
- Styled highly responsive interfaces with Tailwind CSS and CSS Grid.
- Wrote basic automation scripts in Python to scrape UI assets.

EDUCATION
Bachelor of Arts in Graphic Design, Pratt Institute (2016 - 2020)

TECHNICAL SKILLS
Web Core: HTML5, CSS3, JavaScript, TypeScript
Frameworks: React.js, Next.js, Vue.js, Redux
Styling: TailwindCSS, SASS, CSS modules, Figma
Scripting: Python (basic automation)
        """
    },
    {
        "filename": "Emily_Smith_Resume.pdf",
        "email": "emily.smith@email.com",
        "job_index": 1,  # Assign to Project Manager Job
        "raw_text": """
EMILY SMITH
emily.smith@email.com | +44 20 7946 0958 | London, UK

SUMMARY
Dynamic and result-oriented Technical Project Manager with 5+ years of experience leading cross-functional teams using Agile, Scrum, and Kanban methodologies.

EXPERIENCE
Technical Program Manager | CloudStream (2021 - Present)
- Led a team of 15 backend developers, planning sprints and conducting daily standups.
- Managed software project lifecycles using Jira, Confluence, and Asana.
- Spearheaded delivery of 3 major cloud migrations on time and within budget.

EDUCATION
Master of Business Administration (MBA), London Business School (2018 - 2020)

CORE competencies
Project Management, Agile Methodologies, Scrum, JIRA, Confluence, Risk Management, Stakeholder Communication
        """
    },
    {
        "filename": "Zayn_Malik_Resume.pdf",
        "email": "zayn.malik@email.com",
        "job_index": 0,  # Assign to Python Job
        "raw_text": """
ZAYN MALIK - JUNIOR ENGINEER
zayn.malik@email.com | Toronto, Canada

SUMMARY
Recent graduate eager to kickstart a career as a junior software engineer. 

EDUCATION
High School Diploma - Tech Academy (2024)

TECHNICAL EXPOSURE
Languages: Python (beginner), HTML
Projects: Built a simple CLI calculator in python, and a static profile website.
        """
    }
]

# 2. Define target JDs to insert
MOCK_JOBS = [
    {
        "title": "Senior Python Developer",
        "department": "Engineering",
        "job_description": """
We are seeking a Senior Python Developer with strong backend engineering expertise to build and optimize scalable services. You will design database schemas, write clean RESTful APIs, and integrate ML/LLM microservices.
Required: Python, FastAPI/Django, SQL, AWS, Docker. 4+ years experience.
        """,
        "llm_prompt": "Score candidates focusing strongly on Python design patterns, FastAPI REST API structure, and database schema efficiency."
    },
    {
        "title": "Technical Project Manager",
        "department": "Product Management",
        "job_description": """
Looking for a Technical Project Manager with experience leading software teams using Agile, Scrum, and Kanban frameworks. You will coordinate deliverables, manage JIRA boards, and communicate risks to stakeholders.
Required: Agile, Scrum, Kanban, JIRA, stakeholder communication. 3+ years experience.
        """,
        "llm_prompt": "Evaluate candidate's leadership skills, agile framework proficiency, and project execution records."
    }
]

def run_local_evaluation(reset_db: bool = False):
    print("=" * 70)
    print("      AI-RECRUITER SCORING ENGINE - MULTI-JOB EVALUATION")
    print("=" * 70)
    
    # 1. Initialize tables
    print("[1/4] Preparing SQLite database tables...")
    if reset_db:
        print("      Reset requested: dropping all tables before seeding demo data.")
        Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)
    run_migrations()
    
    db = SessionLocal()
    
    # 2. Insert mock Jobs
    print("[2/4] Populating database with target Job Profiles...")
    jobs = []
    for mj in MOCK_JOBS:
        j = Job(
            title=mj["title"],
            department=mj["department"],
            job_description=mj["job_description"],
            llm_prompt=mj["llm_prompt"],
            status="Active",
            created_at=datetime.now(timezone.utc).isoformat()
        )
        db.add(j)
        jobs.append(j)
    db.commit()
    
    for j in jobs:
        db.refresh(j)
        print(f"      Inserted Job Profile ID {j.id}: '{j.title}' ({j.department})")
        
    print("-" * 70)
    
    # 3. Insert mock candidates linked to specific Job IDs
    print("[3/4] Ingesting candidates assigned to target jobs...")
    candidates = []
    for mock in MOCK_CANDIDATES:
        assigned_job = jobs[mock["job_index"]]
        c = Candidate(
            filename=mock["filename"],
            email=mock["email"],
            raw_text=mock["raw_text"],
            job_id=assigned_job.id,
            status="Pending",
            created_at=datetime.now(timezone.utc).isoformat()
        )
        db.add(c)
        candidates.append(c)
    db.commit()
    
    for c in candidates:
        db.refresh(c)
        assigned_job = db.query(Job).filter(Job.id == c.job_id).first()
        print(f"      Ingested candidate: '{c.filename}' linked to Job ID {c.job_id} ('{assigned_job.title}')")
        
    print("-" * 70)
    
    # 4. Execute scoring engine pipelines
    print("[4/4] Triggering job-specific 3-Tier scoring processes...")
    for c in candidates:
        print(f"      Scoring {c.filename} against its job requirements...")
        evaluate_candidate_pipeline(c.id, db)
        
    # 5. Output separate ranked leaderboards per job
    print("\n" + "=" * 80)
    print("                   CONSOLIDATED MULTI-JOB LEADERBOARDS")
    print("=" * 80)
    
    for job in jobs:
        print(f"\n[JOB] POSITION: '{job.title}' ({job.department}) - Status: {job.status}")
        print("=" * 75)
        print(f"{'Rank':<5} | {'Candidate Name':<18} | {'Total':<6} | {'Tier 1':<6} | {'Tier 2':<6} | {'Tier 3':<6} | {'Status':<9}")
        print("-" * 75)
        
        ranked_candidates = db.query(Candidate).filter(Candidate.job_id == job.id).order_by(Candidate.total_score.desc()).all()
        
        if not ranked_candidates:
            print("      No applicants scored for this job profile.")
        else:
            for rank, cand in enumerate(ranked_candidates, 1):
                name = cand.filename.replace("_Resume.pdf", "").replace("_", " ")
                print(f"{rank:<5} | {name:<18} | {cand.total_score:<6.1f} | {cand.tier1:<6.1f} | {cand.tier2:<6.1f} | {cand.tier3:<6.1f} | {cand.status:<9}")
                
        print("=" * 75)
        
    # Print detail breakdowns
    print("\nDetailed Qualitative LLM Breakdowns:")
    for job in jobs:
        print(f"\n>>> Breakdown for Applicants to '{job.title}':")
        ranked_candidates = db.query(Candidate).filter(Candidate.job_id == job.id).order_by(Candidate.total_score.desc()).all()
        for cand in ranked_candidates:
            name = cand.filename.replace("_Resume.pdf", "").replace("_", " ")
            print(f"    * {name} (Total Score: {cand.total_score:.1f} / 100):")
            print(f"      - Summary : {cand.summary}")
            try:
                evidences = json.loads(cand.evidence) if cand.evidence else []
                print("      - Evidence:")
                for ev in evidences:
                    print(f"        * {ev}")
            except Exception:
                print(f"      - Evidence: {cand.evidence}")
                
    db.close()
    print("=" * 70)

if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Run a local scoring demo. Keeps existing database data by default."
    )
    parser.add_argument(
        "--reset-db",
        action="store_true",
        help="Drop and recreate all tables before running the demo.",
    )
    args = parser.parse_args()
    run_local_evaluation(reset_db=args.reset_db)
