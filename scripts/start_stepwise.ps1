<#
PowerShell stepwise startup script for Windows
Usage: Open PowerShell in repo root and run: .\scripts\start_stepwise.ps1

What it does:
- Step 0: verify Zerodha credentials (calls Python helper verify_zerodha_credentials)
- Step 1: start Market Data API (scripts/run_market_data.py) and wait for /health and /api/v1/market/tick/BANKNIFTY
- Step 4.5: start User API (python -m user_module.api_service) and wait for /health
- Step 5: start Dashboard UI (Vite in dashboard/modular_ui) and wait for http://localhost:8888/

It prints PASS/FAIL and short details for each step and cleans up started processes on failure.
#>

param(
    [int]$TimeoutSeconds = 30
)

function Write-Status($msg) { Write-Host "[stepwise] $msg" }
function Wait-ForHttp($url, $timeoutSec) {
    $start = Get-Date
    while ((Get-Date) - $start -lt ([timespan]::FromSeconds($timeoutSec))) {
        try {
            $r = Invoke-WebRequest -Uri $url -UseBasicParsing -TimeoutSec 3 -ErrorAction Stop
            return @{ ok = $true; status = $r.StatusCode }
        } catch {
            Start-Sleep -Seconds 1
        }
    }
    return @{ ok = $false }
}

# Helper to run a small python snippet and capture JSON output
function Run-PythonCheck($pyCode) {
    try {
        # Run python and capture only stdout; do not merge stderr so logging doesn't corrupt JSON output
        $out = & python -c $pyCode
        if ($LASTEXITCODE -ne 0) {
            return "__ERROR__:Python exit code $LASTEXITCODE`n$out"
        }
        return $out
    } catch {
        return "__ERROR__:$($_.Exception.Message)"
    }
} 

# Keep track of started processes so we can stop them on failure
$startedProcs = @()
$summary = @{}

# -------- Step 0: Credentials --------
Write-Status "Step 0: verifying Zerodha credentials..."
$py = @'
import json, sys
from start_local import verify_zerodha_credentials
ok, info = verify_zerodha_credentials()
# Ensure info is serializable: convert to string representation
info_str = "credentials verified" if ok and info else ("credentials failed" if not ok else "unknown")
print(json.dumps({"ok": bool(ok), "info": info_str}))
'@
$raw = Run-PythonCheck $py
if ($raw -and $raw -match '__ERROR__') {
    Write-Host "Step 0: FAIL - python error: $raw" -ForegroundColor Red
    $summary['Step 0'] = 'FAIL: python error'
    exit 1
}
try {
    $obj = $raw | ConvertFrom-Json
    if ($obj.ok -eq $true) {
        Write-Host "Step 0: PASS - credentials OK: $($obj.info)" -ForegroundColor Green
        $summary['Step 0'] = 'PASS'
    } else {
        Write-Host "Step 0: FAIL - $($obj.info)" -ForegroundColor Red
        $summary['Step 0'] = "FAIL: $($obj.info)"
        exit 1
    }
} catch {
    Write-Host "Step 0: FAIL - could not parse python output: $raw" -ForegroundColor Red
    $summary['Step 0'] = 'FAIL: parse error'
    exit 1
} 

# -------- Step 1: Market Data API / Historical data --------
Write-Status "Step 1: start Market Data API and verify historical ticks..."
# Start market data via helper script which seeds PYTHONPATH correctly
$mdProc = Start-Process -FilePath python -ArgumentList 'scripts\run_market_data.py' -PassThru -WorkingDirectory (Get-Location).Path
$startedProcs += $mdProc
Write-Status "Started Market Data PID=$($mdProc.Id)"

# Wait for /health
$res = Wait-ForHttp 'http://localhost:8004/health' $TimeoutSeconds
if (-not $res.ok) {
    Write-Host "Step 1: FAIL - Market Data health check failed after $TimeoutSeconds s" -ForegroundColor Red
    $summary['Step 1'] = 'FAIL: health check timeout'
    goto :cleanup_fail
}
Write-Host "Step 1: Market Data /health OK (status $($res.status))" -ForegroundColor Green

# Check tick endpoint
$res2 = Wait-ForHttp 'http://localhost:8004/api/v1/market/tick/BANKNIFTY' $TimeoutSeconds
if (-not $res2.ok) {
    Write-Host "Step 1: FAIL - tick endpoint did not respond in $TimeoutSeconds s" -ForegroundColor Red
    $summary['Step 1'] = 'FAIL: tick endpoint'
    goto :cleanup_fail
}
Write-Host "Step 1: PASS - tick endpoint reachable (market data present)" -ForegroundColor Green
$summary['Step 1'] = 'PASS'

