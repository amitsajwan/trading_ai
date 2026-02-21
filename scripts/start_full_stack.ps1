param(
    [Parameter(Mandatory = $true)]
    [string]$Instrument,
    [string]$SourceBase = "http://127.0.0.1:8002",
    [string]$MarketApiBase = "http://127.0.0.1:8004",
    [string]$DashboardApiBase = "http://127.0.0.1:9000",
    [string]$EngineApiBase = "http://127.0.0.1:9006",
    [string]$WsBase = "http://127.0.0.1:9009",
    [switch]$KillExisting
)

$ErrorActionPreference = "Stop"

function Wait-HttpOk {
    param(
        [Parameter(Mandatory = $true)][string]$Url,
        [int]$TimeoutSeconds = 45,
        [int]$SleepMilliseconds = 800
    )
    $sw = [System.Diagnostics.Stopwatch]::StartNew()
    while ($sw.Elapsed.TotalSeconds -lt $TimeoutSeconds) {
        try {
            $resp = Invoke-WebRequest -Uri $Url -UseBasicParsing -TimeoutSec 4
            if ($resp.StatusCode -ge 200 -and $resp.StatusCode -lt 300) {
                return $true
            }
        } catch {
            Start-Sleep -Milliseconds $SleepMilliseconds
        }
    }
    return $false
}

function Stop-PortProcess {
    param([int]$Port)
    try {
        $procs = Get-NetTCPConnection -LocalPort $Port -State Listen -ErrorAction SilentlyContinue |
            Select-Object -ExpandProperty OwningProcess -Unique
        foreach ($pid in $procs) {
            if ($pid -and $pid -ne $PID) {
                try {
                    taskkill /PID $pid /T /F | Out-Null
                } catch {
                    Stop-Process -Id $pid -Force -ErrorAction SilentlyContinue
                }
            }
        }
    } catch {
        # Best effort only.
    }
}

function Stop-ManagedProcesses {
    param([string]$PidFile)
    if (-not (Test-Path $PidFile)) {
        return
    }
    try {
        $raw = Get-Content -Path $PidFile -Raw
        if (-not $raw) { return }
        $json = $raw | ConvertFrom-Json
        $services = $json.services
        if (-not $services) { return }
        foreach ($svc in $services.PSObject.Properties) {
            $procId = [int]$svc.Value
            if ($procId -gt 0 -and $procId -ne $PID) {
                try {
                    taskkill /PID $procId /T /F | Out-Null
                } catch {
                    Stop-Process -Id $procId -Force -ErrorAction SilentlyContinue
                }
            }
        }
    } catch {
        Write-Host "[full-start] warning: failed to stop managed processes from pid file"
    }
}

function Wait-PortFree {
    param(
        [Parameter(Mandatory = $true)][int]$Port,
        [int]$TimeoutSeconds = 20
    )
    $sw = [System.Diagnostics.Stopwatch]::StartNew()
    while ($sw.Elapsed.TotalSeconds -lt $TimeoutSeconds) {
        $listeners = Get-NetTCPConnection -LocalPort $Port -State Listen -ErrorAction SilentlyContinue
        if (-not $listeners) {
            return $true
        }
        $owners = @($listeners | Select-Object -ExpandProperty OwningProcess -Unique)
        foreach ($owner in $owners) {
            if ($owner -and $owner -ne $PID) {
                try {
                    taskkill /PID $owner /T /F | Out-Null
                } catch {
                    Stop-Process -Id $owner -Force -ErrorAction SilentlyContinue
                }
            }
        }
        Start-Sleep -Milliseconds 500
    }
    return $false
}

function Wait-PortListening {
    param(
        [Parameter(Mandatory = $true)][int]$Port,
        [int]$TimeoutSeconds = 20
    )
    $sw = [System.Diagnostics.Stopwatch]::StartNew()
    while ($sw.Elapsed.TotalSeconds -lt $TimeoutSeconds) {
        try {
            $listeners = Get-NetTCPConnection -LocalPort $Port -State Listen -ErrorAction SilentlyContinue
            if ($listeners) {
                return $true
            }
        } catch {
            # Retry until timeout
        }
        Start-Sleep -Milliseconds 500
    }
    return $false
}

