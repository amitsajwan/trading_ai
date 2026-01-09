<#
Enhanced stepwise startup with comprehensive verification after each step
#>

param(
    [int]$TimeoutSeconds = 30
)

function Write-Status($msg) { Write-Host "[stepwise] $msg" -ForegroundColor Cyan }
function Write-Success($msg) { Write-Host "✅ $msg" -ForegroundColor Green }
function Write-Error($msg) { Write-Host "❌ $msg" -ForegroundColor Red }
function Write-Warning($msg) { Write-Host "⚠️  $msg" -ForegroundColor Yellow }

function Wait-ForHttp($url, $timeoutSec) {
    $start = Get-Date
    while ((Get-Date) - $start -lt ([timespan]::FromSeconds($timeoutSec))) {
        try {
            $r = Invoke-WebRequest -Uri $url -UseBasicParsing -TimeoutSec 3 -ErrorAction Stop
            return @{ ok = $true; status = $r.StatusCode; content = $r.Content }
        } catch {
            Start-Sleep -Seconds 1
        }
    }
    return @{ ok = $false }
}

function Test-Endpoint($url, $description) {
    Write-Status "  Testing $description..."
    try {
        $response = Invoke-WebRequest -Uri $url -UseBasicParsing -TimeoutSec 5 -ErrorAction Stop
        try {
            $json = $response.Content | ConvertFrom-Json
            Write-Success "$description - Status: $($response.StatusCode)"
            return @{ ok = $true; status = $response.StatusCode; data = $json }
        } catch {
            Write-Success "$description - Status: $($response.StatusCode) (non-JSON)"
            return @{ ok = $true; status = $response.StatusCode; data = $response.Content }
        }
    } catch {
        Write-Error "$description - Failed: $($_.Exception.Message)"
        return @{ ok = $false; error = $_.Exception.Message }
    }
}

function Run-PythonCheck($pyCode) {
    try {
        $out = & python -c $pyCode 2>&1 | Out-String
        if ($LASTEXITCODE -ne 0) {
            return "__ERROR__:Python exit code $LASTEXITCODE`n$out"
        }
        return $out
    } catch {
        return "__ERROR__:$($_.Exception.Message)"
    }
}

$startedProcs = @()
$summary = @()

# -------- Step 0: Credentials --------
Write-Host "`n========== Step 0: Verifying Zerodha Credentials ==========" -ForegroundColor Yellow
Write-Status "Verifying Zerodha credentials..."
$py = @'
import json, sys
from start_local import verify_zerodha_credentials
ok, info = verify_zerodha_credentials()
info_str = "credentials verified" if ok and info else ("credentials failed" if not ok else "unknown")
print(json.dumps({"ok": bool(ok), "info": info_str}))
'@
$raw = Run-PythonCheck $py
if ($raw -and $raw -match '__ERROR__') {
    Write-Error "Step 0: FAIL - python error: $raw"
    exit 1
}
try {
    $obj = $raw | ConvertFrom-Json
    if ($obj.ok -eq $true) {
        Write-Success "Step 0: PASS - credentials OK: $($obj.info)"
        $summary['Step 0'] = 'PASS'
    } else {
        Write-Error "Step 0: FAIL - $($obj.info)"
        exit 1
    }
} catch {
    Write-Error "Step 0: FAIL - could not parse python output: $raw"
    exit 1
}

# -------- Step 1: Market Data API --------
Write-Host "`n========== Step 1: Market Data API (port 8004) ==========" -ForegroundColor Yellow
Write-Status "Starting Market Data API..."
$mdProc = Start-Process -FilePath python -ArgumentList 'scripts\run_market_data.py' -PassThru -WorkingDirectory (Get-Location).Path
$startedProcs += $mdProc
Write-Status "Started Market Data PID=$($mdProc.Id)"

# Wait for health
$res = Wait-ForHttp 'http://localhost:8004/health' $TimeoutSeconds
if (-not $res.ok) {
    Write-Error "Step 1: FAIL - Market Data health check failed after $TimeoutSeconds s"
    goto :cleanup_fail
}
Write-Success "Step 1: Market Data /health OK (status $($res.status))"

