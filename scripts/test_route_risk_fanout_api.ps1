Set-Location (Join-Path $PSScriptRoot "..")

Write-Host ""
Write-Host "============================================================"
Write-Host "ROUTE RISK LIVE WEATHER FAN-OUT API TEST"
Write-Host "============================================================"
Write-Host ""

# ============================================================
# ROUTE RISK ENGINE LIVE WEATHER FAN-OUT API TEST
# ============================================================
#
# Purpose:
# - Submit a larger route-risk job to FastAPI.
# - Use 8 route segments with latitude and longitude values.
# - Enable live weather mode.
# - Prove that one route request can fan out into many Celery tasks.
# - Prove each Celery task can fetch live weather from Open-Meteo.
# - Save the returned job_id automatically.
# - Poll job status until the job finishes.
# - Fetch raw task results.
# - Fetch the clean user-facing route-risk summary.
#
# Requirements:
# - Docker Desktop must be running.
# - FastAPI must be running.
# - Redis must be running.
# - Celery worker must be running.
# - Internet access must be available.
# - Open-Meteo API must be reachable.
#
# Start the app first with:
#
#     .\scripts\start_dev.ps1
#
# Then run this script from the project root:
#
#     .\scripts\test_route_risk_fanout_api.ps1

$body = @{
    route_name = "Rexburg to Idaho Falls Live Weather Fan-Out Test Route"
    origin = "Rexburg, ID"
    destination = "Idaho Falls, ID"
    use_live_weather = $true
    segments = @(
        @{
            label = "Rexburg to Thornton"
            latitude = 43.7742
            longitude = -111.8118

            weather = @{
                temperature_f = 0
                wind_mph = 0
                condition = "ignored because live weather is enabled"
                visibility_miles = $null
            }

            road_condition = "normal"
            is_night = $false
        },
        @{
            label = "Thornton to South Rexburg Junction"
            latitude = 43.7068
            longitude = -111.8670

            weather = @{
                temperature_f = 0
                wind_mph = 0
                condition = "ignored because live weather is enabled"
                visibility_miles = $null
            }

            road_condition = "normal"
            is_night = $false
        },
        @{
            label = "South Rexburg Junction to Rigby North"
            latitude = 43.6505
            longitude = -111.9115

            weather = @{
                temperature_f = 0
                wind_mph = 0
                condition = "ignored because live weather is enabled"
                visibility_miles = $null
            }

            road_condition = "normal"
            is_night = $false
        },
        @{
            label = "Rigby North to Rigby South"
            latitude = 43.6108
            longitude = -111.9558

            weather = @{
                temperature_f = 0
                wind_mph = 0
                condition = "ignored because live weather is enabled"
                visibility_miles = $null
            }

            road_condition = "construction"
            is_night = $false
        },
        @{
            label = "Rigby South to Lorenzo"
            latitude = 43.5749
            longitude = -111.9815

            weather = @{
                temperature_f = 0
                wind_mph = 0
                condition = "ignored because live weather is enabled"
                visibility_miles = $null
            }

            road_condition = "normal"
            is_night = $false
        },
        @{
            label = "Lorenzo to Idaho Falls North"
            latitude = 43.5456
            longitude = -112.0064

            weather = @{
                temperature_f = 0
                wind_mph = 0
                condition = "ignored because live weather is enabled"
                visibility_miles = $null
            }

            road_condition = "normal"
            is_night = $false
        },
        @{
            label = "Idaho Falls North to Central Idaho Falls"
            latitude = 43.5125
            longitude = -112.0298

            weather = @{
                temperature_f = 0
                wind_mph = 0
                condition = "ignored because live weather is enabled"
                visibility_miles = $null
            }

            road_condition = "construction"
            is_night = $false
        },
        @{
            label = "Central Idaho Falls to Downtown Idaho Falls"
            latitude = 43.4927
            longitude = -112.0408

            weather = @{
                temperature_f = 0
                wind_mph = 0
                condition = "ignored because live weather is enabled"
                visibility_miles = $null
            }

            road_condition = "normal"
            is_night = $false
        }
    )
} | ConvertTo-Json -Depth 10

Write-Host "Submitting live-weather route-risk fan-out job..."
Write-Host ""

try {
    $response = Invoke-RestMethod `
        -Uri "http://localhost:8000/submit_route_risk_job" `
        -Method Post `
        -ContentType "application/json" `
        -Body $body
} catch {
    Write-Host "ERROR: Failed to submit live-weather route-risk fan-out job."
    Write-Host "Make sure FastAPI is running at http://localhost:8000"
    Write-Host ""
    Write-Host $_
    exit 1
}

Write-Host "Submit response:"
$response | ConvertTo-Json -Depth 10

$jobId = $response.job_id