function Get-PortOwnerIds {
    param([Parameter(Mandatory = $true)][int]$Port)
    try {
        return @(
            Get-NetTCPConnection -LocalPort $Port -State Listen -ErrorAction SilentlyContinue |
                Select-Object -ExpandProperty OwningProcess -Unique
        )
    } catch {
        return @()
    }
}

function Get-PrimaryPortOwner {
    param([Parameter(Mandatory = $true)][int]$Port)
    $owners = @(Get-PortOwnerIds -Port $Port)
    if ($owners.Count -gt 0) {
        return [int]$owners[0]
    }
    return 0
}

function Get-LogTail {
    param(
        [Parameter(Mandatory = $true)][string]$Path,
        [int]$Lines = 40
    )
    if (-not (Test-Path $Path)) {
        return "<log file missing: $Path>"
    }
    try {
        return (Get-Content -Path $Path -Tail $Lines -ErrorAction SilentlyContinue) -join "`n"
    } catch {
        return "<failed reading log: $Path>"
    }
}

function Ensure-Dir {
    param([string]$Path)
    if (-not (Test-Path $Path)) {
        New-Item -Path $Path -ItemType Directory | Out-Null
    }
}

function Import-EnvFile {
    param([string]$Path)
    if (-not (Test-Path $Path)) {
        throw ".env file not found at $Path"
    }
    $lines = Get-Content -Path $Path
    foreach ($line in $lines) {
        $trimmed = $line.Trim()
        if (-not $trimmed -or $trimmed.StartsWith("#")) { continue }
        $eq = $trimmed.IndexOf("=")
        if ($eq -lt 1) { continue }
        $key = $trimmed.Substring(0, $eq).Trim()
        $value = $trimmed.Substring($eq + 1).Trim()
        if (($value.StartsWith('"') -and $value.EndsWith('"')) -or ($value.StartsWith("'") -and $value.EndsWith("'"))) {
            $value = $value.Substring(1, $value.Length - 2)
        }
        [System.Environment]::SetEnvironmentVariable($key, $value, "Process")
    }
}

$root = (Resolve-Path ".").Path
Import-EnvFile -Path (Join-Path $root ".env")

# Strict requirement: risk config must be explicitly present; no fallback defaults.
foreach ($requiredVar in @("ACCOUNT_CAPITAL")) {
    $val = [System.Environment]::GetEnvironmentVariable($requiredVar, "Process")
    if (-not $val) {
        throw "Missing required env var for risk gating: $requiredVar"
    }
}

$signalAbs = [System.Environment]::GetEnvironmentVariable("SIGNAL_MAX_POSITION_VALUE", "Process")
$signalPct = [System.Environment]::GetEnvironmentVariable("SIGNAL_MAX_POSITION_SIZE_PCT", "Process")
$legacyPct = [System.Environment]::GetEnvironmentVariable("MAX_POSITION_SIZE_PCT", "Process")

if (-not $signalAbs -and -not $signalPct -and -not $legacyPct) {
    throw "Missing risk limit env var. Set SIGNAL_MAX_POSITION_VALUE or SIGNAL_MAX_POSITION_SIZE_PCT (preferred), or MAX_POSITION_SIZE_PCT (legacy)."
}

$runDir = Join-Path $root ".run"
Ensure-Dir $runDir

if ($KillExisting) {
    Write-Host "[full-start] stopping listeners on 9000/9006/9008/9009 ..."
    $previousPidFile = Join-Path $runDir "full_start_pids.json"
    Stop-ManagedProcesses -PidFile $previousPidFile
    Stop-PortProcess -Port 9000
    Stop-PortProcess -Port 9006
    Stop-PortProcess -Port 9008
    Stop-PortProcess -Port 9009
    foreach ($port in @(9000, 9006, 9008, 9009)) {
        if (-not (Wait-PortFree -Port $port -TimeoutSeconds 25)) {
            throw "Port $port is still in use after KillExisting. Abort to avoid mixed old/new processes."
        }
    }
}

$instrumentUpper = $Instrument.Trim().ToUpper()
$contractFile = Join-Path $runDir ("startup_contract_{0}.json" -f ($instrumentUpper -replace '[^A-Z0-9_-]', '_'))

