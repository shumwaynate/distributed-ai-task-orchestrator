Set-Location (Join-Path $PSScriptRoot "..")

Write-Host ""
Write-Host "============================================================"
Write-Host "ROUTE RISK FAN-OUT API TEST"
Write-Host "============================================================"
Write-Host ""

# ============================================================
# ROUTE RISK ENGINE FAN-OUT API TEST
# ============================================================
#
# Purpose:
# - Submit a larger route-risk job to FastAPI.
# - Use 8 route segments instead of 2.
# - Prove that one route request can fan out into many Celery tasks.
# - Save the returned job_id automatically.
# - Check job status without manual copying.
# - Fetch raw segment results and aggregated route-level results.
# - Fetch the clean user-facing route-risk summary endpoint.
#
# Requirements:
# - FastAPI must be running.
# - Redis must be running.
# - Celery worker must be running.
#
# Start the app first with:
#
#     .\scripts\start_dev.ps1
#
# Then run this script from the project root:
#
#     .\scripts\test_route_risk_fanout_api.ps1

$body = @{
    route_name = "Rexburg to Idaho Falls Extended Fan-Out Test Route"
    origin = "Rexburg, ID"
    destination = "Idaho Falls, ID"
    segments = @(
        @{
            label = "Rexburg to Thornton"
            weather = @{
                temperature_f = 26
                wind_mph = 12
                condition = "snow"
                visibility_miles = 3
            }
            road_condition = "normal"
            is_night = $true
        },
        @{
            label = "Thornton to Sugar City Junction"
            weather = @{
                temperature_f = 24
                wind_mph = 18
                condition = "snow"
                visibility_miles = 2
            }
            road_condition = "icy"
            is_night = $true
        },
        @{
            label = "Sugar City Junction to Rigby North"
            weather = @{
                temperature_f = 30
                wind_mph = 10
                condition = "cloudy"
                visibility_miles = 5
            }
            road_condition = "normal"
            is_night = $true
        },
        @{
            label = "Rigby North to Rigby South"
            weather = @{
                temperature_f = 34
                wind_mph = 28
                condition = "cloudy"
                visibility_miles = 6
            }
            road_condition = "construction"
            is_night = $true
        },
        @{
            label = "Rigby South to Lorenzo"
            weather = @{
                temperature_f = 32
                wind_mph = 26
                condition = "light snow"
                visibility_miles = 2
            }
            road_condition = "normal"
            is_night = $true
        },
        @{
            label = "Lorenzo to Roberts"
            weather = @{
                temperature_f = 29
                wind_mph = 32
                condition = "fog"
                visibility_miles = 1
            }
            road_condition = "normal"
            is_night = $true
        },
        @{
            label = "Roberts to Idaho Falls North"
            weather = @{
                temperature_f = 36
                wind_mph = 14
                condition = "rain"
                visibility_miles = 4
            }
            road_condition = "construction"
            is_night = $true
        },
        @{
            label = "Idaho Falls North to Downtown Idaho Falls"
            weather = @{
                temperature_f = 38
                wind_mph = 8
                condition = "clear"
                visibility_miles = 8
            }
            road_condition = "normal"
            is_night = $false
        }
    )
} | ConvertTo-Json -Depth 10

Write-Host "Submitting extended route-risk fan-out job..."
Write-Host ""

try {
    $response = Invoke-RestMethod `
        -Uri "http://localhost:8000/submit_route_risk_job" `
        -Method Post `
        -ContentType "application/json" `
        -Body $body
} catch {
    Write-Host "ERROR: Failed to submit route-risk fan-out job."
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

Write-Host ""
Write-Host "Checking job status..."
Write-Host ""

Start-Sleep -Seconds 1

try {
    $status = Invoke-RestMethod `
        -Uri "http://localhost:8000/job_status/$jobId" `
        -Method Get
} catch {
    Write-Host "ERROR: Failed to retrieve job status."
    Write-Host $_
    exit 1
}

Write-Host "Job status:"
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
Write-Host "FAN-OUT TEST SUMMARY"
Write-Host "============================================================"
Write-Host ""

Write-Host "Expected task count: 8"
Write-Host "Actual task count: $($response.task_count)"
Write-Host "Job status: $($status.status)"
Write-Host "Progress percent: $($status.progress_percent)"

Write-Host ""
Write-Host "Clean summary endpoint:"
Write-Host "Route status: $($summary.route_status)"
Write-Host "Route name: $($summary.route_name)"
Write-Host "Origin: $($summary.origin)"
Write-Host "Destination: $($summary.destination)"
Write-Host "Segment count: $($summary.segment_count)"
Write-Host "Route risk score: $($summary.route_risk_score)"
Write-Host "Route risk level: $($summary.route_risk_level)"

if ($summary.highest_risk_segment) {
    Write-Host "Highest-risk segment: $($summary.highest_risk_segment.segment_label)"
    Write-Host "Highest-risk segment score: $($summary.highest_risk_segment.risk_score)"
    Write-Host "Highest-risk segment level: $($summary.highest_risk_segment.risk_level)"
}

Write-Host ""
Write-Host "Route summary:"
Write-Host $summary.summary

Write-Host ""
Write-Host "============================================================"
Write-Host "END ROUTE RISK FAN-OUT API TEST"
Write-Host "============================================================"
Write-Host ""