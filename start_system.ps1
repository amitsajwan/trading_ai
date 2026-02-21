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
    ./start_system.ps1 -Source historical -HistoricalSource synthetic -TimeSemantics virtual
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

    [string]$FastForwardTo = '',

    [double]$FastForwardSpeed = 20.0,

    [ValidateSet('auto', 'rebase', 'virtual', 'clock')]
    [string]$TimeSemantics = 'auto',

    [string]$VirtualTimeStart = '',

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
Import-DotEnv -EnvPath (Join-Path $root 'market_data_dashboard\.env')

function Read-EnvInt {
    param(
        [Parameter(Mandatory=$true)][string]$Name,
        [Parameter(Mandatory=$true)][int]$DefaultValue
    )
    $raw = [System.Environment]::GetEnvironmentVariable($Name)
    if ([string]::IsNullOrWhiteSpace($raw)) {
        return $DefaultValue
    }
    $parsed = 0
    if ([int]::TryParse($raw, [ref]$parsed)) {
        return $parsed
    }
    return $DefaultValue
}

function Read-EnvBool {
    param(
        [Parameter(Mandatory=$true)][string]$Name,
        [Parameter(Mandatory=$true)][bool]$DefaultValue
    )
    $raw = [System.Environment]::GetEnvironmentVariable($Name)
    if ([string]::IsNullOrWhiteSpace($raw)) {
        return $DefaultValue
    }
    switch ($raw.Trim().ToLowerInvariant()) {
        '1' { return $true }
        'true' { return $true }
        'yes' { return $true }
        'on' { return $true }
        '0' { return $false }
        'false' { return $false }
        'no' { return $false }
        'off' { return $false }
        default { return $DefaultValue }
    }
}

# Resolve effective ports from environment unless explicitly passed as parameters.
if (-not $PSBoundParameters.ContainsKey('ApiPort')) {
    $ApiPort = Read-EnvInt -Name 'API_PORT' -DefaultValue $ApiPort
}
if (-not $PSBoundParameters.ContainsKey('DashboardPort')) {
    $DashboardPort = Read-EnvInt -Name 'DASHBOARD_PORT' -DefaultValue $DashboardPort
}

# Default FreshStart to true unless explicitly provided.
if (-not $PSBoundParameters.ContainsKey('FreshStart')) {
    $FreshStart = $true
}

# Prefer virtualenv python if present (avoids system-python dependency drift)
$pythonCandidates = @()

# 1) Repo-local venv (canonical)
$pythonCandidates += (Join-Path $root '.venv\Scripts\python.exe')

# 2) Currently activated venv, if any
if (-not [string]::IsNullOrWhiteSpace($env:VIRTUAL_ENV)) {
    $pythonCandidates += (Join-Path $env:VIRTUAL_ENV 'Scripts\python.exe')
}

# 3) Parent-workspace venv (common when mono-workspace hosts multiple repos)
$parentRoot = Split-Path -Parent $root
if (-not [string]::IsNullOrWhiteSpace($parentRoot)) {
    $pythonCandidates += (Join-Path $parentRoot '.venv\Scripts\python.exe')
}

$pythonExe = $null
foreach ($candidate in $pythonCandidates) {
    if ($candidate -and (Test-Path $candidate)) {
        $pythonExe = $candidate
        break
    }
}