# -------- Historical detection (after Step 1) --------
Write-Status "Analyzing tick age for historical mode..."
$pyAge = @'
import json, requests, sys
try:
    r = requests.get("http://localhost:8004/api/v1/market/tick/BANKNIFTY", timeout=5)
    if r.status_code != 200:
        print(json.dumps({"ok": False, "error": f"status:{r.status_code}"}))
    else:
        j = r.json()
        from datetime import datetime
        ts = datetime.fromisoformat(j.get("timestamp"))
        now = datetime.now(ts.tzinfo)
        age = (now - ts).total_seconds()
        print(json.dumps({"ok": True, "age": int(age), "timestamp": j.get("timestamp")}))
except Exception as e:
    print(json.dumps({"ok": False, "error": str(e)}))
'@
$rawAge = Run-PythonCheck $pyAge
if ($rawAge -and $rawAge -match '__ERROR__') {
    Write-Host "Tick age check failed: $rawAge" -ForegroundColor Yellow
    $summary['Historical'] = 'UNKNOWN'
} else {
    try {
        $aobj = $rawAge | ConvertFrom-Json
        if ($aobj.ok -and $aobj.age -ne $null) {
            $ageSec = [int]$aobj.age
            Write-Host "Tick age: $ageSec seconds (timestamp $($aobj.timestamp))"
            $histThreshold = 3600 # seconds
            if ($ageSec -gt $histThreshold) {
                Write-Host "   ⚠️  DATA IS HISTORICAL (age > $histThreshold s)" -ForegroundColor Yellow
                $summary['Historical'] = "HISTORICAL (age ${ageSec}s)"
            } else {
                Write-Host "   ✅ Data appears fresh" -ForegroundColor Green
                $summary['Historical'] = "FRESH (age ${ageSec}s)"
            }
        } else {
            Write-Host "Tick age check returned no data: $($aobj.error)" -ForegroundColor Yellow
            $summary['Historical'] = 'UNKNOWN'
        }
    } catch {
        Write-Host "Tick age parse failed: $rawAge" -ForegroundColor Yellow
        $summary['Historical'] = 'UNKNOWN'
    }
}

# -------- Step 2: News API --------
Write-Status "Step 2: start/verify News API (port 8005)..."
$newsProc = Start-Process -FilePath python -ArgumentList '-m','news_module.api_service' -PassThru -WorkingDirectory (Get-Location).Path
$startedProcs += $newsProc
$resNews = Wait-ForHttp 'http://localhost:8005/health' $TimeoutSeconds
if (-not $resNews.ok) {
    Write-Host "Step 2: FAIL - News API /health not responding" -ForegroundColor Red
    $summary['Step 2'] = 'FAIL'
    goto :cleanup_fail
}
Write-Host "Step 2: PASS - News API healthy" -ForegroundColor Green
# Verify news endpoints
$resNews2 = Wait-ForHttp 'http://localhost:8005/api/v1/news/BANKNIFTY' 10
$resNews3 = Wait-ForHttp 'http://localhost:8005/api/v1/news/BANKNIFTY/sentiment' 10
if ($resNews2.ok -and $resNews3.ok) {
    Write-Host "Step 2: PASS - news endpoints OK" -ForegroundColor Green
    $summary['Step 2'] = 'PASS'
} else {
    Write-Host "Step 2: WARN - news endpoints missing" -ForegroundColor Yellow
    $summary['Step 2'] = 'WARN'
}

# -------- Step 3: Engine API --------
Write-Status "Step 3: start/verify Engine API (port 8006)..."
$engineProc = Start-Process -FilePath python -ArgumentList '-m','engine_module.api_service' -PassThru -WorkingDirectory (Get-Location).Path
$startedProcs += $engineProc
$resEngine = Wait-ForHttp 'http://localhost:8006/health' $TimeoutSeconds
if (-not $resEngine.ok) {
    Write-Host "Step 3: FAIL - Engine API /health not responding" -ForegroundColor Red
    $summary['Step 3'] = 'FAIL'
    goto :cleanup_fail
}
Write-Host "Step 3: PASS - Engine healthy" -ForegroundColor Green
# verify signals endpoint
$resSig = Wait-ForHttp 'http://localhost:8006/api/v1/signals/BANKNIFTY' 10
if ($resSig.ok) {
    Write-Host "Step 3: PASS - signals endpoint reachable" -ForegroundColor Green
    $summary['Step 3'] = 'PASS'
} else {
    Write-Host "Step 3: WARN - signals endpoint missing" -ForegroundColor Yellow
    $summary['Step 3'] = 'WARN'
}

