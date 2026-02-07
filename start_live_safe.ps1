# Fail-Safe Live Mode Startup Script
# Ensures system is validated before starting

$ErrorActionPreference = "Stop"

Write-Host ""
Write-Host "========================================" -ForegroundColor Cyan
Write-Host "  FAIL-SAFE LIVE MODE STARTUP" -ForegroundColor Cyan
Write-Host "========================================" -ForegroundColor Cyan
Write-Host ""

# Check if virtual environment exists
if (-not (Test-Path ".venv\Scripts\Activate.ps1")) {
    Write-Host "❌ Virtual environment not found!" -ForegroundColor Red
    Write-Host "   Create it with: python -m venv .venv" -ForegroundColor Yellow
    exit 1
}

# Activate virtual environment
Write-Host "Activating virtual environment..." -ForegroundColor Gray
& .\.venv\Scripts\Activate.ps1

# Set PYTHONPATH
$env:PYTHONPATH = "$PWD\market_data\src"

# Run validated startup
Write-Host "Running validated startup..." -ForegroundColor Gray
Write-Host ""

python start_live_validated.py

if ($LASTEXITCODE -eq 0) {
    Write-Host ""
    Write-Host "========================================" -ForegroundColor Green
    Write-Host "  ✅ SYSTEM READY - ALL VALIDATED" -ForegroundColor Green
    Write-Host "========================================" -ForegroundColor Green
    Write-Host ""
    Write-Host "Dashboard: http://localhost:8008" -ForegroundColor Cyan
    Write-Host "API:       http://localhost:8004" -ForegroundColor Cyan
    Write-Host ""
    Write-Host "To monitor continuously (optional):" -ForegroundColor Yellow
    Write-Host "  python monitor_live_mode.py" -ForegroundColor Gray
    Write-Host ""
} else {
    Write-Host ""
    Write-Host "========================================" -ForegroundColor Red
    Write-Host "  ❌ STARTUP FAILED" -ForegroundColor Red
    Write-Host "========================================" -ForegroundColor Red
    Write-Host ""
    Write-Host "System stopped to prevent wrong data." -ForegroundColor Yellow
    Write-Host "Please fix the errors above." -ForegroundColor Yellow
    Write-Host ""
    exit 1
}
