#!/usr/bin/env pwsh
<#
.SYNOPSIS
    Stop services started by start_system.ps1 (PowerShell-native).
#>

$ErrorActionPreference = 'Stop'
$root = Split-Path -Parent $MyInvocation.MyCommand.Path
$runDir = Join-Path $root '.run'

function Stop-TrackedProcess {
    param([string]$Name)
    $pidFile = Join-Path $runDir "$Name.pid"
    if (Test-Path $pidFile) {
        $processId = Get-Content $pidFile -ErrorAction SilentlyContinue
        if ($processId) {
            try {
                Stop-Process -Id ([int]$processId) -Force -ErrorAction Stop
                Write-Host "[stop_system] Stopped $Name (pid=$processId)" -ForegroundColor Yellow
            } catch {
                Write-Host "[stop_system] $Name not running (pid=$processId)" -ForegroundColor DarkYellow
            }
        }
        Remove-Item $pidFile -Force -ErrorAction SilentlyContinue
        return $true
    }
    return $false
}

$stoppedAny = $false
if (Stop-TrackedProcess 'dashboard') { $stoppedAny = $true }
if (Stop-TrackedProcess 'market_data') { $stoppedAny = $true }

if ($stoppedAny) {
    Write-Host "[stop_system] ✅ Done" -ForegroundColor Green
} else {
    Write-Host "[stop_system] No tracked processes were running" -ForegroundColor Yellow
}