if (-not $pythonExe) {
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

# Resolve effective time semantics for this run.
$resolvedUseVirtualTime = $false
$resolvedRebaseToNow = $false
$resolvedClockSyncToNow = $false

if ($execMode -eq 'live' -and $TimeSemantics -eq 'virtual') {
    throw "-TimeSemantics virtual is not supported in live mode. Use historical source or set -TimeSemantics auto/rebase."
}

if ($execMode -eq 'historical') {
    switch ($TimeSemantics) {
        'virtual' {
            $resolvedUseVirtualTime = $true
            $resolvedRebaseToNow = $false
        }
        'rebase' {
            $resolvedUseVirtualTime = $false
            $resolvedRebaseToNow = $true
        }
        'clock' {
            $resolvedUseVirtualTime = $false
            $resolvedRebaseToNow = $false
            $resolvedClockSyncToNow = $true
        }
        default {
            # Auto policy keeps current behavior:
            # - synthetic replay => now-like rebased time
            # - zerodha/file replay => original historical timestamps
            if ($HistoricalSource -eq 'synthetic') {
                $resolvedRebaseToNow = $true
            }
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

function Stop-OrphanedMarketDataProcesses {
    param([Parameter(Mandatory=$true)][string]$RootPath)
    try {
        $rootNorm = $RootPath.Replace('\', '\\')
        $orphans = Get-CimInstance Win32_Process | Where-Object {
            $_.Name -eq 'python.exe' -and $_.CommandLine -and (
                (
                    ($_.CommandLine -like "*$rootNorm*" -or $_.CommandLine -like "*market_data*") -and (
                        $_.CommandLine -like '*-m market_data.runner*' -or
                        $_.CommandLine -like '*-m market_data.api_service*' -or
                        $_.CommandLine -like '*-m market_data.runner_historical*' -or
                        $_.CommandLine -like '*-m market_data.sources.websocket*'
                    )
                ) -or
                $_.CommandLine -like '*start_dashboard.py*'
            )
        }

        foreach ($p in $orphans) {
            try {
                Stop-Process -Id ([int]$p.ProcessId) -Force -ErrorAction Stop
                Write-Host "[start_system] Stopped orphan process (pid=$($p.ProcessId))" -ForegroundColor DarkYellow
            } catch {}
        }
    } catch {}
}

# Stop old tracked processes first.
Stop-TrackedProcess (Join-Path $runDir 'market_data.pid')
Stop-TrackedProcess (Join-Path $runDir 'dashboard.pid')
Stop-OrphanedMarketDataProcesses -RootPath $root

if ($FreshStart) {
    Write-Host "[start_system] Fresh start enabled: deleting '${execMode}:*' keys + known test/sentinel keys" -ForegroundColor Cyan
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

# Remove known placeholder/test keys that can pollute instrument discovery.
for pat in (
    "ohlc_sorted:FALLBACK_TEST:*",
    "price:FALLBACK_TEST:*",
    "websocket:tick:FALLBACK_TEST:*",
    "market:ohlc:FALLBACK_TEST:*",
    "indicators:FALLBACK_TEST:*",
):
    cursor = 0
    while True:
        cursor, keys = r.scan(cursor=cursor, match=pat, count=500)
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
if ($resolvedUseVirtualTime) {
    $env:USE_VIRTUAL_TIME = '1'
} else {
    $env:USE_VIRTUAL_TIME = '0'
}

if ($resolvedRebaseToNow) {
    $env:HISTORICAL_REBASE_TO_NOW = '1'
} else {
    $env:HISTORICAL_REBASE_TO_NOW = '0'
}
if ($resolvedClockSyncToNow) {
    $env:HISTORICAL_CLOCK_SYNC_TO_NOW = '1'
    if (-not [string]::IsNullOrWhiteSpace($FastForwardTo)) {
        $env:HISTORICAL_CLOCK_SYNC_ANCHOR = 'fast_forward'
    } else {
        $env:HISTORICAL_CLOCK_SYNC_ANCHOR = 'start'
    }
} else {
    Remove-Item Env:HISTORICAL_CLOCK_SYNC_TO_NOW -ErrorAction SilentlyContinue
    Remove-Item Env:HISTORICAL_CLOCK_SYNC_ANCHOR -ErrorAction SilentlyContinue
}

# Keep Redis virtual-time state aligned with selected time semantics.
$env:SYSTEM_VIRTUAL_TIME_ENABLE = $env:USE_VIRTUAL_TIME
if (-not [string]::IsNullOrWhiteSpace($VirtualTimeStart)) {
    $env:SYSTEM_VIRTUAL_TIME_CURRENT = $VirtualTimeStart
}

$virtualSync = @'
import os
from datetime import datetime, timezone
import redis

host = os.getenv('REDIS_HOST', 'localhost')
port = int(os.getenv('REDIS_PORT', '6379'))
enable = os.getenv('SYSTEM_VIRTUAL_TIME_ENABLE', '0').strip().lower() in ('1', 'true', 'yes', 'on')
virtual_time = os.getenv('SYSTEM_VIRTUAL_TIME_CURRENT', '').strip()

r = redis.Redis(host=host, port=port, db=0, decode_responses=True)
if enable:
    if not virtual_time:
        virtual_time = datetime.now(timezone.utc).isoformat()
    r.set('system:virtual_time:enabled', '1')
    r.set('system:virtual_time:current', virtual_time)
    print(f"[start_system] Virtual time enabled at {virtual_time}")
else:
    r.set('system:virtual_time:enabled', '0')
    r.delete('system:virtual_time:current')
    print('[start_system] Virtual time disabled')
'@

try {
    $virtualSync | & $pythonExe -
} catch {
    Write-Host "[start_system] WARNING: Virtual time sync failed: $($_.Exception.Message)" -ForegroundColor Yellow
} finally {
    Remove-Item Env:SYSTEM_VIRTUAL_TIME_ENABLE -ErrorAction SilentlyContinue
    Remove-Item Env:SYSTEM_VIRTUAL_TIME_CURRENT -ErrorAction SilentlyContinue
}

# Keep Redis execution-mode state aligned with this run.
$env:SYSTEM_EXECUTION_MODE = $execMode
$modeSync = @'
import os
import redis

host = os.getenv('REDIS_HOST', 'localhost')
port = int(os.getenv('REDIS_PORT', '6379'))
mode = os.getenv('SYSTEM_EXECUTION_MODE', 'historical').strip().lower()

r = redis.Redis(host=host, port=port, db=0, decode_responses=True)
r.set('system:execution_mode', mode)
print(f"[start_system] Redis execution mode set to {mode}")
'@

try {
    $modeSync | & $pythonExe -
} catch {
    Write-Host "[start_system] WARNING: Redis mode sync failed: $($_.Exception.Message)" -ForegroundColor Yellow
} finally {
    Remove-Item Env:SYSTEM_EXECUTION_MODE -ErrorAction SilentlyContinue
}

$effectiveTimeMode = if ($resolvedUseVirtualTime) { 'virtual' } elseif ($resolvedRebaseToNow) { 'rebase' } elseif ($resolvedClockSyncToNow) { 'clock' } else { 'historical' }
$redisHost = [System.Environment]::GetEnvironmentVariable('REDIS_HOST')
if ([string]::IsNullOrWhiteSpace($redisHost)) {
    $redisHost = 'localhost'
}
$redisPort = Read-EnvInt -Name 'REDIS_PORT' -DefaultValue 6379
$apiBaseUrl = "http://127.0.0.1:$ApiPort"
$dashboardBaseUrl = "http://127.0.0.1:$DashboardPort"
$apiHealthUrl = "$apiBaseUrl/health"
$dashboardHealthUrl = "$dashboardBaseUrl/api/health"
$wsUrl = "ws://127.0.0.1:$DashboardPort/ws"
$sampleInstrument = [System.Environment]::GetEnvironmentVariable('INSTRUMENT_SYMBOL')
if ([string]::IsNullOrWhiteSpace($sampleInstrument)) {
    $sampleInstrument = 'BANKNIFTY26MARFUT'
}
if ($sampleInstrument -match '[=\?&/\s]') {
    Write-Host "[start_system] WARNING: Invalid INSTRUMENT_SYMBOL='$sampleInstrument'; using BANKNIFTY26MARFUT for startup probes." -ForegroundColor Yellow
    $sampleInstrument = 'BANKNIFTY26MARFUT'
}
$sampleInstrumentName = [System.Environment]::GetEnvironmentVariable('INSTRUMENT_NAME')
if ([string]::IsNullOrWhiteSpace($sampleInstrumentName)) {
    $sampleInstrumentName = 'N/A'
}
$wsTickMode = [System.Environment]::GetEnvironmentVariable('KITE_TICKER_MODE')
if ([string]::IsNullOrWhiteSpace($wsTickMode)) {
    $wsTickMode = 'full'
}
$strictRealOnlyFlag = Read-EnvBool -Name 'LIVE_STRICT_REAL_ONLY' -DefaultValue $true
$strictLiveRealOnly = ($execMode -eq 'live' -and $wsSource -eq 'real' -and $strictRealOnlyFlag)
$dataPolicy = if ($strictLiveRealOnly) { 'REAL_ONLY (synthetic fallback disabled)' } else { 'fallbacks may be enabled' }
$redisKeyNamespace = "${execMode}:*"
$redisPublishChannels = "market:ohlc:${sampleInstrument}:*, indicators:${sampleInstrument}:*"
# Only force mock options path when running true mock/synthetic modes.
# For historical Zerodha replay we want real options-chain behavior.
if ($wsSource -eq 'mock' -or ($wsSource -eq 'historical' -and $HistoricalSource -ne 'zerodha')) {
    $env:USE_MOCK_KITE = '1'
} else {
    Remove-Item Env:USE_MOCK_KITE -ErrorAction SilentlyContinue
}
if ($wsSource -eq 'historical') {
    # Keep compatibility with older env-based config
    $env:HISTORICAL_SOURCE = $HistoricalSource
    $env:HISTORICAL_WS_SOURCE = $HistoricalSource
    $env:HISTORICAL_WS_TICK_INTERVAL = '0.25'
    $env:HISTORICAL_SPEED = [string]$HistoricalSpeed
    if (-not [string]::IsNullOrWhiteSpace($HistoricalFrom)) {
        $env:HISTORICAL_FROM = $HistoricalFrom
    } else {
        Remove-Item Env:HISTORICAL_FROM -ErrorAction SilentlyContinue
    }
    if (-not [string]::IsNullOrWhiteSpace($FastForwardTo)) {
        $env:HISTORICAL_FAST_FORWARD_TO = $FastForwardTo
        $env:HISTORICAL_FAST_FORWARD_SPEED = [string]$FastForwardSpeed
    } else {
        Remove-Item Env:HISTORICAL_FAST_FORWARD_TO -ErrorAction SilentlyContinue
        Remove-Item Env:HISTORICAL_FAST_FORWARD_SPEED -ErrorAction SilentlyContinue
    }
}

Write-Host "[start_system] Starting market_data runner (source=$Source, ws=$wsSource, mode=$execMode)" -ForegroundColor Cyan
$runnerLog = Join-Path $runDir 'market_data.log'
$runnerProc = Start-Process -FilePath $pythonExe -ArgumentList $runnerArgs -PassThru -WorkingDirectory $root -RedirectStandardOutput $runnerLog -RedirectStandardError (Join-Path $runDir 'market_data.err')
Set-Content -Path (Join-Path $runDir 'market_data.pid') -Value $runnerProc.Id

$apiOk = $false
for ($i=0; $i -lt 60; $i++) {
    try {
        $null = Invoke-WebRequest -Uri $apiHealthUrl -UseBasicParsing -TimeoutSec 2
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
        $null = Invoke-WebRequest -Uri $dashboardHealthUrl -UseBasicParsing -TimeoutSec 2
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

$redisOk = $false
$redisVerifyErr = ''
$redisProbe = @'
import os
import sys
import redis

host = os.getenv('REDIS_HOST', 'localhost')
port = int(os.getenv('REDIS_PORT', '6379'))

try:
    client = redis.Redis(host=host, port=port, db=0, socket_connect_timeout=2, socket_timeout=2)
    client.ping()
    print(f"ok:{host}:{port}")
except Exception as exc:
    print(str(exc))
    sys.exit(1)
'@
try {
    $redisProbeOut = $redisProbe | & $pythonExe -
    if ($LASTEXITCODE -eq 0) {
        $redisOk = $true
    } else {
        $redisVerifyErr = ($redisProbeOut | Out-String).Trim()
    }
} catch {
    $redisVerifyErr = $_.Exception.Message
}

Write-Host ""
Write-Host "[start_system] system started" -ForegroundColor Green
Write-Host "  Source:      $Source"
Write-Host "  Exec mode:   $execMode"
Write-Host "  Time mode:   $effectiveTimeMode (requested=$TimeSemantics, virtual=$($env:USE_VIRTUAL_TIME), rebase=$($env:HISTORICAL_REBASE_TO_NOW), clock_sync=$($env:HISTORICAL_CLOCK_SYNC_TO_NOW))"
Write-Host "  Stream:      ws_source=$wsSource, ws_mode=$wsTickMode"
Write-Host "  Data policy: $dataPolicy"
Write-Host "  Volume:      vol_total=volume_traded, vol_delta=diff(volume_traded), vol_delta=0 means no new trade"
Write-Host "  Instrument:  $sampleInstrument ($sampleInstrumentName)"
if ($redisOk) {
    Write-Host "  Redis:       ${redisHost}:$redisPort [verified]"
} else {
    Write-Host "  Redis:       ${redisHost}:$redisPort [not verified: $redisVerifyErr]" -ForegroundColor Yellow
}
Write-Host "  Redis path:  keys=$redisKeyNamespace"
Write-Host "  Redis pub:   $redisPublishChannels"
Write-Host "  API:         $apiBaseUrl [verified: $apiHealthUrl]"
Write-Host "  Dashboard:   $dashboardBaseUrl/ [verified: $dashboardHealthUrl]"
Write-Host "  WebSocket:   $wsUrl [verified via dashboard health]"
if ($strictLiveRealOnly) {
    Write-Host "  Live guard:  options/depth return no_data/503 when upstream data is missing (no synthetic fill)"
}
try {
    $indicatorSampleUrl = "$apiBaseUrl/api/v1/technical/indicators/$sampleInstrument?timeframe=1m"
    $indicatorResp = Invoke-WebRequest -Uri $indicatorSampleUrl -UseBasicParsing -TimeoutSec 4
    $indicatorBody = $indicatorResp.Content | ConvertFrom-Json
    $barsAvailable = 0
    if ($null -ne $indicatorBody.bars_available) {
        $barsAvailable = [int]$indicatorBody.bars_available
    }

    $indObj = $indicatorBody.indicators
    $hasSma20 = ($null -ne $indObj.sma_20)
    $hasMacd = ($null -ne $indObj.macd_value)
    $hasRsi14 = ($null -ne $indObj.rsi_14)
    $hasAtr14 = ($null -ne $indObj.atr_14)

    $missingWarmup = @()
    if (-not $hasSma20) { $missingWarmup += "sma_20(20)" }
    if (-not $hasMacd) { $missingWarmup += "macd_value(26)" }

    $warmupStatus = if ($missingWarmup.Count -eq 0) { "ready" } else { "warming_up: $($missingWarmup -join ', ')" }
    Write-Host "  Indicators:  bars_available=$barsAvailable, warmup=$warmupStatus, present=rsi_14:$hasRsi14 atr_14:$hasAtr14 sma_20:$hasSma20 macd_value:$hasMacd"
} catch {
    Write-Host "  Indicators:  status check unavailable ($($_.Exception.Message))" -ForegroundColor Yellow
}
try {
    $env:STARTUP_REDIS_HOST = $redisHost
    $env:STARTUP_REDIS_PORT = [string]$redisPort
    $env:STARTUP_API_BASE = $apiBaseUrl
    $env:STARTUP_DASH_BASE = $dashboardBaseUrl
    $env:STARTUP_INSTRUMENT = $sampleInstrument
    $env:STARTUP_EXEC_MODE = $execMode
    $readinessProbe = @'
import os
import json
import urllib.request
import urllib.error
import redis

host = os.getenv("STARTUP_REDIS_HOST", "localhost")
port = int(os.getenv("STARTUP_REDIS_PORT", "6379"))
api_base = os.getenv("STARTUP_API_BASE", "http://127.0.0.1:8004")
dash_base = os.getenv("STARTUP_DASH_BASE", "http://127.0.0.1:8000")
instrument = os.getenv("STARTUP_INSTRUMENT", "BANKNIFTY26MARFUT").upper()
mode = os.getenv("STARTUP_EXEC_MODE", "historical").strip().lower()

r = redis.Redis(host=host, port=port, db=0, decode_responses=True)

def http_json(url, timeout=4):
    try:
        with urllib.request.urlopen(url, timeout=timeout) as resp:
            return resp.status, json.loads(resp.read().decode("utf-8"))
    except Exception as exc:
        return None, str(exc)

def zcard_any(keys):
    best_key = None
    best_cnt = 0
    for k in keys:
        try:
            cnt = int(r.zcard(k) or 0)
        except Exception:
            cnt = 0
        if cnt > best_cnt:
            best_key = k
            best_cnt = cnt
    return best_key, best_cnt

def count_scan(patterns):
    total = 0
    for p in patterns:
        total += sum(1 for _ in r.scan_iter(match=p))
    return total

tf_1m_keys = [f"{mode}:ohlc_sorted:{instrument}:1m", f"ohlc_sorted:{instrument}:1m", f"{mode}:ohlc_sorted:{instrument}:1min", f"ohlc_sorted:{instrument}:1min"]
tf_5m_keys = [f"{mode}:ohlc_sorted:{instrument}:5m", f"ohlc_sorted:{instrument}:5m"]
tf_15m_keys = [f"{mode}:ohlc_sorted:{instrument}:15m", f"ohlc_sorted:{instrument}:15m"]

_, tf_1m_cnt = zcard_any(tf_1m_keys)
_, tf_5m_cnt = zcard_any(tf_5m_keys)
_, tf_15m_cnt = zcard_any(tf_15m_keys)

status_5, body_5 = http_json(f"{api_base}/api/v1/market/ohlc/{instrument}?timeframe=5min&limit=20")
status_15, body_15 = http_json(f"{api_base}/api/v1/market/ohlc/{instrument}?timeframe=15min&limit=20")
api_5m_cnt = len(body_5) if status_5 == 200 and isinstance(body_5, list) else 0
api_15m_cnt = len(body_15) if status_15 == 200 and isinstance(body_15, list) else 0

ind_1m_cnt = count_scan([f"{mode}:indicators:{instrument}:1m:*", f"indicators:{instrument}:1m:*", f"{mode}:indicators:{instrument}:1min:*", f"indicators:{instrument}:1min:*"])
ind_5m_cnt = count_scan([f"{mode}:indicators:{instrument}:5m:*", f"indicators:{instrument}:5m:*"])
ind_15m_cnt = count_scan([f"{mode}:indicators:{instrument}:15m:*", f"indicators:{instrument}:15m:*"])

# Prewarm depth/options once so mode-prefixed cache keys exist for downstream consumers.
http_json(f"{api_base}/api/v1/market/depth/{instrument}")
http_json(f"{api_base}/api/v1/options/chain/{instrument}")
# Prewarm indicators for canonical timeframes so Redis key counts stabilize quickly.
http_json(f"{api_base}/api/v1/technical/indicators/{instrument}?timeframe=1m")
http_json(f"{api_base}/api/v1/technical/indicators/{instrument}?timeframe=5min")
http_json(f"{api_base}/api/v1/technical/indicators/{instrument}?timeframe=15min")

depth_buy = r.get(f"{mode}:depth:{instrument}:buy") or r.get(f"depth:{instrument}:buy")
opt_chain = r.get(f"{mode}:options:{instrument}:chain") or r.get(f"options:{instrument}:chain")

tf_5m_source = "redis" if tf_5m_cnt > 0 else ("api_derived" if api_5m_cnt > 0 else "missing")
tf_15m_source = "redis" if tf_15m_cnt > 0 else ("api_derived" if api_15m_cnt > 0 else "missing")

print(f"[startup] tf_redis: 1m={tf_1m_cnt}, 5m={tf_5m_cnt}, 15m={tf_15m_cnt} (canonical keys: 1m/5m/15m)")
print(f"[startup] tf_api:   5min={api_5m_cnt}, 15min={api_15m_cnt} (source: 5m={tf_5m_source}, 15m={tf_15m_source})")
print(f"[startup] ind_keys: 1m={ind_1m_cnt}, 5m={ind_5m_cnt}, 15m={ind_15m_cnt}")
print(f"[startup] depth:    {'ready' if depth_buy else 'missing'}")
print(f"[startup] options:  {'ready' if opt_chain else 'missing'}")
'@
    $probeOut = $readinessProbe | & $pythonExe -
    if ($LASTEXITCODE -eq 0 -and $probeOut) {
        foreach ($line in $probeOut) {
            Write-Host "  $line"
        }
    } else {
        Write-Host "  Startup probe: unavailable"
    }
} catch {
    Write-Host "  Startup probe: failed ($($_.Exception.Message))" -ForegroundColor Yellow
} finally {
    Remove-Item Env:STARTUP_REDIS_HOST -ErrorAction SilentlyContinue
    Remove-Item Env:STARTUP_REDIS_PORT -ErrorAction SilentlyContinue
    Remove-Item Env:STARTUP_API_BASE -ErrorAction SilentlyContinue
    Remove-Item Env:STARTUP_DASH_BASE -ErrorAction SilentlyContinue
    Remove-Item Env:STARTUP_INSTRUMENT -ErrorAction SilentlyContinue
    Remove-Item Env:STARTUP_EXEC_MODE -ErrorAction SilentlyContinue
}
Write-Host "  Consumer samples:"
Write-Host "    - mode:         $apiBaseUrl/api/v1/system/mode"
Write-Host "    - instruments:  $apiBaseUrl/api/v1/market/instruments"
Write-Host "    - tick:         $apiBaseUrl/api/v1/market/tick/$sampleInstrument"
Write-Host "    - depth:        $apiBaseUrl/api/v1/market/depth/$sampleInstrument"
Write-Host "    - options:      $apiBaseUrl/api/v1/options/chain/$sampleInstrument"
Write-Host "    - ohlc:         $dashboardBaseUrl/api/market-data/ohlc/$sampleInstrument?timeframe=1m&limit=20"
Write-Host "    - indicators:   $dashboardBaseUrl/api/market-data/indicators/$sampleInstrument?timeframe=1m"
Write-Host "    - ws topics:    /topic/market/ohlc/$sampleInstrument, /topic/indicators/$sampleInstrument"
Write-Host "  Logs:        $runnerLog, $(Join-Path $runDir 'market_data.err'), $dashLog, $dashErr"
Write-Host "  Stop:        ./stop_system.ps1"