# -------- Step 4.5: User API --------
Write-Status "Step 4.5: start User API (port 8007) and verify /health..."
# Ensure PYTHONPATH contains user_module/src
$abs = (Resolve-Path -Path .\user_module\src).Path
if ($env:PYTHONPATH) { $env:PYTHONPATH = "$abs;$env:PYTHONPATH" } else { $env:PYTHONPATH = $abs }
$uaProc = Start-Process -FilePath python -ArgumentList '-m','user_module.api_service' -PassThru -WorkingDirectory (Get-Location).Path
$startedProcs += $uaProc
Write-Status "Started User API PID=$($uaProc.Id)"
$res3 = Wait-ForHttp 'http://localhost:8007/health' $TimeoutSeconds
if (-not $res3.ok) {
    Write-Host "Step 4.5: FAIL - User API /health not responding after $TimeoutSeconds s" -ForegroundColor Red
    $summary['Step 4.5'] = 'FAIL: /health'
    goto :cleanup_fail
}
Write-Host "Step 4.5: PASS - User API healthy" -ForegroundColor Green
$summary['Step 4.5'] = 'PASS'

# -------- Step 5: Dashboard UI (Vite) --------
Write-Status "Step 5: start Dashboard UI (Vite) and verify http://localhost:8888/ ..."
# Check npm
if (-not (Get-Command npm -ErrorAction SilentlyContinue)) {
    Write-Host "Step 5: FAIL - npm not found in PATH. Install Node.js/npm" -ForegroundColor Red
    $summary['Step 5'] = 'FAIL: npm missing'
    goto :cleanup_fail
}
$uiDir = Join-Path (Get-Location) 'dashboard\modular_ui'
# If node_modules missing, run install
if (-not (Test-Path (Join-Path $uiDir 'node_modules'))) {
    Write-Status "node_modules missing - running npm install in $uiDir"
    $lock = Test-Path (Join-Path $uiDir 'package-lock.json')
    $npmCmd = 'ci'
    if (-not $lock) { $npmCmd = 'install' }
    $npmInstall = Start-Process -FilePath npm -ArgumentList $npmCmd -WorkingDirectory $uiDir -NoNewWindow -Wait -PassThru
    if ($npmInstall.ExitCode -ne 0) {
        Write-Host "Step 5: FAIL - npm install failed (exit $($npmInstall.ExitCode))" -ForegroundColor Red
        $summary['Step 5'] = 'FAIL: npm install'
        goto :cleanup_fail
    }
}
# Start Vite on port 8888
$viteProc = Start-Process -FilePath npm -ArgumentList 'run','dev','--','--port','8888' -WorkingDirectory $uiDir -PassThru
$startedProcs += $viteProc
Write-Status "Started Vite PID=$($viteProc.Id)"
$res4 = Wait-ForHttp 'http://localhost:8888/' $TimeoutSeconds
if (-not $res4.ok) {
    Write-Host "Step 5: FAIL - Dashboard UI did not become healthy after $TimeoutSeconds s" -ForegroundColor Red
    $summary['Step 5'] = 'FAIL: UI health'
    goto :cleanup_fail
}
Write-Host "Step 5: UI served at http://localhost:8888/" -ForegroundColor Green
# Verify a proxied endpoint
$res5 = Wait-ForHttp 'http://localhost:8888/api/market-data/tick/BANKNIFTY' $TimeoutSeconds
if (-not $res5.ok) {
    Write-Host "Step 5: WARN - proxied tick endpoint did not respond (UI->backend proxy)" -ForegroundColor Yellow
    $summary['Step 5'] = 'PASS (UI up, proxy missing)'
} else {
    Write-Host "Step 5: PASS - proxied tick endpoint reachable via UI" -ForegroundColor Green
    $summary['Step 5'] = 'PASS'
}

# All done - print summary and keep processes running (user can Ctrl+C to stop)
Write-Host `n========== SUMMARY ==========` -ForegroundColor Cyan
foreach ($k in $summary.Keys) { Write-Host "$k : $($summary[$k])" }
Write-Host `nProcesses started:` -ForegroundColor Cyan
foreach ($p in $startedProcs) { Write-Host "$($p.ProcessName) PID=$($p.Id)" }
Write-Host "`nAll steps completed. Press Ctrl+C to stop started processes and exit." -ForegroundColor Green

# Wait until user interrupts
try { while ($true) { Start-Sleep -Seconds 1 } } catch { }

:cleanup_fail
# If we jump here due to a failure, cleanup started processes
Write-Host "`nFailure detected - stopping started processes..." -ForegroundColor Yellow
foreach ($p in $startedProcs) {
    try { Stop-Process -Id $p.Id -Force -ErrorAction SilentlyContinue } catch { }
}
Write-Host "Stopped" -ForegroundColor Yellow
Write-Host `nPartial summary:` -ForegroundColor Cyan
foreach ($k in $summary.Keys) { Write-Host "$k : $($summary[$k])" }
exit 1
