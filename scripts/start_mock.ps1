<#
PowerShell runbook to start local dev environment in MOCK provider mode.
- Starts only MongoDB and Redis via docker-compose
- Sets env to use mock provider
- Starts `python start_local.py` in background and waits for health endpoints
- Runs `verify_market_data.py` as a final smoke check
#>

Write-Host "Starting local infra (MongoDB + Redis)..."
docker compose up -d mongodb redis

# Wait for Redis to respond on host port 6380
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
if ($attempt -ge $maxAttempts) {
    Write-Error "Redis did not become available in time"
    exit 1
}

# Set mock env vars for this session
$env:USE_MOCK_KITE = '1'
$env:TRADING_PROVIDER = 'mock'

Write-Host "Launching local services (mock provider) via start_local.py"
# Start start_local.py in a new process so this runbook can continue
$proc = Start-Process -FilePath python -ArgumentList 'start_local.py' -NoNewWindow -PassThru

# Wait for services' health endpoints
$services = @(
    @{Name='Market Data'; Url='http://localhost:8004/health'},
    @{Name='News'; Url='http://localhost:8005/health'},
    @{Name='Engine'; Url='http://localhost:8006/health'},
    @{Name='Dashboard'; Url='http://localhost:8888/api/health'}
)

foreach ($s in $services) {
    Write-Host "Waiting for $($s.Name) at $($s.Url)..."
    $attempt = 0
    $ok = $false
    while ($attempt -lt $maxAttempts -and -not $ok) {
        try {
            $resp = Invoke-WebRequest -UseBasicParsing -Uri $s.Url -TimeoutSec 2 -ErrorAction Stop
            if ($resp.StatusCode -eq 200) {
                Write-Host "  $($s.Name) is healthy"
                $ok = $true
                break
            }
        } catch {
            Start-Sleep -Seconds 2
            $attempt++
            Write-Host "  $($s.Name) not ready (attempt $attempt/$maxAttempts)"
        }
    }
    if (-not $ok) { Write-Warning "$($s.Name) did not respond in time" }
}

Write-Host "Running verify_market_data.py using mock provider..."
# Run verification (mock mode is set via env)
python verify_market_data.py

Write-Host "Done. To stop services, press Ctrl+C in the start_local window or run: docker compose down"