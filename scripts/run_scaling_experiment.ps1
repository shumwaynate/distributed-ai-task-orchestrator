param(
    [Parameter(ValueFromRemainingArguments = $true)]
    [int[]]$Workers
)

$Tasks = if ($env:TASKS) { [int]$env:TASKS } else { 20 }
$Delay = if ($env:DELAY) { [int]$env:DELAY } else { 1 }
$Workload = if ($env:WORKLOAD) { $env:WORKLOAD } else { "slow" }
$Size = if ($env:SIZE) { [int]$env:SIZE } else { 75 }
$PollInterval = if ($env:POLL_INTERVAL) { [double]$env:POLL_INTERVAL } else { 0.5 }

Set-Location (Join-Path $PSScriptRoot "..")

if (-not $Workers -or $Workers.Count -eq 0) {
    Write-Host "Usage:"
    Write-Host ".\scripts\run_scaling_experiment.ps1 1 2 4 8"
    exit 1
}

$summary = @()

foreach ($workerCount in $Workers) {

    Write-Host ""
    Write-Host "========================================"
    Write-Host "Starting scaling experiment run"
    Write-Host "Worker containers: $workerCount"
    Write-Host "Tasks: $Tasks"
    Write-Host "Workload: $Workload"
    Write-Host "Size: $Size"
    Write-Host "========================================"
    Write-Host ""

    docker compose down | Out-Null

    $env:WORKER_CONCURRENCY = "1"

    docker compose up --build -d redis api

    if ($LASTEXITCODE -ne 0) {
        Write-Host "Failed to start redis/api containers."
        exit 1
    }

    docker compose up -d --scale worker=$workerCount worker

    if ($LASTEXITCODE -ne 0) {
        Write-Host "Failed to scale worker containers."
        docker compose down | Out-Null
        exit 1
    }

    Write-Host "Waiting for API..."

    $ready = $false

    for ($i = 1; $i -le 30; $i++) {
        try {
            Invoke-WebRequest `
                -Uri "http://127.0.0.1:8000/" `
                -UseBasicParsing `
                -TimeoutSec 2 | Out-Null

            $ready = $true
            break
        }
        catch {
            Start-Sleep -Seconds 1
        }
    }

    if (-not $ready) {
        Write-Host "API did not become ready."

        docker compose logs api

        docker compose down | Out-Null

        exit 1
    }

    Write-Host "API is ready."

    $output = python scripts\benchmark.py `
        --tasks $Tasks `
        --delay $Delay `
        --workers $workerCount `
        --workload $Workload `
        --size $Size `
        --poll-interval $PollInterval

    $output | ForEach-Object { Write-Host $_ }

    $runtimeLine = $output | Select-String "Total runtime:" | Select-Object -Last 1
    $throughputLine = $output | Select-String "Throughput:" | Select-Object -Last 1
    $statusLine = $output | Select-String "Final status:" | Select-Object -Last 1

    $summary += [PSCustomObject]@{
        Workers = $workerCount
        RuntimeSeconds = if ($runtimeLine) {
            $runtimeLine.ToString().Split()[2]
        }
        else {
            "FAILED"
        }

        ThroughputTasksPerSecond = if ($throughputLine) {
            $throughputLine.ToString().Split()[1]
        }
        else {
            "FAILED"
        }

        FinalStatus = if ($statusLine) {
            $statusLine.ToString().Split()[2]
        }
        else {
            "FAILED"
        }
    }

    Write-Host ""
    Write-Host "Stopping containers..."
    docker compose down | Out-Null

    Start-Sleep -Seconds 2
}

Write-Host ""
Write-Host "========================================"
Write-Host "Scaling experiment complete."
Write-Host "========================================"
Write-Host ""

$summary | Format-Table -AutoSize