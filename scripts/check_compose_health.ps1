$ports = @(8004,8005,8006,8888,8001,8002,8003)
foreach ($p in $ports) {
    Write-Host "Checking http://localhost:$p/health"
    $ok = $false
    for ($i = 0; $i -lt 18; $i++) {
        try {
            $r = Invoke-WebRequest -UseBasicParsing -Uri ("http://localhost:{0}/health" -f $p) -TimeoutSec 5
            if ($r.StatusCode -eq 200) {
                $content = $r.Content | ConvertFrom-Json
                Write-Host "  [OK] $p ->" $content.status
                $ok = $true
                break
            }
        } catch {
            Start-Sleep -Seconds 5
        }
        Write-Host "  attempt $($i+1) failed, retrying..."
    }
    if (-not $ok) {
        Write-Host "  [FAIL] $p did not become healthy"
    }
}

Write-Host "\nDocker compose ps:"
docker compose ps

Write-Host "\nRecent logs (tail 100) for services not healthy:"
$failed = @()
foreach ($p in $ports) {
    try {
        $r = Invoke-WebRequest -UseBasicParsing -Uri ("http://localhost:{0}/health" -f $p) -TimeoutSec 2
        if ($r.StatusCode -ne 200) { $failed += $p }
    } catch { $failed += $p }
}
if ($failed.Count -gt 0) {
    foreach ($p in $failed) {
        Write-Host "--- Logs for services on port $p ---"
        # Try to map port to service name via docker compose ps
        docker compose ps --service --ports | Select-String "0.0.0.0:$p" | ForEach-Object {
            $svc = $_ -replace ":.*","" -replace "^\s+",""
            if ($svc) {
                Write-Host "Service: $svc"
                docker compose logs --no-color --tail 100 $svc
            }
        }
    }
} else { Write-Host "All services responded OK to /health" }
