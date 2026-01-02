# PowerShell script to start Redis using Docker
# If Docker is not available, provides instructions for manual setup

Write-Host "Checking for Docker..." -ForegroundColor Cyan

try {
    $dockerVersion = docker --version 2>&1
    if ($LASTEXITCODE -eq 0) {
        Write-Host "Docker found: $dockerVersion" -ForegroundColor Green
        
        # Check if Redis container is already running
        $redisRunning = docker ps --filter "name=redis" --format "{{.Names}}" 2>&1
        if ($redisRunning -eq "redis") {
            Write-Host "Redis container is already running!" -ForegroundColor Green
            exit 0
        }
        
        # Check if Redis container exists but is stopped
        $redisExists = docker ps -a --filter "name=redis" --format "{{.Names}}" 2>&1
        if ($redisExists -eq "redis") {
            Write-Host "Starting existing Redis container..." -ForegroundColor Yellow
            docker start redis
            Start-Sleep -Seconds 2
            docker ps --filter "name=redis"
            Write-Host "Redis started successfully!" -ForegroundColor Green
            exit 0
        }
        
        # Create and start new Redis container
        Write-Host "Starting Redis container..." -ForegroundColor Yellow
        docker run -d --name redis -p 6379:6379 redis:7-alpine
        Start-Sleep -Seconds 2
        
        # Verify it's running
        $redisStatus = docker ps --filter "name=redis" --format "{{.Status}}" 2>&1
        if ($redisStatus) {
            Write-Host "Redis started successfully!" -ForegroundColor Green
            Write-Host "Status: $redisStatus" -ForegroundColor Green
            Write-Host ""
            Write-Host "Redis is now available at localhost:6379" -ForegroundColor Cyan
        } else {
            Write-Host "Failed to start Redis container" -ForegroundColor Red
            exit 1
        }
    } else {
        throw "Docker not found"
    }
} catch {
    Write-Host ""
    Write-Host "Docker is not available on this system." -ForegroundColor Yellow
    Write-Host ""
    Write-Host "To install Redis on Windows:" -ForegroundColor Cyan
    Write-Host "1. Install Docker Desktop: https://www.docker.com/products/docker-desktop" -ForegroundColor White
    Write-Host "2. Or use WSL2: wsl --install" -ForegroundColor White
    Write-Host "3. Or download Redis for Windows: https://github.com/microsoftarchive/redis/releases" -ForegroundColor White
    Write-Host ""
    Write-Host "For now, the system will work in fallback mode without Redis." -ForegroundColor Yellow
    exit 1
}