Write-Host ""
Write-Host "Saved job ID automatically:"
Write-Host $jobId

# ============================================================
# POLL JOB STATUS UNTIL COMPLETE
# ============================================================
#
# Fan-out live weather jobs can take longer because each segment task calls
# an external weather API.
#
# This loop waits until all tasks finish before fetching final results.

Write-Host ""
Write-Host "Polling job status until complete..."
Write-Host ""

$maxAttempts = 60
$attempt = 0
$status = $null

while ($attempt -lt $maxAttempts) {
    $attempt++

    try {
        $status = Invoke-RestMethod `
            -Uri "http://localhost:8000/job_status/$jobId" `
            -Method Get
    } catch {
        Write-Host "ERROR: Failed to retrieve job status."
        Write-Host $_
        exit 1
    }

    Write-Host "Attempt $attempt/$maxAttempts - Status: $($status.status), Progress: $($status.progress_percent)%"

    if (
        $status.status -eq "SUCCESS" -or
        $status.status -eq "PARTIAL_FAILURE"
    ) {
        break
    }

    Start-Sleep -Seconds 2
}

if ($null -eq $status) {
    Write-Host "ERROR: No job status was returned."
    exit 1
}

if ($status.status -ne "SUCCESS" -and $status.status -ne "PARTIAL_FAILURE") {
    Write-Host ""
    Write-Host "ERROR: Job did not finish before timeout."
    Write-Host "Final observed status:"
    $status | ConvertTo-Json -Depth 10
    exit 1
}

Write-Host ""
Write-Host "Final job status:"
$status | ConvertTo-Json -Depth 10

Write-Host ""
Write-Host "Fetching raw job results..."
Write-Host ""

try {
    $results = Invoke-RestMethod `
        -Uri "http://localhost:8000/results/$jobId" `
        -Method Get
} catch {
    Write-Host "ERROR: Failed to retrieve raw job results."
    Write-Host $_
    exit 1
}

Write-Host "Raw job results:"
$results | ConvertTo-Json -Depth 40

Write-Host ""
Write-Host "Fetching clean route-risk summary..."
Write-Host ""

try {
    $summary = Invoke-RestMethod `
        -Uri "http://localhost:8000/route_risk_summary/$jobId" `
        -Method Get
} catch {
    Write-Host "ERROR: Failed to retrieve clean route-risk summary."
    Write-Host $_
    exit 1
}

Write-Host "Clean route-risk summary:"
$summary | ConvertTo-Json -Depth 40

Write-Host ""
Write-Host "============================================================"
Write-Host "LIVE WEATHER FAN-OUT TEST SUMMARY"
Write-Host "============================================================"
Write-Host ""

Write-Host "Expected task count: 8"
Write-Host "Actual task count: $($response.task_count)"
Write-Host "Expected coordinate-enabled segment count: 8"
Write-Host "Actual coordinate-enabled segment count: $($summary.coordinate_segment_count)"
Write-Host "Job status: $($status.status)"
Write-Host "Progress percent: $($status.progress_percent)"

Write-Host ""
Write-Host "Clean summary endpoint:"
Write-Host "Route status: $($summary.route_status)"
Write-Host "Route name: $($summary.route_name)"
Write-Host "Origin: $($summary.origin)"
Write-Host "Destination: $($summary.destination)"
Write-Host "Segment count: $($summary.segment_count)"
Write-Host "Weather mode: $($summary.weather_mode)"
Write-Host "Route risk score: $($summary.route_risk_score)"
Write-Host "Route risk level: $($summary.route_risk_level)"

if ($summary.highest_risk_segment) {
    Write-Host "Highest-risk segment: $($summary.highest_risk_segment.segment_label)"
    Write-Host "Highest-risk latitude: $($summary.highest_risk_segment.latitude)"
    Write-Host "Highest-risk longitude: $($summary.highest_risk_segment.longitude)"

    if ($summary.highest_risk_segment.weather) {
        Write-Host "Highest-risk weather source: $($summary.highest_risk_segment.weather.source)"
        Write-Host "Highest-risk weather condition: $($summary.highest_risk_segment.weather.condition)"
        Write-Host "Highest-risk temperature F: $($summary.highest_risk_segment.weather.temperature_f)"
        Write-Host "Highest-risk wind MPH: $($summary.highest_risk_segment.weather.wind_mph)"
    }

    Write-Host "Highest-risk segment score: $($summary.highest_risk_segment.risk_score)"
    Write-Host "Highest-risk segment level: $($summary.highest_risk_segment.risk_level)"
}

Write-Host ""
Write-Host "Route summary:"
Write-Host $summary.summary

Write-Host ""
Write-Host "============================================================"
Write-Host "END ROUTE RISK LIVE WEATHER FAN-OUT API TEST"
Write-Host "============================================================"
Write-Host ""