Write-Host "[full-start] discovering/applying startup contract for $instrumentUpper ..."
$contractCmd = @(
    "scripts/startup_contract.py",
    "--instrument", $instrumentUpper,
    "--source-base", $SourceBase,
    "--market-api-base", $MarketApiBase,
    "--dashboard-api-base", $DashboardApiBase,
    "--engine-api-base", $EngineApiBase,
    "--apply",
    "--out", $contractFile
)
& python @contractCmd
if ($LASTEXITCODE -ne 0) {
    throw "startup_contract.py failed"
}

$contractJson = Get-Content -Path $contractFile -Raw | ConvertFrom-Json
$contract = $contractJson.startup_contract.contract
$redisHost = [string]$contract.redis.host
$redisPort = [string]$contract.redis.port
$execMode = [string]$contract.execution_mode
$resolvedInstrument = [string]$contract.instrument

if (-not $redisHost -or -not $redisPort -or -not $resolvedInstrument) {
    throw "Invalid contract data in $contractFile"
}

Write-Host ("[full-start] contract resolved: instrument={0} mode={1} redis={2}:{3}" -f $resolvedInstrument, $execMode, $redisHost, $redisPort)

# Export runtime env for child processes (contract is source-of-truth).
$env:REDIS_HOST = $redisHost
$env:REDIS_PORT = $redisPort
$env:INSTRUMENT_SYMBOL = $resolvedInstrument
$env:DEFAULT_INSTRUMENT = $resolvedInstrument
$env:VITE_INSTRUMENT_SYMBOL = $resolvedInstrument
$env:EXECUTION_MODE = $execMode
$env:SYSTEM_EXECUTION_MODE = $execMode
$env:SOURCE_DASHBOARD_BASE_URL = $SourceBase
$env:MARKET_API_BASE_URL = $MarketApiBase
$env:ENGINE_API_BASE_URL = $EngineApiBase
$env:VITE_DASHBOARD_API_URL = $DashboardApiBase
$env:VITE_ENGINE_API_URL = $EngineApiBase
$env:VITE_WS_URL = "ws://localhost:9009"
$env:REDIS_WS_GATEWAY_PORT = "9009"
$env:REDIS_WS_GATEWAY_HOST = "0.0.0.0"
if (-not $env:SIGNAL_MAX_POSITION_SIZE_PCT -and $env:MAX_POSITION_SIZE_PCT) {
    $env:SIGNAL_MAX_POSITION_SIZE_PCT = $env:MAX_POSITION_SIZE_PCT
    Write-Host "[full-start] risk config: mapped legacy MAX_POSITION_SIZE_PCT -> SIGNAL_MAX_POSITION_SIZE_PCT"
}
# Ensure module imports resolve consistently for engine/dashboard subprocesses.
$env:PYTHONPATH = @(
    $root,
    (Join-Path $root "engine_module\src"),
    (Join-Path $root "genai_module\src"),
    (Join-Path $root "core_kernel\src"),
    (Join-Path $root "market_data\src"),
    (Join-Path $root "risk_module\src"),
    (Join-Path $root "news_module\src"),
    (Join-Path $root "user_module\src"),
    (Join-Path $root "dashboard\src")
) -join ";"

Write-Host "[full-start] starting Engine API (9006) ..."
$engineOut = Join-Path $runDir "engine9006.out"
$engineErr = Join-Path $runDir "engine9006.err"
$engineStarted = $false
$wsStarted = $false
$dashStarted = $false
$uiStarted = $false
$engineProc = $null
$wsProc = $null
$dashProc = $null
$uiProc = $null
$engineOwnerPid = 0
$wsOwnerPid = 0
$dashOwnerPid = 0
$uiOwnerPid = 0

