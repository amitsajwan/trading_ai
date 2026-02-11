#!/usr/bin/env pwsh
<#
.SYNOPSIS
    Stop all trading system services

.DESCRIPTION
    Stops all running services and cleans up connections
#>

Write-Host "[STOP] Stopping Trading System..." -ForegroundColor Red
Write-Host ""

# Function to stop processes on a port
function Stop-ProcessOnPort {
    param([int]$Port)
    
    $connections = Get-NetTCPConnection -LocalPort $Port -ErrorAction SilentlyContinue
    if ($connections) {
        foreach ($conn in $connections) {
            $process = Get-Process -Id $conn.OwningProcess -ErrorAction SilentlyContinue
            if ($process) {
                Write-Host "Stopping $($process.Name) (PID: $($process.Id)) on port $Port" -ForegroundColor Yellow
                Stop-Process -Id $process.Id -Force -ErrorAction SilentlyContinue
            }
        }
        Write-Host "[+] Stopped services on port $Port" -ForegroundColor Green
    }
}

# Stop services by port
Write-Host "Stopping Dashboard (port 8000)..." -ForegroundColor Cyan
Stop-ProcessOnPort -Port 8000

Write-Host "Stopping API (port 8004)..." -ForegroundColor Cyan
Stop-ProcessOnPort -Port 8004

# Stop Python processes (WebSocket collector, etc.)
Write-Host ""
Write-Host "Stopping Python services..." -ForegroundColor Cyan
$pythonProcesses = Get-Process python -ErrorAction SilentlyContinue | Where-Object {
    $_.MainWindowTitle -match "market_data|websocket" -or
    $_.CommandLine -match "market_data|websocket"
}

foreach ($proc in $pythonProcesses) {
    Write-Host "Stopping Python process (PID: $($proc.Id))" -ForegroundColor Yellow
    Stop-Process -Id $proc.Id -Force -ErrorAction SilentlyContinue
}

if ($pythonProcesses.Count -gt 0) {
    Write-Host "[+] Stopped $($pythonProcesses.Count) Python service(s)" -ForegroundColor Green
}

Write-Host ""
Write-Host "[SUCCESS] System stopped" -ForegroundColor Green
Write-Host ""
Write-Host "Note: Redis is still running. Use 'docker stop redis' to stop it." -ForegroundColor Gray
