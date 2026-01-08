<#
PowerShell runbook to start local dev environment in HISTORICAL replay mode.
Usage examples:
  .\scripts\start_historical.ps1 -Source synthetic -Speed 1.0 -Ticks:$true
  .\scripts\start_historical.ps1 -Source "C:\data\bnf.csv" -From 2024-01-15 -Ticks:$true -Speed 1.0
#>
param(
    [string]$Source = "synthetic",
    [float]$Speed = 1.0,
    [switch]$Ticks = $false,
    [string]$From = ""
)

Write-Host "Starting infra (MongoDB + Redis)..."
docker compose up -d mongodb redis

# Wait for Redis
$maxAttempts = 20
$attempt = 0
while ($attempt -lt $maxAttempts) {
    try {
        python - <<'PY' -q
import redis,sys
r=redis.Redis(host='localhost',port=6380,db=0,decode_responses=True)
try:
    r.ping()
    print('OK')
except Exception as e:
    sys.exit(1)
PY
        Write-Host "Redis is available"
        break
    } catch {
        Start-Sleep -Seconds 2
        $attempt++
        Write-Host "Waiting for Redis... attempt $attempt/$maxAttempts"
    }
}
if ($attempt -ge $maxAttempts) { Write-Error "Redis not available"; exit 1 }

# Set historical env vars
$env:TRADING_PROVIDER = 'historical'
$env:HISTORICAL_SOURCE = $Source
$env:HISTORICAL_SPEED = $Speed.ToString()
if ($Ticks) { $env:HISTORICAL_TICKS = '1' }
if ($From) { $env:HISTORICAL_FROM = $From }

Write-Host "Launching local services in historical mode"
Start-Process -FilePath python -ArgumentList 'start_local.py --provider historical' -NoNewWindow -PassThru

Write-Host "Historical replay started. Monitor logs or use redis-cli to inspect 'system:virtual_time:current' key."