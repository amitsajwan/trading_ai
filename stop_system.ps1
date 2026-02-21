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

# On Windows, force-killing the supervisor may leave child Python processes alive.
# Clean up any orphaned market_data processes for this workspace.
try {
    $rootNorm = $root.Replace('\\', '\\')
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
            Write-Host "[stop_system] Stopped orphan (pid=$($p.ProcessId))" -ForegroundColor Yellow
            $stoppedAny = $true
        } catch {}
    }
} catch {}

if ($stoppedAny) {
    Write-Host "[stop_system] ✅ Done" -ForegroundColor Green
} else {
    Write-Host "[stop_system] No tracked processes were running" -ForegroundColor Yellow
}
