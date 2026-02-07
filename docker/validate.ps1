# Docker Compose Validation Script
# Tests all compose file combinations to ensure they work correctly

Write-Host "Docker Compose Validation Script" -ForegroundColor Cyan
Write-Host "==================================" -ForegroundColor Cyan

# Function to test compose configuration
function Test-ComposeConfig {
    param(
        [string]$Description,
        [string]$Command
    )

    Write-Host "Testing $Description... " -NoNewline
    try {
        $result = Invoke-Expression "$Command 2>&1"
        if ($LASTEXITCODE -eq 0) {
            Write-Host "PASS" -ForegroundColor Green
            return $true
        } else {
            Write-Host "FAIL" -ForegroundColor Red
            Write-Host "Error: $result" -ForegroundColor Red
            return $false
        }
    }
    catch {
        Write-Host "FAIL" -ForegroundColor Red
        Write-Host "Exception: $($_.Exception.Message)" -ForegroundColor Red
        return $false
    }
}

# Test individual files
Write-Host "`nTesting Individual Files:" -ForegroundColor Yellow
Write-Host "----------------------------" -ForegroundColor Yellow

$mainTest = Test-ComposeConfig "Main compose file" "docker-compose -f docker-compose.yml config --quiet"
$dataTest = Test-ComposeConfig "Data services only" "docker-compose -f docker-compose.data.yml config --quiet"

# Test override combinations
Write-Host "`nTesting Override Combinations:" -ForegroundColor Yellow
Write-Host "----------------------------------" -ForegroundColor Yellow

$devTest = Test-ComposeConfig "Main + Development overrides" "docker-compose -f docker-compose.yml -f docker-compose.override.yml config --quiet"
$mockTest = Test-ComposeConfig "Main + Mock overrides" "docker-compose -f docker-compose.yml -f docker-compose.mock.yml config --quiet"

# Test service counts
Write-Host "`nService Count Validation:" -ForegroundColor Yellow
Write-Host "-----------------------------" -ForegroundColor Yellow

$mainServices = (docker-compose -f docker-compose.yml config --services | Measure-Object -Line).Lines
$dataServices = (docker-compose -f docker-compose.data.yml config --services | Measure-Object -Line).Lines
$devServices = (docker-compose -f docker-compose.yml -f docker-compose.override.yml config --services | Measure-Object -Line).Lines
$mockServices = (docker-compose -f docker-compose.yml -f docker-compose.mock.yml config --services | Measure-Object -Line).Lines

Write-Host "Main compose: $mainServices services"
Write-Host "Data only: $dataServices services"
Write-Host "Dev overrides: $devServices services"
Write-Host "Mock overrides: $mockServices services"

# Validate service counts make sense
$serviceCountValid = ($mainServices -gt $dataServices) -and ($devServices -eq $mainServices) -and ($mockServices -eq $mainServices)

if ($serviceCountValid) {
    Write-Host "Service counts are consistent" -ForegroundColor Green
} else {
    Write-Host "Service count mismatch detected" -ForegroundColor Red
    exit 1
}

# Test environment variable overrides in mock file
Write-Host "`nTesting Environment Overrides:" -ForegroundColor Yellow
Write-Host "----------------------------------" -ForegroundColor Yellow

# Check if mock environment variables are properly set
$mockConfig = docker-compose -f docker-compose.yml -f docker-compose.mock.yml config
$mockEnvValid = $mockConfig | Select-String -Pattern "TRADING_PROVIDER: mock" -Quiet

if ($mockEnvValid) {
    Write-Host "Mock environment variables applied" -ForegroundColor Green
} else {
    Write-Host "Mock environment variables missing" -ForegroundColor Red
    exit 1
}

# Overall result
$allTestsPass = $mainTest -and $dataTest -and $devTest -and $mockTest -and $serviceCountValid -and $mockEnvValid

if ($allTestsPass) {
    Write-Host "`nAll validations passed!" -ForegroundColor Green
    Write-Host "Docker Compose configuration is ready for use." -ForegroundColor Green
} else {
    Write-Host "`nSome validations failed!" -ForegroundColor Red
    exit 1
}