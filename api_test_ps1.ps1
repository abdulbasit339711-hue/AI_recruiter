# PowerShell curl.exe smoke-test for the AI Recruiter backend
# ------------------------------------------------------------
# Prerequisites:
#   1. FastAPI server must be running on http://127.0.0.1:8000
#   2. PDF test files have been generated (run generate_test_resumes.py)
#   3. Windows 10+ includes the native `curl.exe` executable
# ------------------------------------------------------------

$BaseUrl = "http://127.0.0.1:8000"

# ----------------------------------------------------------------
# 1️⃣ Create the AI Engineer job (parameters are passed via query)
# ----------------------------------------------------------------
Write-Host "`n=== 1️⃣ Create Job (AI Engineer) ==="

$JobUrl = "$BaseUrl/jobs?" +
    "title=AI%20Engineer&" +
    "department=Engineering&" +
    "job_description=AI%20Engineer%20with%20experience%20of%201%20year%20or%20less%20with%20proficiency%20with%20LLMs%20and%20Agentic%20workflows"

# FastAPI returns JSON – capture it and extract the id
$JobJson = curl.exe -s -X POST $JobUrl
if ($JobJson -match '"id"\s*:\s*([0-9]+)') {
    $JobId = $Matches[1]
    Write-Host "Created job - ID: $JobId"
} else {
    Write-Host "⚠️  Job creation failed. Response:"
    Write-Host $JobJson

    # Try to locate an existing AI Engineer job
    Write-Host "Attempting to locate an existing AI Engineer job..."
    $JobsList = curl.exe -s "$BaseUrl/jobs"
    if ($JobsList -match '"title"\s*:\s*"AI Engineer".*?"id"\s*:\s*([0-9]+)') {
        $JobId = $Matches[1]
        Write-Host "Found existing job - ID: $JobId"
    } else {
        Throw "Unable to obtain a job ID - aborting script."
    }
}

# ---------------------------------------------------------------
# 2️⃣ Upload a test resume PDF (choose any file from test_resumes/)
# ---------------------------------------------------------------
Write-Host "`n=== 2️⃣ Upload a test resume ==="
$PdfPath = "test_resumes/04_ats_score_55.pdf"   # change if you want another file
$UploadUrl = "$BaseUrl/upload?job_id=$JobId"

# curl.exe -F creates a multipart/form-data request
$UploadJson = curl.exe -s -X POST $UploadUrl -F "file=@$PdfPath"

if ($UploadJson -match '"id"\s*:\s*([0-9]+)') {
    $CandidateId = $Matches[1]
    Write-Host "Uploaded resume - Candidate ID: $CandidateId"
    Write-Host "Full upload JSON response:"
    $UploadJson | python -m json.tool
} else {
    Write-Host "⚠️  Upload failed. Response:"
    Write-Host $UploadJson
    Throw "Upload failed - aborting script."
}

# --------------------------------------------------------------
# 3️⃣ Retrieve the candidate record (verify scoring output)
# --------------------------------------------------------------
Write-Host "`n=== 3️⃣ Retrieve candidate record ==="
$CandidateJson = curl.exe -s -X GET "$BaseUrl/candidates/$CandidateId"
Write-Host "Candidate GET JSON response:"
$CandidateJson | python -m json.tool

# --------------------------------------------------------------
# 4️⃣ List all jobs (quick sanity check)
# --------------------------------------------------------------
Write-Host "`n=== 4️⃣ List all jobs ==="
$JobsJson = curl.exe -s -X GET "$BaseUrl/jobs"
$JobsJson | python -m json.tool

# --------------------------------------------------------------
# 5️⃣ (Optional) Soft-archive the job – uncomment to clean up
# --------------------------------------------------------------
# curl.exe -s -X DELETE "$BaseUrl/jobs/$JobId"
# Write-Host "Job $JobId archived (soft-deleted)."
