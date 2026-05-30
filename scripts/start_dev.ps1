param(
    [int]$Workers = 4
)

Set-Location (Join-Path $PSScriptRoot "..")

Write-Host "Starting Distributed AI Task Orchestrator development environment..."
Write-Host "Worker concurrency: $Workers"

if (Test-Path ".\.venv\Scripts\Activate.ps1") {
    . .\.venv\Scripts\Activate.ps1
} else {
    Write-Host "Could not find Windows virtual environment activation script."
    exit 1
}

Write-Host "Cleaning up old FastAPI and Celery processes..."
Get-Process python -ErrorAction SilentlyContinue | Where-Object {
    $_.Path -like "*python*"
} | Out-Null

Write-Host "Checking Redis..."
redis-cli ping
if ($LASTEXITCODE -ne 0) {
    Write-Host "Redis is not responding. Start Redis first."
    exit 1
}

Write-Host "Starting FastAPI..."
$api = Start-Process powershell -ArgumentList @(
    "-NoExit",
    "-Command",
    ". .\.venv\Scripts\Activate.ps1; uvicorn app.api.main:app --reload"
) -PassThru

Start-Sleep -Seconds 2

Write-Host "Starting Celery worker..."
$worker = Start-Process powershell -ArgumentList @(
    "-NoExit",
    "-Command",
    ". .\.venv\Scripts\Activate.ps1; celery -A app.worker.celery_app worker --loglevel=info --concurrency=$Workers --hostname=worker_${Workers}_windows@%h"
) -PassThru

Write-Host ""
Write-Host "Development environment running."
Write-Host "FastAPI PID: $($api.Id)"
Write-Host "Worker PID: $($worker.Id)"
Write-Host ""
Write-Host "Close the opened PowerShell windows to stop services."