try {
    if ((Get-PortOwnerIds -Port 9006).Count -gt 0) {
        throw "Port 9006 is already in use before startup. Run with -KillExisting to clean listeners."
    }
    $engineProc = Start-Process -FilePath python `
        -ArgumentList "-m", "engine_module.api_service" `
        -WorkingDirectory $root `
        -RedirectStandardOutput $engineOut `
        -RedirectStandardError $engineErr `
        -PassThru

    Start-Sleep -Seconds 2
    if ($engineProc.HasExited) {
        $tail = Get-LogTail -Path $engineErr -Lines 80
        throw "Engine API process exited immediately (pid=$($engineProc.Id), exit=$($engineProc.ExitCode)). stderr tail:`n$tail"
    }
    $engineStarted = $true
    if (-not (Wait-HttpOk -Url "$EngineApiBase/health" -TimeoutSeconds 180)) {
        throw "Engine API health check failed on $EngineApiBase/health"
    }
    $engineOwnerPid = Get-PrimaryPortOwner -Port 9006

    Write-Host "[full-start] starting Redis WS gateway (9009) ..."
    if ((Get-PortOwnerIds -Port 9009).Count -gt 0) {
        throw "Port 9009 is already in use before startup. Run with -KillExisting to clean listeners."
    }
    $wsOut = Join-Path $runDir "ws9009.out"
    $wsErr = Join-Path $runDir "ws9009.err"
    $wsProc = Start-Process -FilePath python `
        -ArgumentList "-m", "redis_ws_gateway.main" `
        -WorkingDirectory $root `
        -RedirectStandardOutput $wsOut `
        -RedirectStandardError $wsErr `
        -PassThru

    Start-Sleep -Seconds 1
    if ($wsProc.HasExited) {
        $tail = Get-LogTail -Path $wsErr -Lines 80
        throw "WS gateway process exited immediately (pid=$($wsProc.Id), exit=$($wsProc.ExitCode)). stderr tail:`n$tail"
    }
    $wsStarted = $true
    if (-not (Wait-PortListening -Port 9009 -TimeoutSeconds 30)) {
        $tail = Get-LogTail -Path $wsErr -Lines 80
        throw "WS gateway failed to bind port 9009 within timeout. stderr tail:`n$tail"
    }
    if (-not (Wait-HttpOk -Url "$WsBase/health" -TimeoutSeconds 90)) {
        throw "WS gateway health check failed on $WsBase/health"
    }
    $wsOwnerPid = Get-PrimaryPortOwner -Port 9009

    Write-Host "[full-start] starting Dashboard backend (9000) ..."
    if ((Get-PortOwnerIds -Port 9000).Count -gt 0) {
        throw "Port 9000 is already in use before startup. Run with -KillExisting to clean listeners."
    }
    $dashOut = Join-Path $runDir "dashboard9000.out"
    $dashErr = Join-Path $runDir "dashboard9000.err"
    $dashProc = Start-Process -FilePath python `
        -ArgumentList "scripts/start_dashboard_only.py", "--instrument", $resolvedInstrument, "--skip-contract", "--port", "9000", "--host", "0.0.0.0" `
        -WorkingDirectory $root `
        -RedirectStandardOutput $dashOut `
        -RedirectStandardError $dashErr `
        -PassThru

    Start-Sleep -Seconds 1
    if ($dashProc.HasExited) {
        $tail = Get-LogTail -Path $dashErr -Lines 80
        throw "Dashboard backend process exited immediately (pid=$($dashProc.Id), exit=$($dashProc.ExitCode)). stderr tail:`n$tail"
    }
    $dashStarted = $true
    if (-not (Wait-PortListening -Port 9000 -TimeoutSeconds 30)) {
        $tail = Get-LogTail -Path $dashErr -Lines 80
        throw "Dashboard backend failed to bind port 9000 within timeout. stderr tail:`n$tail"
    }
    if (-not (Wait-HttpOk -Url "$DashboardApiBase/api/health" -TimeoutSeconds 120)) {
        throw "Dashboard backend health check failed on $DashboardApiBase/api/health"
    }
    $dashOwnerPid = Get-PrimaryPortOwner -Port 9000

    Write-Host "[full-start] starting UI (9008) ..."
    if ((Get-PortOwnerIds -Port 9008).Count -gt 0) {
        throw "Port 9008 is already in use before startup. Run with -KillExisting to clean listeners."
    }
    $uiOut = Join-Path $runDir "ui9008.out"
    $uiErr = Join-Path $runDir "ui9008.err"
    $uiProc = Start-Process -FilePath npm.cmd `
        -ArgumentList "run", "dev", "--", "--host", "0.0.0.0", "--port", "9008" `
        -WorkingDirectory (Join-Path $root "dashboard/modular_ui") `
        -RedirectStandardOutput $uiOut `
        -RedirectStandardError $uiErr `
        -PassThru

    Start-Sleep -Seconds 1
    if ($uiProc.HasExited) {
        $tail = Get-LogTail -Path $uiErr -Lines 80
        throw "UI process exited immediately (pid=$($uiProc.Id), exit=$($uiProc.ExitCode)). stderr tail:`n$tail"
    }
    $uiStarted = $true
    if (-not (Wait-PortListening -Port 9008 -TimeoutSeconds 45)) {
        $tail = Get-LogTail -Path $uiErr -Lines 80
        throw "UI failed to bind port 9008 within timeout. stderr tail:`n$tail"
    }
    if (-not (Wait-HttpOk -Url "http://127.0.0.1:9008" -TimeoutSeconds 120)) {
        throw "UI health check failed on http://127.0.0.1:9008"
    }
    $uiOwnerPid = Get-PrimaryPortOwner -Port 9008

    Write-Host "[full-start] reinitialize orchestrator + run one analysis cycle ..."
    $runCmd = @(
        "scripts/startup_contract.py",
        "--instrument", $resolvedInstrument,
        "--source-base", $SourceBase,
        "--market-api-base", $MarketApiBase,
        "--dashboard-api-base", $DashboardApiBase,
        "--engine-api-base", $EngineApiBase,
        "--reinitialize",
        "--run",
        "--out", $contractFile
    )
    & python @runCmd
    if ($LASTEXITCODE -ne 0) {
        throw "startup_contract.py reinitialize/run failed"
    }

    $pidSummary = [ordered]@{
        instrument = $resolvedInstrument
        mode = $execMode
        redis = @{
            host = $redisHost
            port = [int]$redisPort
        }
        services = @{
            engine_api_9006 = $engineOwnerPid
            ws_gateway_9009 = $wsOwnerPid
            dashboard_api_9000 = $dashOwnerPid
            ui_9008 = $uiOwnerPid
        }
        launcher_processes = @{
            engine_launcher = if ($engineProc) { $engineProc.Id } else { 0 }
            ws_launcher = if ($wsProc) { $wsProc.Id } else { 0 }
            dashboard_launcher = if ($dashProc) { $dashProc.Id } else { 0 }
            ui_launcher = if ($uiProc) { $uiProc.Id } else { 0 }
        }
        logs = @{
            engine_out = $engineOut
            engine_err = $engineErr
            ws_out = $wsOut
            ws_err = $wsErr
            dashboard_out = $dashOut
            dashboard_err = $dashErr
            ui_out = $uiOut
            ui_err = $uiErr
            contract = $contractFile
        }
        urls = @{
            ui = "http://127.0.0.1:9008"
            dashboard_health = "$DashboardApiBase/api/health"
            engine_health = "$EngineApiBase/health"
            ws_health = "$WsBase/health"
        }
    }

    $pidFile = Join-Path $runDir "full_start_pids.json"
    $pidSummary | ConvertTo-Json -Depth 8 | Set-Content -Path $pidFile -Encoding UTF8
    $errFile = Join-Path $runDir "start_full_stack.last_error.txt"
    if (Test-Path $errFile) {
        Remove-Item -Path $errFile -Force -ErrorAction SilentlyContinue
    }

    Write-Host ""
    Write-Host "[full-start] SUCCESS"
    Write-Host ("  Instrument: {0}" -f $resolvedInstrument)
    Write-Host ("  Mode:       {0}" -f $execMode)
    Write-Host ("  UI:         http://127.0.0.1:9008")
    Write-Host ("  PID file:   {0}" -f $pidFile)
}
catch {
    $errMessage = $_.Exception.Message
    Write-Host "[full-start] ERROR: $errMessage"
    $errFile = Join-Path $runDir "start_full_stack.last_error.txt"
    Set-Content -Path $errFile -Value ("{0}`n{1}" -f (Get-Date).ToString("o"), $errMessage) -Encoding UTF8

    if ($uiStarted) { Stop-PortProcess -Port 9008 }
    if ($dashStarted) { Stop-PortProcess -Port 9000 }
    if ($wsStarted) { Stop-PortProcess -Port 9009 }
    if ($engineStarted) { Stop-PortProcess -Port 9006 }

    throw
}
