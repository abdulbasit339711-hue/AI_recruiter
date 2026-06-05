#!/usr/bin/env bash
# ------------------------------------------------------------
# Simple curl smoke‑test script for the AI Recruiter backend.
# Prerequisites:
#   1. The FastAPI server must be running on http://127.0.0.1:8000
#   2. The test PDFs have been generated (run generate_test_resumes.py)
#   3. `curl` is available (Windows 10+ includes it, or use Git‑bash).
# ------------------------------------------------------------

BASE_URL="http://127.0.0.1:8000"

# -------------------------------------------------------------------
# 1️⃣ Create a job (AI Engineer – 1 yr or less, LLM & Agentic workflow)
# -------------------------------------------------------------------
JOB_RESPONSE=$(curl -s -X POST "$BASE_URL/jobs" \
    -H "Content-Type: application/json" \
    -d '{
        "title": "AI Engineer",
        "department": "Engineering",
        "job_description": "AI Engineer with experience of 1 year or less, proficient with LLMs and Agentic workflows.",
        "llm_prompt": null
    }')

# Extract the job ID from the JSON response (requires jq – install if missing)
if command -v jq >/dev/null 2>&1; then
    JOB_ID=$(echo "$JOB_RESPONSE" | jq -r '.id')
else
    # Fallback: naive extraction (works for simple JSON)
    JOB_ID=$(echo "$JOB_RESPONSE" | sed -n 's/.*"id": *\([0-9]*\).*/\1/p')
fi

echo "Created job – ID: $JOB_ID"

# ---------------------------------------------------------------
# 2️⃣ Upload a test resume PDF (choose any from test_resumes/ )
# ---------------------------------------------------------------
PDF_PATH="test_resumes/04_ats_score_55.pdf"   # expected score ≈55

UPLOAD_RESPONSE=$(curl -s -X POST "$BASE_URL/upload?job_id=$JOB_ID" \
    -H "Accept: application/json" \
    -F "file=@$PDF_PATH")

# Show the full JSON response
echo "Upload response:" && echo "$UPLOAD_RESPONSE" | python -m json.tool

# Extract candidate ID for later lookup
if command -v jq >/dev/null 2>&1; then
    CANDIDATE_ID=$(echo "$UPLOAD_RESPONSE" | jq -r '.id')
else
    CANDIDATE_ID=$(echo "$UPLOAD_RESPONSE" | sed -n 's/.*"id": *\([0-9]*\).*/\1/p')
fi

echo "Candidate created – ID: $CANDIDATE_ID"

# ----------------------------------------------------------
# 3️⃣ Retrieve the candidate record (to verify scoring output)
# ----------------------------------------------------------
CANDIDATE_GET=$(curl -s -X GET "$BASE_URL/candidates/$CANDIDATE_ID")

echo "Candidate GET response:" && echo "$CANDIDATE_GET" | python -m json.tool

# ----------------------------------------------------------
# 4️⃣ List all jobs (quick sanity check)
# ----------------------------------------------------------
JOBS_LIST=$(curl -s -X GET "$BASE_URL/jobs")

echo "Jobs list:" && echo "$JOBS_LIST" | python -m json.tool

# ----------------------------------------------------------
# 5️⃣ Clean‑up (optional): delete the job (soft‑archive)
# ----------------------------------------------------------
# curl -X DELETE "$BASE_URL/jobs/$JOB_ID"

# End of script
