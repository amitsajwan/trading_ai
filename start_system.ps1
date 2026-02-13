#!/usr/bin/env pwsh
<#
.SYNOPSIS
    Start full market-data stack (PowerShell-native, no bash required).

.DESCRIPTION
    Canonical PowerShell entrypoint for:
      1) market_data runner
      2) market_data dashboard

    Source contract:
      -Source kite       -> real websocket, live namespace
      -Source mock       -> mock websocket, historical namespace
      -Source historical -> historical websocket adapter, historical namespace

.EXAMPLES
    ./start_system.ps1 -Source kite
    ./start_system.ps1 -Source historical -HistoricalSource synthetic
    ./start_system.ps1 -Source historical -HistoricalSource zerodha -HistoricalFrom 2026-02-11 -HistoricalSpeed 1
    ./start_system.ps1 -Source mock -FreshStart
#>

param(
    [ValidateSet('kite', 'mock', 'historical')]
    [string]$Source = 'mock',

    [ValidateSet('live', 'historical', 'paper')]
    [string]$Mode,

    [string]$HistoricalSource = 'synthetic',

    [string]$HistoricalFrom = '',

    [double]$HistoricalSpeed = 5.0,

    [switch]$FreshStart,

    [int]$ApiPort = 8004,
    [int]$DashboardPort = 8000
)

$ErrorActionPreference = 'Stop'
$root = Split-Path -Parent $MyInvocation.MyCommand.Path
$runDir = Join-Path $root '.run'
if (-not (Test-Path $runDir)) {
    New-Item -ItemType Directory -Path $runDir | Out-Null
}

function Import-DotEnv {
    param(
        [Parameter(Mandatory=$true)][string]$EnvPath,
        [switch]$OverrideExisting = $false
    )
    if (-not (Test-Path $EnvPath)) {
        return
    }
    Get-Content $EnvPath | ForEach-Object {
        $line = $_.Trim()
        if (-not $line) { return }
        if ($line.StartsWith('#')) { return }
        $idx = $line.IndexOf('=')
        if ($idx -lt 1) { return }
        $key = $line.Substring(0, $idx).Trim()
        $val = $line.Substring($idx + 1).Trim()
        if (-not $key) { return }

        # Strip surrounding quotes
        if (($val.StartsWith('"') -and $val.EndsWith('"')) -or ($val.StartsWith("'") -and $val.EndsWith("'"))) {
            $val = $val.Substring(1, $val.Length - 2)
        }

        $existing = [System.Environment]::GetEnvironmentVariable($key)
        if ($OverrideExisting -or [string]::IsNullOrEmpty($existing)) {
            [System.Environment]::SetEnvironmentVariable($key, $val)
            Set-Item -Path ("Env:" + $key) -Value $val
        }
    }
}

# Load canonical env defaults so all child processes (runner/api/dashboard) agree.
Import-DotEnv -EnvPath (Join-Path $root 'market_data\.env')

# Default FreshStart to true unless explicitly provided.
if (-not $PSBoundParameters.ContainsKey('FreshStart')) {
    $FreshStart = $true
}

# Prefer workspace venv python if present (avoids system-python dependency drift)
$pythonExe = Join-Path $root '.venv\Scripts\python.exe'
if (-not (Test-Path $pythonExe)) {
    $pythonExe = 'python'
}

# Backward compatibility: old -Mode maps to -Source unless -Source explicitly passed by caller.
if ($PSBoundParameters.ContainsKey('Mode') -and -not $PSBoundParameters.ContainsKey('Source')) {
    switch ($Mode) {
        'live' { $Source = 'kite' }
        'historical' { $Source = 'historical' }
        'paper' { $Source = 'mock' }
    }
}

switch ($Source) {
    'kite' {
        $execMode = 'live'
        $wsSource = 'real'
        $runnerArgs = @('-m','market_data.runner','--mode','live','--start-collectors','--prompt-login')
    }
    'mock' {
        $execMode = 'live'
        $wsSource = 'mock'
        $env:USE_MOCK_KITE = '1'
        $runnerArgs = @('-m','market_data.runner','--mode','live','--start-collectors')
    }
    'historical' {
        $execMode = 'historical'
        $wsSource = 'historical'
        $runnerArgs = @(
            '-m','market_data.runner',
            '--mode',$execMode,
            '--historical-source',$HistoricalSource,
            '--historical-speed',[string]$HistoricalSpeed,
            '--start-collectors'
        )
        if ($HistoricalSource -eq 'zerodha') {
            $runnerArgs += '--prompt-login'
        }
        if (-not [string]::IsNullOrWhiteSpace($HistoricalFrom)) {
            $runnerArgs += @('--historical-from', $HistoricalFrom)
        }
    }
}

function Stop-TrackedProcess {
    param([string]$PidFile)
    if (Test-Path $PidFile) {
        $processId = Get-Content $PidFile -ErrorAction SilentlyContinue
        if ($processId) {
            try {
                Stop-Process -Id ([int]$processId) -Force -ErrorAction Stop
            } catch {}
        }
        Remove-Item $PidFile -Force -ErrorAction SilentlyContinue
    }
}

