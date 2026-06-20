param(
    [Parameter(ValueFromRemainingArguments = $true)]
    [int[]]$Workers
)

$Tasks = if ($env:TASKS) {
    [int]$env:TASKS
}
else {
    20
}

$PollInterval = if ($env:POLL_INTERVAL) {
    [double]$env:POLL_INTERVAL
}
else {
    0.5
}

Set-Location (Join-Path $PSScriptRoot "..")

if (-not $Workers -or $Workers.Count -eq 0) {
    Write-Host "Usage:"
    Write-Host ".\scripts\run_scaling_experiment.ps1 1 2 4 8"
    Write-Host ""
    Write-Host "Optional environment variables:"
    Write-Host '$env:TASKS = "20"'
    Write-Host '$env:POLL_INTERVAL = "0.5"'
    exit 1
}

if ($Tasks -lt 2 -or $Tasks -gt 50) {
    Write-Host "TASKS must be between 2 and 50."
    Write-Host "The value is used as the route checkpoint count."
    exit 1
}

foreach ($workerCount in $Workers) {
    if ($workerCount -lt 1) {
        Write-Host "Every worker count must be at least 1."
        exit 1
    }
}

$summary = @()

try {
    foreach ($workerCount in $Workers) {
        Write-Host ""
        Write-Host "========================================"
        Write-Host "Starting Route Risk scaling experiment"
        Write-Host "Worker containers: $workerCount"
        Write-Host "Route-risk tasks/checkpoints: $Tasks"
        Write-Host "Poll interval: $PollInterval seconds"
        Write-Host "========================================"
        Write-Host ""

        docker compose down | Out-Null

        if ($LASTEXITCODE -ne 0) {
            Write-Host "Warning: docker compose down returned an error."
        }

        $env:WORKER_CONCURRENCY = "1"

        docker compose up --build -d redis api

        if ($LASTEXITCODE -ne 0) {
            throw "Failed to start the Redis and API containers."
        }

        docker compose up -d --scale worker=$workerCount worker

        if ($LASTEXITCODE -ne 0) {
            throw "Failed to start $workerCount worker container(s)."
        }

        Write-Host "Waiting for the API..."

        $ready = $false

        for ($attempt = 1; $attempt -le 60; $attempt++) {
            try {
                Invoke-WebRequest `
                    -Uri "http://127.0.0.1:8000/" `
                    -UseBasicParsing `
                    -TimeoutSec 2 |
                    Out-Null

                $ready = $true
                break
            }
            catch {
                Start-Sleep -Seconds 1
            }
        }

        if (-not $ready) {
            Write-Host "The API did not become ready."
            docker compose logs api
            throw "API startup failed."
        }

        Write-Host "API is ready."
        Write-Host "Submitting the real routed Route Risk workload..."
        Write-Host ""

        $output = @(
            python .\scripts\benchmark.py `
                --tasks $Tasks `
                --workers $workerCount `
                --poll-interval $PollInterval `
                2>&1
        )

        $benchmarkExitCode = $LASTEXITCODE

        $output |
            ForEach-Object {
                Write-Host $_
            }

        $runtimeLine = (
            $output |
                Select-String "Total runtime:" |
                Select-Object -Last 1
        )

        $throughputLine = (
            $output |
                Select-String "Throughput:" |
                Select-Object -Last 1
        )

        $statusLine = (
            $output |
                Select-String "Final status:" |
                Select-Object -Last 1
        )

        $runtimeValue = "FAILED"
        $throughputValue = "FAILED"
        $statusValue = "FAILED"

        if ($runtimeLine) {
            $runtimeParts = (
                $runtimeLine.ToString() -split "\s+"
            )

            if ($runtimeParts.Count -ge 3) {
                $runtimeValue = $runtimeParts[2]
            }
        }

        if ($throughputLine) {
            $throughputParts = (
                $throughputLine.ToString() -split "\s+"
            )

            if ($throughputParts.Count -ge 2) {
                $throughputValue = $throughputParts[1]
            }
        }

        if ($statusLine) {
            $statusParts = (
                $statusLine.ToString() -split "\s+"
            )

            if ($statusParts.Count -ge 3) {
                $statusValue = $statusParts[2]
            }
        }

        if ($benchmarkExitCode -ne 0) {
            Write-Host ""
            Write-Host (
                "Benchmark failed for worker count " +
                "$workerCount with exit code $benchmarkExitCode."
            )
        }

        $summary += [PSCustomObject]@{
            Workers = $workerCount
            Tasks = $Tasks
            RuntimeSeconds = $runtimeValue
            ThroughputTasksPerSecond = $throughputValue
            FinalStatus = $statusValue
        }

        Write-Host ""
        Write-Host "Stopping containers for this run..."

        docker compose down | Out-Null

        Start-Sleep -Seconds 2
    }
}
finally {
    Write-Host ""
    Write-Host "Ensuring experiment containers are stopped..."

    docker compose down | Out-Null
}

Write-Host ""
Write-Host "========================================"
Write-Host "Route Risk scaling experiment complete"
Write-Host "========================================"
Write-Host ""

$summary |
    Format-Table -AutoSize

Write-Host ""
Write-Host "Results were appended to:"
Write-Host "benchmarks\results.csv"