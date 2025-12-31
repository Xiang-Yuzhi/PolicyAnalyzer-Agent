# Set environment variables to suppress warnings
$env:USER_AGENT = "EFundPolicyAgent/1.0"

# Check if venv exists and activate
if (Test-Path ".\venv\Scripts\Activate.ps1") {
    Write-Host "Activating virtual environment..." -ForegroundColor Cyan
    . .\venv\Scripts\Activate.ps1
}
else {
    Write-Host "Warning: Virtual environment 'venv' not found. Ensure it is established." -ForegroundColor Yellow
}

# Run the Streamlit app
Write-Host "Starting EFund Policy Analysis Agent..." -ForegroundColor Green
python -m streamlit run app.py

# --- Post-execution logic ---
Write-Host "`nStreamlit has stopped." -ForegroundColor Cyan

# Check for Git changes
if (Test-Path ".git") {
    $status = git status --porcelain
    if ($status) {
        Write-Host "--------------------------------------------------" -ForegroundColor Yellow
        Write-Host "REMINDER: You have uncommitted changes in Git." -ForegroundColor Yellow
        Write-Host "Don't forget to commit and upload your updates!" -ForegroundColor Cyan
        Write-Host "--------------------------------------------------" -ForegroundColor Yellow
    }
}

Write-Host "Press [Enter] to close this window..." -ForegroundColor Gray
$null = Read-Host