# Verify endpoints
Write-Status "Verifying Market Data endpoints..."
$tickRes = Test-Endpoint 'http://localhost:8004/api/v1/market/tick/BANKNIFTY' "Market Data /api/v1/market/tick/BANKNIFTY"
if ($tickRes.ok) {
    $tickData = $tickRes.data
    if ($tickData.timestamp) {
        Write-Status "  Tick timestamp: $($tickData.timestamp)"
        if ($tickData.price) { Write-Status "  Tick price: $($tickData.price)" }
        if ($tickData.volume) { Write-Status "  Tick volume: $($tickData.volume)" }
        
        # Check if historical
        $pyAge = @'
import json, requests
try:
    r = requests.get("http://localhost:8004/api/v1/market/tick/BANKNIFTY", timeout=5)
    if r.status_code == 200:
        j = r.json()
        from datetime import datetime
        ts = datetime.fromisoformat(j.get("timestamp"))
        now = datetime.now(ts.tzinfo)
        age = (now - ts).total_seconds()
        print(json.dumps({"ok": True, "age": int(age), "timestamp": j.get("timestamp")}))
    else:
        print(json.dumps({"ok": False, "error": f"status:{r.status_code}"}))
except Exception as e:
    print(json.dumps({"ok": False, "error": str(e)}))
'@
        $rawAge = Run-PythonCheck $pyAge
        if ($rawAge -and -not ($rawAge -match '__ERROR__')) {
            try {
                $aobj = $rawAge | ConvertFrom-Json
                if ($aobj.ok -and $aobj.age -ne $null) {
                    $ageSec = [int]$aobj.age
                    Write-Status "  Tick age: $ageSec seconds"
                    if ($ageSec -gt 3600) {
                        Write-Warning "  ⚠️  DATA IS HISTORICAL (age > 3600s)"
                    } else {
                        Write-Success "  ✅ Data appears fresh"
                    }
                }
            } catch { }
        }
    }
    Write-Success "Step 1: PASS - Market Data API fully verified"
    $summary['Step 1'] = 'PASS'
} else {
    Write-Error "Step 1: FAIL - tick endpoint not working"
    $summary['Step 1'] = 'FAIL'
    goto :cleanup_fail
}

# -------- Step 2: News API --------
Write-Host "`n========== Step 2: News API (port 8005) ==========" -ForegroundColor Yellow
Write-Status "Starting News API..."
$newsProc = Start-Process -FilePath python -ArgumentList '-m','news_module.api_service' -PassThru -WorkingDirectory (Get-Location).Path
$startedProcs += $newsProc
Write-Status "Started News API PID=$($newsProc.Id)"

$resNews = Wait-ForHttp 'http://localhost:8005/health' $TimeoutSeconds
if (-not $resNews.ok) {
    Write-Error "Step 2: FAIL - News API /health not responding"
    $summary['Step 2'] = 'FAIL'
    goto :cleanup_fail
}
Write-Success "Step 2: News API /health OK"

# Verify news endpoints
Write-Status "Verifying News API endpoints..."
$newsRes = Test-Endpoint 'http://localhost:8005/api/v1/news/BANKNIFTY' "News API /api/v1/news/BANKNIFTY"
$sentimentRes = Test-Endpoint 'http://localhost:8005/api/v1/news/BANKNIFTY/sentiment' "News API /api/v1/news/BANKNIFTY/sentiment"

if ($newsRes.ok) {
    $newsData = $newsRes.data
    if ($newsData -is [array]) {
        Write-Status "  News count: $($newsData.Count)"
    } elseif ($newsData.news -is [array]) {
        Write-Status "  News count: $($newsData.news.Count)"
    }
}

if ($sentimentRes.ok) {
    $sentimentData = $sentimentRes.data
    if ($sentimentData.sentiment) {
        Write-Status "  Sentiment: $($sentimentData.sentiment)"
    }
    if ($sentimentData.score) {
        Write-Status "  Sentiment score: $($sentimentData.score)"
    }
}

if ($newsRes.ok -and $sentimentRes.ok) {
    Write-Success "Step 2: PASS - News API fully verified"
    $summary['Step 2'] = 'PASS'
} else {
    Write-Warning "Step 2: WARN - some news endpoints missing"
    $summary['Step 2'] = 'WARN'
}

# -------- Step 3: Engine API --------
Write-Host "`n========== Step 3: Engine API (port 8006) ==========" -ForegroundColor Yellow
Write-Status "Starting Engine API..."
$engineProc = Start-Process -FilePath python -ArgumentList '-m','engine_module.api_service' -PassThru -WorkingDirectory (Get-Location).Path
$startedProcs += $engineProc
Write-Status "Started Engine API PID=$($engineProc.Id)"

$resEngine = Wait-ForHttp 'http://localhost:8006/health' $TimeoutSeconds
if (-not $resEngine.ok) {
    Write-Error "Step 3: FAIL - Engine API /health not responding"
    $summary['Step 3'] = 'FAIL'
    goto :cleanup_fail
}
Write-Success "Step 3: Engine API /health OK"

# Verify signals endpoint
Write-Status "Verifying Engine API endpoints..."
$signalsRes = Test-Endpoint 'http://localhost:8006/api/v1/signals/BANKNIFTY' "Engine API /api/v1/signals/BANKNIFTY"

if ($signalsRes.ok) {
    $signalsData = $signalsRes.data
    if ($signalsData -is [array]) {
        Write-Status "  Signals count: $($signalsData.Count)"
    } elseif ($signalsData.signals -is [array]) {
        Write-Status "  Signals count: $($signalsData.signals.Count)"
    }
    Write-Success "Step 3: PASS - Engine API fully verified"
    $summary['Step 3'] = 'PASS'
} else {
    Write-Warning "Step 3: WARN - signals endpoint missing"
    $summary['Step 3'] = 'WARN'
}

