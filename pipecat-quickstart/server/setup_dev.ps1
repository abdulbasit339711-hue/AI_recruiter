# Pipecat AI-Recruiter Native Windows Setup
# This script installs dependencies and checks environment variables for native execution.

Write-Host "--- AI-Recruiter Native Windows Setup ---" -ForegroundColor Cyan

# 1. Check for uv
if (!(Get-Command uv -ErrorAction SilentlyContinue)) {
    Write-Host "[-] 'uv' not found. Installing uv..." -ForegroundColor Yellow
    powershell -ExecutionPolicy ByPass -c "irm https://astral.sh/uv/install.ps1 | iex"
    $env:Path += ";$env:USERPROFILE\.cargo\bin"
} else {
    Write-Host "[+] 'uv' found." -ForegroundColor Green
}

# 2. Sync dependencies
Write-Host "[*] Syncing dependencies (Native Windows x86_64)..." -ForegroundColor Cyan
try {
    uv sync --locked
} catch {
    Write-Host "[!] uv sync failed. Attempting to fix onnxruntime..." -ForegroundColor Yellow
    # Common fix for onnxruntime issues on Windows
    uv pip install onnxruntime --upgrade
    uv sync --locked
}

# 3. Check for Visual C++ Redistributable (Required by onnxruntime/Silero VAD)
# Checking for 2015-2022 Redistributable
$vc_check = Get-ItemProperty -Path "HKLM:\SOFTWARE\Microsoft\VisualStudio\14.0\VC\Runtimes\x64" -ErrorAction SilentlyContinue
if (!$vc_check) {
    Write-Host "[!] Warning: Microsoft Visual C++ Redistributable not detected." -ForegroundColor Yellow
    Write-Host "    Silero VAD (onnxruntime) requires this. Download here:" -ForegroundColor White
    Write-Host "    https://aka.ms/vs/17/release/vc_redist.x64.exe" -ForegroundColor Cyan
} else {
    Write-Host "[+] Visual C++ Redistributable detected." -ForegroundColor Green
}

# 4. Check .env
if (!(Test-Path .env)) {
    if (Test-Path .env.example) {
        Write-Host "[*] .env not found. Creating from .env.example..." -ForegroundColor Yellow
        Copy-Item .env.example .env
    } else {
        Write-Host "[!] .env.example not found. Please create a .env file." -ForegroundColor Red
        exit
    }
}

# 5. Validate API Keys
$env_content = Get-Content .env
$missing_keys = @()
foreach ($key in @("GROQ_API_KEY", "DEEPGRAM_API_KEY", "CARTESIA_API_KEY")) {
    if (!($env_content -match "$key=")) {
        $missing_keys += $key
    }
}

if ($missing_keys.Count -gt 0) {
    Write-Host "[!] Warning: The following keys are missing in .env: $($missing_keys -join ', ')" -ForegroundColor Yellow
} else {
    Write-Host "[+] Basic API keys found." -ForegroundColor Green
}

Write-Host "`n--- Setup Complete ---" -ForegroundColor Cyan
Write-Host "To start the LiveKit Recruiter Bot:" -ForegroundColor White
Write-Host "  uv run runner.py" -ForegroundColor Green
Write-Host "`nTo start the Local Audio Bot (Host Mic/Speakers):" -ForegroundColor White
Write-Host "  uv run local_bot.py" -ForegroundColor Green
