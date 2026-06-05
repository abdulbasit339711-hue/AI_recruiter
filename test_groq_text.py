import os
import sys
import json
from dotenv import load_dotenv

# Load environment variables (including GROQ_API_KEY)
load_dotenv(os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', '..', '..', '.env'))

# Ensure proxies are cleared (just in case)
for var in ["HTTP_PROXY", "HTTPS_PROXY", "http_proxy", "https_proxy", "NO_PROXY", "no_proxy"]:
    os.environ.pop(var, None)

# Add project root to PYTHONPATH for imports
PROJECT_ROOT = r"C:\Users\basit\.gemini\antigravity-ide\scratch\ai-recruiter"
sys.path.append(PROJECT_ROOT)

# Import the necessary components
from app.database import SessionLocal
from app.models import Candidate, Job
from app.llm.groq_client import evaluate_with_llm

# Open a DB session and fetch a candidate and its job
db = SessionLocal()
# Pick the first candidate (you can change the filename if desired)
candidate = db.query(Candidate).filter(Candidate.filename == "Ali_Khan_Resume.pdf").first()
if not candidate:
    print("❌ Candidate not found – ensure test_scoring.py has been run to seed the DB.")
    sys.exit(1)

job = db.query(Job).filter(Job.id == candidate.job_id).first()
if not job:
    print("❌ Job not found for the candidate.")
    sys.exit(1)

print(f"🚀 Sending extracted resume text to Groq for candidate: {candidate.filename}")
print(f"   Job title: {job.title}\n")

# Call the LLM evaluation (this will use the real Groq API if key is set)
result = evaluate_with_llm(resume_text=candidate.raw_text, jd_text=job.job_description)

print("\n=== GROQ RESPONSE =========================")
print(json.dumps(result, indent=2))
print("==========================================")

db.close()