# Stop old tracked processes first.
Stop-TrackedProcess (Join-Path $runDir 'market_data.pid')
Stop-TrackedProcess (Join-Path $runDir 'dashboard.pid')

if ($FreshStart) {
    Write-Host "[start_system] Fresh start enabled: deleting '${execMode}:*' keys only" -ForegroundColor Cyan
    $env:EXEC_MODE_CLEANUP = $execMode
    $cleanup = @'
import os
import redis
host = os.getenv('REDIS_HOST', 'localhost')
port = int(os.getenv('REDIS_PORT', '6379'))
mode = os.getenv('EXEC_MODE_CLEANUP', 'historical')
r = redis.Redis(host=host, port=port, db=0, decode_responses=True)
cursor = 0
deleted = 0
while True:
    cursor, keys = r.scan(cursor=cursor, match=f"{mode}:*", count=1000)
    if keys:
        deleted += r.delete(*keys)
    if cursor == 0:
        break
if mode == 'historical':
    r.delete('system:historical:ready')
print("[start_system] Deleted keys for mode '{}': {}".format(mode, deleted))
'@
    try {
        $cleanup | & $pythonExe -
    } catch {
        Write-Host "[start_system] WARNING: Redis cleanup failed: $($_.Exception.Message)" -ForegroundColor Yellow
    } finally {
        Remove-Item Env:EXEC_MODE_CLEANUP -ErrorAction SilentlyContinue
    }
}

$env:PYTHONPATH = "$root/market_data/src;$root"
$env:EXECUTION_MODE = $execMode
$env:KITE_WS_SOURCE = $wsSource
if ($wsSource -ne 'real') {
    $env:USE_MOCK_KITE = '1'
}
if ($wsSource -eq 'historical') {
    # Keep compatibility with older env-based config
    $env:HISTORICAL_SOURCE = $HistoricalSource
    $env:HISTORICAL_WS_SOURCE = $HistoricalSource
    $env:HISTORICAL_WS_TICK_INTERVAL = '0.25'
    $env:HISTORICAL_SPEED = [string]$HistoricalSpeed
    if (-not [string]::IsNullOrWhiteSpace($HistoricalFrom)) {
        $env:HISTORICAL_FROM = $HistoricalFrom
    }
}

Write-Host "[start_system] Starting market_data runner (source=$Source, ws=$wsSource, mode=$execMode)" -ForegroundColor Cyan
$runnerLog = Join-Path $runDir 'market_data.log'
$runnerProc = Start-Process -FilePath $pythonExe -ArgumentList $runnerArgs -PassThru -WorkingDirectory $root -RedirectStandardOutput $runnerLog -RedirectStandardError (Join-Path $runDir 'market_data.err')
Set-Content -Path (Join-Path $runDir 'market_data.pid') -Value $runnerProc.Id

$apiOk = $false
for ($i=0; $i -lt 60; $i++) {
    try {
        $null = Invoke-WebRequest -Uri "http://127.0.0.1:$ApiPort/health" -UseBasicParsing -TimeoutSec 2
        $apiOk = $true
        break
    } catch {
        Start-Sleep -Seconds 1
    }
}

if (-not $apiOk) {
    Write-Host "[start_system] ERROR: API did not become healthy. Check $runnerLog" -ForegroundColor Red
    exit 1
}

Write-Host "[start_system] Starting dashboard" -ForegroundColor Cyan
$env:MARKET_DATA_API_URL = "http://127.0.0.1:$ApiPort"
$env:DASHBOARD_PORT = [string]$DashboardPort
$dashLog = Join-Path $runDir 'dashboard.log'
$dashErr = Join-Path $runDir 'dashboard.err'
$dashProc = Start-Process -FilePath $pythonExe -ArgumentList @('start_dashboard.py') -PassThru -WorkingDirectory (Join-Path $root 'market_data_dashboard') -RedirectStandardOutput $dashLog -RedirectStandardError $dashErr
Set-Content -Path (Join-Path $runDir 'dashboard.pid') -Value $dashProc.Id

$dashboardOk = $false
for ($i=0; $i -lt 30; $i++) {
    if ($dashProc.HasExited) {
        break
    }
    try {
        $null = Invoke-WebRequest -Uri "http://127.0.0.1:$DashboardPort/api/health" -UseBasicParsing -TimeoutSec 2
        $dashboardOk = $true
        break
    } catch {
        Start-Sleep -Seconds 1
    }
}

if (-not $dashboardOk) {
    Write-Host "[start_system] ERROR: Dashboard did not become healthy on port $DashboardPort" -ForegroundColor Red
    Write-Host "[start_system] Check logs: $dashLog and $dashErr" -ForegroundColor Yellow
    exit 1
}

Write-Host "" 
Write-Host "[start_system] ✅ system started" -ForegroundColor Green
Write-Host "  Source:      $Source"
Write-Host "  Exec mode:   $execMode"
Write-Host "  API:         http://127.0.0.1:$ApiPort/health"
Write-Host "  Dashboard:   http://127.0.0.1:$DashboardPort/"
Write-Host "  Logs:        $runnerLog, $dashLog"
Write-Host "  Stop:        ./stop_system.ps1" 
