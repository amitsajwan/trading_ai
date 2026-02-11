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
    ./start_system.ps1 -Source mock -FreshStart
#>

param(
    [ValidateSet('kite', 'mock', 'historical')]
    [string]$Source = 'mock',

    [ValidateSet('live', 'historical', 'paper')]
    [string]$Mode,

    [string]$HistoricalSource = 'synthetic',

    [switch]$FreshStart = $true,

    [int]$ApiPort = 8004,
    [int]$DashboardPort = 8000
)

$ErrorActionPreference = 'Stop'
$root = Split-Path -Parent $MyInvocation.MyCommand.Path
$runDir = Join-Path $root '.run'
if (-not (Test-Path $runDir)) {
    New-Item -ItemType Directory -Path $runDir | Out-Null
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
        $execMode = 'historical'
        $wsSource = 'mock'
        $runnerArgs = @('-m','market_data.runner','--mode','live','--start-collectors')
    }
    'historical' {
        $execMode = 'historical'
        $wsSource = 'historical'
        $runnerArgs = @('-m','market_data.runner','--mode','live','--start-collectors')
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
    $cleanup = @"
import os
import redis
host = os.getenv('REDIS_HOST', 'localhost')
port = int(os.getenv('REDIS_PORT', '6379'))
mode = "$execMode"
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
print(f"[start_system] Deleted keys for mode '{mode}': {deleted}")
"@
    try {
        python -c $cleanup
    } catch {
        Write-Host "[start_system] WARNING: Redis cleanup failed: $($_.Exception.Message)" -ForegroundColor Yellow
    }
}

$env:PYTHONPATH = "$root/market_data/src;$root"
$env:EXECUTION_MODE = $execMode
$env:KITE_WS_SOURCE = $wsSource
if ($wsSource -ne 'real') {
    $env:USE_MOCK_KITE = '1'
}
if ($wsSource -eq 'historical') {
    $env:HISTORICAL_WS_SOURCE = $HistoricalSource
    $env:HISTORICAL_WS_TICK_INTERVAL = '0.25'
}

Write-Host "[start_system] Starting market_data runner (source=$Source, ws=$wsSource, mode=$execMode)" -ForegroundColor Cyan
$runnerLog = Join-Path $runDir 'market_data.log'
$runnerProc = Start-Process -FilePath python -ArgumentList $runnerArgs -PassThru -WorkingDirectory $root -RedirectStandardOutput $runnerLog -RedirectStandardError (Join-Path $runDir 'market_data.err')
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
$dashLog = Join-Path $runDir 'dashboard.log'
$dashProc = Start-Process -FilePath python -ArgumentList @('start_dashboard.py') -PassThru -WorkingDirectory (Join-Path $root 'market_data_dashboard') -RedirectStandardOutput $dashLog -RedirectStandardError (Join-Path $runDir 'dashboard.err')
Set-Content -Path (Join-Path $runDir 'dashboard.pid') -Value $dashProc.Id

Write-Host "" 
Write-Host "[start_system] ✅ system started" -ForegroundColor Green
Write-Host "  Source:      $Source"
Write-Host "  Exec mode:   $execMode"
Write-Host "  API:         http://127.0.0.1:$ApiPort/health"
Write-Host "  Dashboard:   http://127.0.0.1:$DashboardPort/"
Write-Host "  Logs:        $runnerLog, $dashLog"
Write-Host "  Stop:        ./stop_system.ps1" 
