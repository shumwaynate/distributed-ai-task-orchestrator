param(
    [int]$Workers = 1
)

$projectRoot = Resolve-Path (Join-Path $PSScriptRoot "..")
Set-Location $projectRoot

Write-Host "Starting Distributed Route Risk Engine development environment..."
Write-Host ""
Write-Host "Windows local development uses one Celery solo worker."
Write-Host "The Workers parameter is retained for command compatibility."
Write-Host "Use the Docker scaling script for multi-worker measurements."

# ============================================================
# VIRTUAL ENVIRONMENT
# ============================================================

$activationScript = Join-Path `
    $projectRoot `
    ".venv\Scripts\Activate.ps1"

if (-not (Test-Path $activationScript)) {
    Write-Host "Could not find the Windows virtual environment."
    Write-Host "Expected: $activationScript"
    exit 1
}

. $activationScript

# ============================================================
# REDIS
# ============================================================

function Test-RedisConnection {
    python -c "import redis; redis.Redis.from_url('redis://localhost:6379/0').ping()" `
        2>$null

    return ($LASTEXITCODE -eq 0)
}

Write-Host ""
Write-Host "Checking Redis..."

if (Test-RedisConnection) {
    Write-Host "Redis is already available on localhost:6379."
}
else {
    Write-Host "Redis is not responding."
    Write-Host "Starting the Docker Compose Redis service..."

    docker --version *> $null

    if ($LASTEXITCODE -ne 0) {
        Write-Host "Docker is unavailable."
        Write-Host "Start Docker Desktop and run this script again."
        exit 1
    }

    docker compose up -d redis

    if ($LASTEXITCODE -ne 0) {
        Write-Host "Docker Compose could not start Redis."
        exit 1
    }

    $redisReady = $false

    for ($attempt = 1; $attempt -le 30; $attempt++) {
        if (Test-RedisConnection) {
            $redisReady = $true
            break
        }

        Start-Sleep -Seconds 1
    }

    if (-not $redisReady) {
        Write-Host "Redis did not become ready."
        docker compose logs --tail 100 redis
        exit 1
    }

    Write-Host "Docker Compose Redis started successfully."
}

# ============================================================
# FASTAPI
# ============================================================

Write-Host ""
Write-Host "Starting FastAPI..."

$apiCommand = @"
Set-Location '$projectRoot'
. '.\.venv\Scripts\Activate.ps1'
uvicorn app.api.main:app --reload
"@

$api = Start-Process `
    powershell `
    -ArgumentList @(
        "-NoExit",
        "-Command",
        $apiCommand
    ) `
    -WorkingDirectory $projectRoot `
    -PassThru

Start-Sleep -Seconds 2

# ============================================================
# CELERY WORKER
# ============================================================

Write-Host "Starting Celery worker..."
Write-Host "Using Celery --pool=solo for Windows stability."

$workerCommand = @"
Set-Location '$projectRoot'
. '.\.venv\Scripts\Activate.ps1'
celery -A app.worker.celery_app worker --loglevel=info --pool=solo --hostname=worker_windows_solo@%h
"@

$worker = Start-Process `
    powershell `
    -ArgumentList @(
        "-NoExit",
        "-Command",
        $workerCommand
    ) `
    -WorkingDirectory $projectRoot `
    -PassThru

# ============================================================
# SUMMARY
# ============================================================

Write-Host ""
Write-Host "Development environment started."
Write-Host "FastAPI PID: $($api.Id)"
Write-Host "Celery worker PID: $($worker.Id)"
Write-Host ""
Write-Host "API documentation:"
Write-Host "http://localhost:8000/docs"
Write-Host ""
Write-Host "Primary endpoints:"
Write-Host "POST http://localhost:8000/submit_routed_route_risk_job"
Write-Host "POST http://localhost:8000/submit_route_comparison_job"
Write-Host ""
Write-Host "Close the opened PowerShell windows to stop FastAPI and Celery."
Write-Host "Redis is managed through the project's Docker Compose service."