# -------- Step 4.5: User API --------
Write-Host "`n========== Step 4.5: User API (port 8007) ==========" -ForegroundColor Yellow
Write-Status "Starting User API..."
$abs = (Resolve-Path -Path .\user_module\src).Path
if ($env:PYTHONPATH) { $env:PYTHONPATH = "$abs;$env:PYTHONPATH" } else { $env:PYTHONPATH = $abs }
$uaProc = Start-Process -FilePath python -ArgumentList '-m','user_module.api_service' -PassThru -WorkingDirectory (Get-Location).Path
$startedProcs += $uaProc
Write-Status "Started User API PID=$($uaProc.Id)"

$res3 = Wait-ForHttp 'http://localhost:8007/health' $TimeoutSeconds
if (-not $res3.ok) {
    Write-Error "Step 4.5: FAIL - User API /health not responding after $TimeoutSeconds s"
    $summary['Step 4.5'] = 'FAIL: /health'
    goto :cleanup_fail
}
Write-Success "Step 4.5: User API /health OK"
$summary['Step 4.5'] = 'PASS'

# -------- Step 5: Dashboard UI --------
Write-Host "`n========== Step 5: Dashboard UI (port 8888) ==========" -ForegroundColor Yellow
Write-Status "Starting Dashboard UI (Vite)..."
if (-not (Get-Command npm -ErrorAction SilentlyContinue)) {
    Write-Error "Step 5: FAIL - npm not found in PATH"
    $summary['Step 5'] = 'FAIL: npm missing'
    goto :cleanup_fail
}
$uiDir = Join-Path (Get-Location) 'dashboard\modular_ui'
if (-not (Test-Path (Join-Path $uiDir 'node_modules'))) {
    Write-Status "node_modules missing - running npm install..."
    $lock = Test-Path (Join-Path $uiDir 'package-lock.json')
    $npmCmd = 'ci'
    if (-not $lock) { $npmCmd = 'install' }
    $npmInstall = Start-Process -FilePath npm -ArgumentList $npmCmd -WorkingDirectory $uiDir -NoNewWindow -Wait -PassThru
    if ($npmInstall.ExitCode -ne 0) {
        Write-Error "Step 5: FAIL - npm install failed"
        $summary['Step 5'] = 'FAIL: npm install'
        goto :cleanup_fail
    }
}
$viteProc = Start-Process -FilePath npm -ArgumentList 'run','dev','--','--port','8888' -WorkingDirectory $uiDir -PassThru
$startedProcs += $viteProc
Write-Status "Started Vite PID=$($viteProc.Id)"

$res4 = Wait-ForHttp 'http://localhost:8888/' $TimeoutSeconds
if (-not $res4.ok) {
    Write-Error "Step 5: FAIL - Dashboard UI did not become healthy after $TimeoutSeconds s"
    $summary['Step 5'] = 'FAIL: UI health'
    goto :cleanup_fail
}
Write-Success "Step 5: Dashboard UI served at http://localhost:8888/"

# Verify proxied endpoint
Write-Status "Verifying Dashboard proxy..."
$proxyRes = Test-Endpoint 'http://localhost:8888/api/market-data/tick/BANKNIFTY' "Dashboard proxy /api/market-data/tick/BANKNIFTY"
if ($proxyRes.ok) {
    Write-Success "Step 5: PASS - Dashboard UI and proxy fully verified"
    $summary['Step 5'] = 'PASS'
} else {
    Write-Warning "Step 5: WARN - proxied endpoint not working (UI up, proxy missing)"
    $summary['Step 5'] = 'PASS (UI up, proxy missing)'
}

# All done
Write-Host "`n========== FINAL SUMMARY ==========" -ForegroundColor Cyan
foreach ($k in $summary.Keys) { 
    $color = if ($summary[$k] -eq 'PASS') { 'Green' } elseif ($summary[$k] -match 'WARN') { 'Yellow' } else { 'Red' }
    Write-Host "$k : $($summary[$k])" -ForegroundColor $color
}
Write-Host "`nProcesses started:" -ForegroundColor Cyan
foreach ($p in $startedProcs) { 
    if (Get-Process -Id $p.Id -ErrorAction SilentlyContinue) {
        Write-Host "$($p.ProcessName) PID=$($p.Id)" -ForegroundColor Green
    } else {
        Write-Host "$($p.ProcessName) PID=$($p.Id) (stopped)" -ForegroundColor Red
    }
}
Write-Host "`nAll steps completed. Press Ctrl+C to stop started processes and exit." -ForegroundColor Green

try { while ($true) { Start-Sleep -Seconds 1 } } catch { }

:cleanup_fail
Write-Host "`nFailure detected - stopping started processes..." -ForegroundColor Yellow
foreach ($p in $startedProcs) {
    try { Stop-Process -Id $p.Id -Force -ErrorAction SilentlyContinue } catch { }
}
Write-Host "Stopped" -ForegroundColor Yellow
Write-Host "`nPartial summary:" -ForegroundColor Cyan
foreach ($k in $summary.Keys) { Write-Host "$k : $($summary[$k])" }
exit 1
