import requests
import sys

BASE_URL = "http://127.0.0.1:8000"

def run_tests():
    # 1. Get health
    try:
        health = requests.get(f"{BASE_URL}/health").json()
        print("Health check status:", health.get("status"))
    except Exception as e:
        print(f"Error connecting to backend: {e}")
        print("Make sure your FastAPI server is running on http://127.0.0.1:8000")
        sys.exit(1)

    # 2. Get active jobs
    jobs = requests.get(f"{BASE_URL}/jobs").json()
    if not jobs:
        print("No jobs found. Creating a test job...")
        job = requests.post(f"{BASE_URL}/jobs", params={
            "title": "Python Developer",
            "department": "Engineering",
            "job_description": "We need a Python developer who knows FastAPI and SQL."
        }).json()
        job_id = job["id"]
    else:
        job_id = jobs[0]["id"]
    print(f"Using Job ID: {job_id}")

    # 3. Get candidates for this job
    candidates_res = requests.get(f"{BASE_URL}/jobs/{job_id}/candidates").json()
    candidates = candidates_res.get("items", [])
    if not candidates:
        print("No candidates found. Please upload a PDF resume using the dashboard first or run test_scoring.py.")
        print("We need at least one candidate in the DB to test the recruitment endpoints.")
        # Let's see if we can query all candidates
        # For now, we will stop if no candidates. But wait! Let's check database.
        sys.exit(0)
    
    candidate = candidates[0]
    candidate_id = candidate["id"]
    print(f"Testing Candidate: {candidate.get('name') or candidate.get('filename')} (ID: {candidate_id})")

    # 4. Test status update
    print("\n--- Test 1: PATCH /candidates/{id}/status ---")
    status_payload = {
        "hr_status": "Screened",
        "changed_by": "verifier@company.com",
        "note": "Candidate resume checks out. Moving to screened."
    }
    res = requests.patch(f"{BASE_URL}/candidates/{candidate_id}/status", json=status_payload)
    print("Response status:", res.status_code)
    cand_data = res.json()
    print("New hr_status:", cand_data.get("hr_status"))
    print("Status history entry added:", "Yes" if "Screened" in cand_data.get("status_history", "") else "No")

    # 5. Test note addition
    print("\n--- Test 2: POST /candidates/{id}/notes ---")
    note_payload = {
        "note": "Completed initial screening interview. Strong Python coding skills.",
        "author": "interviewer@company.com"
    }
    res = requests.post(f"{BASE_URL}/candidates/{candidate_id}/notes", json=note_payload)
    print("Response status:", res.status_code)
    cand_data = res.json()
    print("Updated hr_notes:\n", cand_data.get("hr_notes"))

    # 6. Test score override
    print("\n--- Test 3: PATCH /candidates/{id}/score-override ---")
    override_payload = {
        "override_score": 92.5,
        "reason": "Outstanding open source contributions in FastAPI.",
        "changed_by": "manager@company.com"
    }
    res = requests.patch(f"{BASE_URL}/candidates/{candidate_id}/score-override", json=override_payload)
    print("Response status:", res.status_code)
    cand_data = res.json()
    print("New hr_score_override:", cand_data.get("hr_score_override"))
    
    # 7. Test timeline retrieval
    print("\n--- Test 4: GET /candidates/{id}/timeline ---")
    res = requests.get(f"{BASE_URL}/candidates/{candidate_id}/timeline")
    print("Response status:", res.status_code)
    timeline_data = res.json()
    print("Timeline entries count:", len(timeline_data.get("timeline", [])))
    for idx, entry in enumerate(timeline_data.get("timeline", [])):
        print(f"  [{idx + 1}] Type: {entry.get('type')} | Status: {entry.get('status')} | Changed By: {entry.get('changed_by')} | Note: {entry.get('note')}")

    # 8. Test sorting query params
    print("\n--- Test 5: GET /jobs/{id}/candidates with sort_by=total_score ---")
    res = requests.get(f"{BASE_URL}/jobs/{job_id}/candidates", params={
        "sort_by": "total_score",
        "order": "desc"
    }).json()
    sorted_items = res.get("items", [])
    print(f"Top candidate after override: {sorted_items[0].get('name') or sorted_items[0].get('filename')} with score {sorted_items[0].get('hr_score_override') or sorted_items[0].get('total_score')}")

if __name__ == "__main__":
    run_tests()
