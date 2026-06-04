Set-Location (Join-Path $PSScriptRoot "..")

Write-Host ""
Write-Host "============================================================"
Write-Host "ROUTE RISK API LIVE WEATHER TEST"
Write-Host "============================================================"
Write-Host ""

# ============================================================
# ROUTE RISK ENGINE API LIVE WEATHER TEST
# ============================================================
#
# Purpose:
# - Submit a route-risk job to FastAPI.
# - Use latitude and longitude for each route segment.
# - Enable live weather mode.
# - Save the returned job_id automatically.
# - Poll job status until the job finishes.
# - Fetch raw results only after the job is complete.
# - Fetch the clean user-facing route-risk summary.
# - Print readable JSON output.
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
#     .\scripts\test_route_risk_api.ps1

$body = @{
    route_name = "Rexburg to Idaho Falls Live Weather Test Route"
    origin = "Rexburg, ID"
    destination = "Idaho Falls, ID"
    use_live_weather = $true
    segments = @(
        @{
            label = "Rexburg to Rigby"

            # Approximate route analysis point near Rexburg / US-20.
            latitude = 43.7419
            longitude = -111.8464

            # This weather block remains in the request for compatibility,
            # but live weather mode ignores it for scoring.
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
            label = "Rigby to Idaho Falls"

            # Approximate route analysis point near Rigby / US-20.
            latitude = 43.5987
            longitude = -111.9716

            # This weather block remains in the request for compatibility,
            # but live weather mode ignores it for scoring.
            weather = @{
                temperature_f = 0
                wind_mph = 0
                condition = "ignored because live weather is enabled"
                visibility_miles = $null
            }

            road_condition = "construction"
            is_night = $false
        }
    )
} | ConvertTo-Json -Depth 10

Write-Host "Submitting live-weather route-risk job..."
Write-Host ""

try {
    $response = Invoke-RestMethod `
        -Uri "http://localhost:8000/submit_route_risk_job" `
        -Method Post `
        -ContentType "application/json" `
        -Body $body
} catch {
    Write-Host "ERROR: Failed to submit live-weather route-risk job."
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
# Live weather jobs can take longer than manual-weather jobs because each
# Celery task calls an external weather API.
#
# This loop waits until the job reaches a terminal status before fetching
# final results.

Write-Host ""
Write-Host "Polling job status until complete..."
Write-Host ""

$maxAttempts = 30
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
$results | ConvertTo-Json -Depth 30

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
$summary | ConvertTo-Json -Depth 30

Write-Host ""
Write-Host "============================================================"
Write-Host "LIVE WEATHER ROUTE RISK SUMMARY HIGHLIGHTS"
Write-Host "============================================================"
Write-Host ""

Write-Host "Route status: $($summary.route_status)"
Write-Host "Route name: $($summary.route_name)"
Write-Host "Origin: $($summary.origin)"
Write-Host "Destination: $($summary.destination)"
Write-Host "Segment count: $($summary.segment_count)"
Write-Host "Coordinate-enabled segment count: $($summary.coordinate_segment_count)"
Write-Host "Weather mode: $($summary.weather_mode)"
Write-Host "Route risk score: $($summary.route_risk_score)"
Write-Host "Route risk level: $($summary.route_risk_level)"

if ($summary.highest_risk_segment) {
    Write-Host "Highest-risk segment: $($summary.highest_risk_segment.segment_label)"
    Write-Host "Highest-risk segment latitude: $($summary.highest_risk_segment.latitude)"
    Write-Host "Highest-risk segment longitude: $($summary.highest_risk_segment.longitude)"

    if ($summary.highest_risk_segment.weather) {
        Write-Host "Highest-risk segment weather source: $($summary.highest_risk_segment.weather.source)"
        Write-Host "Highest-risk segment weather condition: $($summary.highest_risk_segment.weather.condition)"
        Write-Host "Highest-risk segment temperature F: $($summary.highest_risk_segment.weather.temperature_f)"
        Write-Host "Highest-risk segment wind MPH: $($summary.highest_risk_segment.weather.wind_mph)"
    }

    Write-Host "Highest-risk segment score: $($summary.highest_risk_segment.risk_score)"
    Write-Host "Highest-risk segment level: $($summary.highest_risk_segment.risk_level)"
}

Write-Host ""
Write-Host "Summary:"
Write-Host $summary.summary

Write-Host ""
Write-Host "============================================================"
Write-Host "END ROUTE RISK API LIVE WEATHER TEST"
Write-Host "============================================================"
Write-Host ""