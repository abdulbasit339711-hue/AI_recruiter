import os
import sys
import json

# ---------------------------------------------------------------------
# Disable any proxy env vars that might interfere with the Groq client
# (some versions of the groq library read these and pass them as a
#  `proxies` kw‑arg, which triggers the "unexpected keyword argument
#  'proxies'" error you observed).
# ---------------------------------------------------------------------
os.environ.pop('HTTP_PROXY', None)
os.environ.pop('HTTPS_PROXY', None)
os.environ.pop('NO_PROXY', None)

# Ensure the project root (parent of scripts/) is on PYTHONPATH so imports resolve correctly
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, PROJECT_ROOT)

# ---------------------------------------------------------------------
# Import the application components
# ---------------------------------------------------------------------
from app.database import SessionLocal
from app.models import Candidate
from app.scoring.engine import evaluate_candidate_pipeline

# ---------------------------------------------------------------------
# Open a DB session and fetch the candidate you want to test
# ---------------------------------------------------------------------
db = SessionLocal()
candidate_filename = 'Ali_Khan_Resume.pdf'  # change if you want another PDF
cand = db.query(Candidate).filter(Candidate.filename == candidate_filename).first()
if not cand:
    print(f'❌ Candidate "{candidate_filename}" not found – run test_scoring.py first to seed the DB.')
    sys.exit(1)

print(f'🚀 Running Groq evaluation for {cand.filename} (ID={cand.id}) …')
# ---------------------------------------------------------------------
# Run the full 3‑tier evaluation pipeline (Tier‑3 will now hit the real Groq API)
# ---------------------------------------------------------------------
evaluate_candidate_pipeline(cand.id, db)

# Refresh the object to get the newly stored results
db.refresh(cand)

# ---------------------------------------------------------------------
# Print a concise, human‑readable result
# ---------------------------------------------------------------------
print('\n=== REAL GROQ RESULT ===========================')
print(f'Summary : {cand.summary}')
print('Evidence:')
for ev in json.loads(cand.evidence or '[]'):
    print(f'  • {ev}')
print('==============================================')

# Close the DB session
db.close()
