# Playwright Test Runner
# Run from: dashboard/modular_ui directory

Set-Location "$PSScriptRoot\..\..\modular_ui"

Write-Host "========================================="
Write-Host "Running Playwright Tests"
Write-Host "========================================="
Write-Host ""

# Test files
$testDir = "$PSScriptRoot\tests"
$configFile = "$PSScriptRoot\playwright.config.ts"

Write-Host "Test directory: $testDir"
Write-Host "Config file: $configFile"
Write-Host ""

if (-not (Test-Path "$testDir")) {
    Write-Host "❌ Test directory not found: $testDir"
    exit 1
}

if (-not (Test-Path "$configFile")) {
    Write-Host "❌ Config file not found: $configFile"
    exit 1
}

# Run tests
Write-Host "Running all tests..."
npx playwright test --config $configFile --reporter=list --timeout=90000 --project=chromium

Write-Host ""
Write-Host "========================================="
Write-Host "Tests Complete"
Write-Host "========================================="
