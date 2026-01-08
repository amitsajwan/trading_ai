# PowerShell script to run all API tests
# Usage: .\scripts\test_all_apis.ps1

Write-Host "Running All API Tests..." -ForegroundColor Green
Write-Host ""

# Run all API test files
pytest `
    tests/e2e/test_dashboard_api.py `
    tests/e2e/test_trading_api.py `
    tests/e2e/test_control_api.py `
    -v `
    --tb=short

Write-Host ""
Write-Host "API Tests Complete!" -ForegroundColor Green



