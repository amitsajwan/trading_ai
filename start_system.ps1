#!/usr/bin/env pwsh
<#
.SYNOPSIS
    Start the complete trading system with dashboard

.DESCRIPTION
    This script starts:
    1. Redis (if not running)
    2. WebSocket Tick Collector (live market data)
    3. Market Data API (port 8004)
    4. Dashboard (port 8000)

.PARAMETER Mode
    The mode to run in: 'live', 'historical', or 'paper'
    Default: 'live'

.EXAMPLE
    .\start_system.ps1
    .\start_system.ps1 -Mode historical
#>

param(
    [ValidateSet('live', 'historical', 'paper')]
    [string]$Mode = 'live'
)

$ErrorActionPreference = "Stop"

Write-Host "[*] Starting Trading System" -ForegroundColor Cyan
Write-Host "Mode: $Mode" -ForegroundColor Yellow
Write-Host ""

# Activate virtual environment (optional)
$venvPaths = @(
    "c:\code\zerodha\.venv\Scripts\Activate.ps1",
    "c:\code\zerodha\venv\Scripts\Activate.ps1",
    "c:\code\zerodha\market_data\.venv\Scripts\Activate.ps1"
)

$venvActivated = $false
foreach ($venvPath in $venvPaths) {
    if (Test-Path $venvPath) {
        Write-Host "[+] Activating virtual environment..." -ForegroundColor Green
        & $venvPath
        $venvActivated = $true
        break
    }
}

if (-not $venvActivated) {
    Write-Host "[!] Virtual environment not found" -ForegroundColor Yellow
    Write-Host "   Continuing with system Python..." -ForegroundColor Yellow
}

# Check Redis
Write-Host ""
Write-Host "[*] Checking Redis..." -ForegroundColor Cyan
try {
    # Check if Redis container is running
    $redisContainer = docker ps --filter "name=zerodha-redis" --format "{{.Names}}" 2>&1
    if ($redisContainer -match "zerodha-redis") {
        Write-Host "[+] Redis container is running" -ForegroundColor Green
    } else {
        # Try to start existing container
        Write-Host "   Starting existing Redis container..." -ForegroundColor Yellow
        $startResult = docker start zerodha-redis 2>&1
        if ($LASTEXITCODE -eq 0) {
            Write-Host "[+] Redis container started" -ForegroundColor Green
            Start-Sleep -Seconds 2
        } else {
            Write-Host "[!] Could not start Redis. System may not work properly." -ForegroundColor Yellow
        }
    }
} catch {
    Write-Host "[!] Docker/Redis check failed: $_" -ForegroundColor Yellow
    Write-Host "   System will attempt to continue..." -ForegroundColor Yellow
}

# Set environment based on mode
$envFile = "c:\code\zerodha\market_data\.env"
if ($Mode -eq 'historical') {
    $envFile = "c:\code\zerodha\market_data\.env.banknifty"
}

if (Test-Path $envFile) {
    Write-Host "[+] Loading environment from $envFile" -ForegroundColor Green
    Get-Content $envFile | ForEach-Object {
        if ($_ -match '^([^=]+)=(.*)$') {
            $key = $matches[1].Trim()
            $value = $matches[2].Trim()
            [Environment]::SetEnvironmentVariable($key, $value, 'Process')
        }
    }
} else {
    Write-Host "[!] Environment file not found: $envFile" -ForegroundColor Yellow
}

# Function to start a background process
function Start-BackgroundService {
    param(
        [string]$Name,
        [string]$Command,
        [string]$WorkingDir,
        [int]$Port = 0
    )
    
    Write-Host ""
    Write-Host "[*] Starting $Name..." -ForegroundColor Cyan
    
    # Check if port is already in use
    if ($Port -gt 0) {
        $portCheck = Get-NetTCPConnection -LocalPort $Port -ErrorAction SilentlyContinue
        if ($portCheck) {
            Write-Host "WARNING: Port $Port is already in use. Service may already be running." -ForegroundColor Yellow
            return $null
        }
    }
    
    $cmdString = "cd '$WorkingDir'; `$env:PYTHONPATH='src'; $Command"
    $process = Start-Process powershell -ArgumentList "-NoExit", "-Command", $cmdString -PassThru -WindowStyle Minimized
    Write-Host "SUCCESS: $Name started (PID: $($process.Id))" -ForegroundColor Green
    
    if ($Port -gt 0) {
        Write-Host "  Listening on port $Port" -ForegroundColor Gray
    }
    
    return $process
}

# Start services based on mode
$processes = @()

Push-Location "c:\code\zerodha\market_data"

if ($Mode -eq 'live') {
    Write-Host ""
    Write-Host "[LIVE MODE] Starting services..." -ForegroundColor Magenta
    
    # Start WebSocket Collector
    $wsProcess = Start-BackgroundService `
        -Name "WebSocket Tick Collector" `
        -Command "python -m market_data.collectors.websocket_tick_collector" `
        -WorkingDir "c:\code\zerodha\market_data"
    $processes += $wsProcess
    
    Start-Sleep -Seconds 3
}
elseif ($Mode -eq 'historical') {
    Write-Host ""
    Write-Host "[HISTORICAL MODE] Starting services..." -ForegroundColor Magenta
    
    # Start Historical Replayer
    $histProcess = Start-BackgroundService `
        -Name "Historical Data Replayer" `
        -Command "python src\market_data\adapters\historical_replay.py" `
        -WorkingDir "c:\code\zerodha\market_data"
    $processes += $histProcess
    
    Start-Sleep -Seconds 2
}

# Start Market Data API
$apiProcess = Start-BackgroundService `
    -Name "Market Data API" `
    -Command "python start_api.py" `
    -WorkingDir "c:\code\zerodha\market_data" `
    -Port 8004
$processes += $apiProcess

Start-Sleep -Seconds 3

Pop-Location

# Start Dashboard
$dashProcess = Start-BackgroundService `
    -Name "Market Data Dashboard" `
    -Command "python start_dashboard.py" `
    -WorkingDir "c:\code\zerodha\market_data_dashboard" `
    -Port 8000
$processes += $dashProcess

# Summary
Write-Host ""
Write-Host "═══════════════════════════════════════════════════" -ForegroundColor Cyan
Write-Host "[SUCCESS] System Started Successfully!" -ForegroundColor Green
Write-Host "═══════════════════════════════════════════════════" -ForegroundColor Cyan
Write-Host ""
Write-Host "Dashboard:    http://localhost:8000" -ForegroundColor White
Write-Host "API:          http://localhost:8004" -ForegroundColor White
Write-Host "API Docs:     http://localhost:8004/docs" -ForegroundColor White
Write-Host ""
Write-Host "Running Mode:    $Mode" -ForegroundColor Yellow
Write-Host "Active Services: $($processes.Count)" -ForegroundColor Yellow
Write-Host ""
Write-Host "Press Ctrl+C in service windows to stop individual services" -ForegroundColor Gray
Write-Host "Or use 'docker stop redis' to stop Redis" -ForegroundColor Gray
Write-Host ""

# Keep script running and monitor processes
Write-Host "Monitoring services (press Ctrl+C to exit monitor)..." -ForegroundColor Cyan
try {
    while ($true) {
        Start-Sleep -Seconds 10
        
        # Check if any process has exited
        foreach ($proc in $processes) {
            if ($proc -and $proc.HasExited) {
                Write-Host "[!] Warning: Process $($proc.Id) has exited" -ForegroundColor Yellow
            }
        }
    }
} catch {
    Write-Host ""
    Write-Host "Monitoring stopped. Services are still running in background." -ForegroundColor Yellow
}
