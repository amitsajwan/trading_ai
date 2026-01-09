<#
Comprehensive API verification script
Checks all services and their endpoints after system startup
#>

param(
    [int]$TimeoutSeconds = 10
)

function Write-Status($msg) { Write-Host "[verify] $msg" -ForegroundColor Cyan }
function Write-Success($msg) { Write-Host "✅ $msg" -ForegroundColor Green }
function Write-Error($msg) { Write-Host "❌ $msg" -ForegroundColor Red }
function Write-Warning($msg) { Write-Host "⚠️  $msg" -ForegroundColor Yellow }

function Test-Endpoint($url, $description, $timeoutSec = 10) {
    Write-Status "Testing $description..."
    try {
        $response = Invoke-WebRequest -Uri $url -UseBasicParsing -TimeoutSec $timeoutSec -ErrorAction Stop
        Write-Success "$description - Status: $($response.StatusCode)"
        try {
            $json = $response.Content | ConvertFrom-Json
            return @{ ok = $true; status = $response.StatusCode; data = $json }
        } catch {
            return @{ ok = $true; status = $response.StatusCode; data = $response.Content }
        }
    } catch {
        Write-Error "$description - Failed: $($_.Exception.Message)"
        return @{ ok = $false; error = $_.Exception.Message }
    }
}

Write-Host "`n========== COMPREHENSIVE API VERIFICATION ==========`n" -ForegroundColor Cyan

# Step 1: Market Data API (port 8004)
Write-Host "`n--- Step 1: Market Data API (port 8004) ---" -ForegroundColor Yellow
$health1 = Test-Endpoint "http://localhost:8004/health" "Market Data /health"
$tick1 = Test-Endpoint "http://localhost:8004/api/v1/market/tick/BANKNIFTY" "Market Data /api/v1/market/tick/BANKNIFTY"
if ($tick1.ok) {
    $tickData = $tick1.data
    if ($tickData.timestamp) {
        Write-Status "Tick timestamp: $($tickData.timestamp)"
        if ($tickData.price) {
            Write-Status "Tick price: $($tickData.price)"
        }
        if ($tickData.volume) {
            Write-Status "Tick volume: $($tickData.volume)"
        }
    }
}

# Step 2: News API (port 8005)
Write-Host "`n--- Step 2: News API (port 8005) ---" -ForegroundColor Yellow
$health2 = Test-Endpoint "http://localhost:8005/health" "News API /health"
$news1 = Test-Endpoint "http://localhost:8005/api/v1/news/BANKNIFTY" "News API /api/v1/news/BANKNIFTY"
$sentiment1 = Test-Endpoint "http://localhost:8005/api/v1/news/BANKNIFTY/sentiment" "News API /api/v1/news/BANKNIFTY/sentiment"
if ($news1.ok) {
    $newsData = $news1.data
    if ($newsData -is [array]) {
        Write-Status "News count: $($newsData.Count)"
    } elseif ($newsData.news -is [array]) {
        Write-Status "News count: $($newsData.news.Count)"
    }
}
if ($sentiment1.ok) {
    $sentimentData = $sentiment1.data
    if ($sentimentData.sentiment) {
        Write-Status "Sentiment: $($sentimentData.sentiment)"
    }
    if ($sentimentData.score) {
        Write-Status "Sentiment score: $($sentimentData.score)"
    }
}

# Step 3: Engine API (port 8006)
Write-Host "`n--- Step 3: Engine API (port 8006) ---" -ForegroundColor Yellow
$health3 = Test-Endpoint "http://localhost:8006/health" "Engine API /health"
$signals1 = Test-Endpoint "http://localhost:8006/api/v1/signals/BANKNIFTY" "Engine API /api/v1/signals/BANKNIFTY"
if ($signals1.ok) {
    $signalsData = $signals1.data
    if ($signalsData -is [array]) {
        Write-Status "Signals count: $($signalsData.Count)"
    } elseif ($signalsData.signals -is [array]) {
        Write-Status "Signals count: $($signalsData.signals.Count)"
    }
}

# Step 4.5: User API (port 8007)
Write-Host "`n--- Step 4.5: User API (port 8007) ---" -ForegroundColor Yellow
$health4 = Test-Endpoint "http://localhost:8007/health" "User API /health"

# Step 5: Dashboard UI (port 8888)
Write-Host "`n--- Step 5: Dashboard UI (port 8888) ---" -ForegroundColor Yellow
$ui1 = Test-Endpoint "http://localhost:8888/" "Dashboard UI /"
$proxy1 = Test-Endpoint "http://localhost:8888/api/market-data/tick/BANKNIFTY" "Dashboard proxy /api/market-data/tick/BANKNIFTY"

# Summary
Write-Host "`n========== VERIFICATION SUMMARY ==========" -ForegroundColor Cyan
$services = @(
    @{ name = "Market Data API"; health = $health1.ok; data = $tick1.ok },
    @{ name = "News API"; health = $health2.ok; data = $news1.ok },
    @{ name = "Engine API"; health = $health3.ok; data = $signals1.ok },
    @{ name = "User API"; health = $health4.ok; data = $false },
    @{ name = "Dashboard UI"; health = $ui1.ok; data = $proxy1.ok }
)

foreach ($svc in $services) {
    $status = if ($svc.health -and $svc.data) { "✅ PASS" } elseif ($svc.health) { "⚠️  PARTIAL" } else { "❌ FAIL" }
    Write-Host "$($svc.name): $status" -ForegroundColor $(if ($svc.health -and $svc.data) { "Green" } elseif ($svc.health) { "Yellow" } else { "Red" })
}

Write-Host "`nVerification complete.`n" -ForegroundColor Cyan
