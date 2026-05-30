param(
    [int]$Workers = 4
)

Set-Location (Join-Path $PSScriptRoot "..")

Write-Host "Starting Distributed AI Task Orchestrator development environment..."
Write-Host "Requested worker concurrency: $Workers"

# ============================================================
# ORIGINAL ORCHESTRATOR LOGIC
# ============================================================
#
# This script starts the local development environment for:
# - FastAPI
# - Celery workers
# - Redis-backed task orchestration
#
# Windows-specific note:
# Celery's default prefork pool can be unstable on Windows and may throw:
#
#     PermissionError: [WinError 5] Access is denied
#
# For local Windows development, this script uses:
#
#     --pool=solo
#
# That means the local worker runs safely as one process.
#
# For actual scaling experiments, use Docker worker container scaling instead
# of relying on Windows multiprocessing.

if (Test-Path ".\.venv\Scripts\Activate.ps1") {
    . .\.venv\Scripts\Activate.ps1
} else {
    Write-Host "Could not find Windows virtual environment activation script."
    exit 1
}

Write-Host "Cleaning up note:"
Write-Host "Close any old FastAPI or Celery PowerShell windows from previous runs if they are still open."

# ============================================================
# REDIS CHECK / DOCKER REDIS STARTUP
# ============================================================

function Test-RedisConnection {
    python -c "import redis; r = redis.Redis.from_url('redis://localhost:6379/0'); r.ping(); print('Redis ping successful')" 2>$null

    if ($LASTEXITCODE -eq 0) {
        return $true
    }

    return $false
}

Write-Host "Checking Redis using Python..."

if (Test-RedisConnection) {
    Write-Host "Redis is already running."
} else {
    Write-Host "Redis is not responding on localhost:6379."
    Write-Host "Attempting to start Redis using Docker..."

    $dockerAvailable = $true
    docker --version *> $null

    if ($LASTEXITCODE -ne 0) {
        $dockerAvailable = $false
    }

    if (-not $dockerAvailable) {
        Write-Host "Docker does not appear to be available."
        Write-Host "Please start Docker Desktop, then run this script again."
        exit 1
    }

    $redisContainerName = "distributed-ai-redis"

    $existingRedisContainer = docker ps -a --filter "name=$redisContainerName" --format "{{.Names}}"

    if ($existingRedisContainer -contains $redisContainerName) {
        Write-Host "Found existing Redis container. Starting it..."
        docker start $redisContainerName *> $null
    } else {
        Write-Host "Creating new Redis container named $redisContainerName..."
        docker run -d `
            --name $redisContainerName `
            -p 6379:6379 `
            redis:7-alpine *> $null
    }

    Start-Sleep -Seconds 3

    if (Test-RedisConnection) {
        Write-Host "Redis started successfully through Docker."
    } else {
        Write-Host "Redis still is not responding."
        Write-Host "Check Docker Desktop and make sure port 6379 is available."
        exit 1
    }
}

# ============================================================
# FASTAPI STARTUP
# ============================================================

Write-Host "Starting FastAPI..."

$api = Start-Process powershell -ArgumentList @(
    "-NoExit",
    "-Command",
    ". .\.venv\Scripts\Activate.ps1; uvicorn app.api.main:app --reload"
) -PassThru

Start-Sleep -Seconds 2

# ============================================================
# CELERY WORKER STARTUP
# ============================================================
#
# Windows local development uses --pool=solo to avoid prefork/billiard
# permission errors.
#
# The $Workers parameter is still displayed because the same script structure
# supports the project idea of configurable worker counts, but on Windows local
# solo mode, Celery will process one task at a time.
#
# For real scaling:
# - Use Docker worker containers.
# - Scale containers instead of using Windows prefork multiprocessing.

Write-Host "Starting Celery worker..."
Write-Host "Windows local mode: using Celery --pool=solo for stability."

$worker = Start-Process powershell -ArgumentList @(
    "-NoExit",
    "-Command",
    ". .\.venv\Scripts\Activate.ps1; celery -A app.worker.celery_app worker --loglevel=info --pool=solo --hostname=worker_windows_solo@%h"
) -PassThru

# ============================================================
# ROUTE RISK ENGINE NOTE
# ============================================================
#
# Route Risk Engine tasks are now available inside app.worker.tasks.
# They reuse this same Redis + Celery infrastructure.
#
# Current route-risk endpoint:
# POST /submit_route_risk_job

Write-Host ""
Write-Host "Development environment running."
Write-Host "FastAPI PID: $($api.Id)"
Write-Host "Worker PID: $($worker.Id)"
Write-Host ""
Write-Host "Available route-risk endpoint:"
Write-Host "POST http://localhost:8000/submit_route_risk_job"
Write-Host ""
Write-Host "Windows note:"
Write-Host "This local script uses Celery solo pool for stability."
Write-Host "Use Docker worker scaling for real multi-worker performance tests."
Write-Host ""
Write-Host "Close the opened PowerShell windows to stop FastAPI and Celery."
Write-Host "Redis Docker container can remain running for future tests."