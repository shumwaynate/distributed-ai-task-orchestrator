[CmdletBinding()]
param(
    [Parameter(
        Mandatory = $true,
        HelpMessage = "Latitude and longitude as 'lat,lon'."
    )]
    [string]$Origin,

    [Parameter(
        Mandatory = $true,
        HelpMessage = "Latitude and longitude as 'lat,lon'."
    )]
    [string]$Destination,

    [string]$OriginLabel = "Origin",
    [string]$DestinationLabel = "Destination",

    # Number of separate Celery worker containers.
    [ValidateRange(1, 32)]
    [int]$Workers = 8,

    # Processes inside each Celery worker container.
    # Keep this at 1 so eight containers represent eight workers,
    # matching the benchmark methodology.
    [ValidateRange(1, 32)]
    [int]$WorkerConcurrency = 1,

    [ValidateRange(2, 100)]
    [int]$CheckpointCount = 8,

    [ValidateRange(1, 3)]
    [int]$RouteCount = 3,

    [string[]]$StateCodes = @("NV"),

    [ValidateRange(0.1, 50.0)]
    [double]$RoadEventRadiusMiles = 5.0,

    [ValidateRange(0.0, 1.0)]
    [double]$ShareFactor = 0.8,

    [ValidateRange(0.1, 10.0)]
    [double]$WeightFactor = 2.5,

    # Leave empty to automatically find the normal external key directory.
    [string]$KeyDirectory = "",

    [switch]$Night,
    [switch]$NoLiveStateEvents,
    [switch]$SkipBuild,
    [switch]$StopAfter,
    [switch]$SaveJson,

    [string]$ApiBaseUrl = "http://127.0.0.1:8000"
)

$ErrorActionPreference = "Stop"


function ConvertFrom-CoordinateText {
    param(
        [Parameter(Mandatory = $true)]
        [string]$Value,

        [Parameter(Mandatory = $true)]
        [string]$ParameterName
    )

    $parts = $Value.Split(
        ",",
        [System.StringSplitOptions]::RemoveEmptyEntries
    )

    if ($parts.Count -ne 2) {
        throw (
            "$ParameterName must use the format " +
            "'latitude,longitude'. Example: 36.1716,-115.1391"
        )
    }

    [double]$latitude = 0
    [double]$longitude = 0

    $style = [System.Globalization.NumberStyles]::Float
    $culture = [System.Globalization.CultureInfo]::InvariantCulture

    $latitudeValid = [double]::TryParse(
        $parts[0].Trim(),
        $style,
        $culture,
        [ref]$latitude
    )

    $longitudeValid = [double]::TryParse(
        $parts[1].Trim(),
        $style,
        $culture,
        [ref]$longitude
    )

    if (-not $latitudeValid -or -not $longitudeValid) {
        throw "$ParameterName contains an invalid latitude or longitude."
    }

    if ($latitude -lt -90 -or $latitude -gt 90) {
        throw "$ParameterName latitude must be between -90 and 90."
    }

    if ($longitude -lt -180 -or $longitude -gt 180) {
        throw "$ParameterName longitude must be between -180 and 180."
    }

    return [PSCustomObject]@{
        Latitude  = $latitude
        Longitude = $longitude
    }
}


function Resolve-RouteRiskKeyDirectory {
    param(
        [string]$RequestedDirectory
    )

    $candidateDirectories = @()

    if (-not [string]::IsNullOrWhiteSpace($RequestedDirectory)) {
        $candidateDirectories += $RequestedDirectory
    }

    if (
        -not [string]::IsNullOrWhiteSpace(
            [string]$env:ROUTE_RISK_KEYS_HOST_DIR
        )
    ) {
        $candidateDirectories += $env:ROUTE_RISK_KEYS_HOST_DIR
    }

    $candidateDirectories += @(
        (Join-Path $HOME "OneDrive\Desktop\ORS Key"),
        (Join-Path $HOME "Desktop\ORS Key"),
        (Join-Path $HOME ".route-risk-keys")
    )

    foreach ($candidate in $candidateDirectories) {
        if (
            -not [string]::IsNullOrWhiteSpace([string]$candidate) -and
            (Test-Path -LiteralPath $candidate -PathType Container)
        ) {
            return (Resolve-Path -LiteralPath $candidate).Path
        }
    }

    $searchedLocations = $candidateDirectories -join "`n - "

    throw (
        "The external API-key directory could not be found. " +
        "Searched:`n - $searchedLocations"
    )
}


function Assert-KeyFileExists {
    param(
        [Parameter(Mandatory = $true)]
        [string]$Directory,

        [Parameter(Mandatory = $true)]
        [string]$FileName,

        [Parameter(Mandatory = $true)]
        [string]$ServiceName
    )

    $filePath = Join-Path $Directory $FileName

    if (-not (Test-Path -LiteralPath $filePath -PathType Leaf)) {
        throw (
            "$ServiceName requires the external key file '$FileName', " +
            "but it was not found in: $Directory"
        )
    }

    $fileInfo = Get-Item -LiteralPath $filePath

    if ($fileInfo.Length -le 0) {
        throw (
            "$ServiceName key file '$FileName' exists but is empty."
        )
    }
}


function Confirm-RequiredKeyFiles {
    param(
        [Parameter(Mandatory = $true)]
        [string]$Directory,

        [Parameter(Mandatory = $true)]
        [string[]]$RequestedStateCodes,

        [Parameter(Mandatory = $true)]
        [bool]$UseLiveStateEvents
    )

    Assert-KeyFileExists `
        -Directory $Directory `
        -FileName "ORSKey.txt" `
        -ServiceName "OpenRouteService"

    if (-not $UseLiveStateEvents) {
        return
    }

    foreach ($stateCode in $RequestedStateCodes) {
        switch ($stateCode.Trim().ToUpperInvariant()) {
            "ID" {
                Assert-KeyFileExists `
                    -Directory $Directory `
                    -FileName "Idaho511Key.txt" `
                    -ServiceName "Idaho 511"
            }

            "NV" {
                Assert-KeyFileExists `
                    -Directory $Directory `
                    -FileName "Nevada511Key.txt" `
                    -ServiceName "Nevada 511"
            }

            "UT" {
                Assert-KeyFileExists `
                    -Directory $Directory `
                    -FileName "UtahUDOTKey.txt" `
                    -ServiceName "Utah UDOT"
            }

            "AZ" {
                Assert-KeyFileExists `
                    -Directory $Directory `
                    -FileName "Arizona511Key.txt" `
                    -ServiceName "Arizona 511"
            }

            default {
                Write-Warning (
                    "No local API-key filename validation is configured " +
                    "for state code '$stateCode'."
                )
            }
        }
    }
}


function Wait-ForApi {
    param(
        [Parameter(Mandatory = $true)]
        [string]$BaseUrl,

        [int]$Attempts = 60,
        [int]$DelaySeconds = 2
    )

    Write-Host "Waiting for the API at $BaseUrl ..."

    for ($attempt = 1; $attempt -le $Attempts; $attempt++) {
        try {
            Invoke-RestMethod `
                -Method Get `
                -Uri "$BaseUrl/" `
                -TimeoutSec 5 |
                Out-Null

            Write-Host "API is ready." -ForegroundColor Green
            return
        }
        catch {
            Write-Host (
                "`rAPI startup check $attempt/$Attempts"
            ) -NoNewline

            Start-Sleep -Seconds $DelaySeconds
        }
    }

    Write-Host ""

    throw (
        "The API did not become ready after " +
        "$($Attempts * $DelaySeconds) seconds."
    )
}


function Get-RouteExplanation {
    param(
        [object]$Result
    )

    $candidates = @(
        $Result.recommendation_explanation,
        $Result.recommendation_reason,
        $Result.summary,
        $Result.recommended_route.route_explanation,
        $Result.recommended_route.explanation,
        $Result.recommended_route.route_warning
    )

    foreach ($candidate in $candidates) {
        if (
            -not [string]::IsNullOrWhiteSpace(
                [string]$candidate
            )
        ) {
            return [string]$candidate
        }
    }

    return (
        "Selected from the completed alternatives using " +
        "the route-risk comparison results."
    )
}


$originCoordinate = ConvertFrom-CoordinateText `
    -Value $Origin `
    -ParameterName "Origin"

$destinationCoordinate = ConvertFrom-CoordinateText `
    -Value $Destination `
    -ParameterName "Destination"

$containersStarted = $false


try {
    if (-not (Get-Command docker -ErrorAction SilentlyContinue)) {
        throw (
            "Docker was not found. Start Docker Desktop and make sure " +
            "the docker command is available."
        )
    }

    & docker compose version | Out-Null

    if ($LASTEXITCODE -ne 0) {
        throw (
            "Docker Compose is not available through 'docker compose'."
        )
    }

    $resolvedKeyDirectory = Resolve-RouteRiskKeyDirectory `
        -RequestedDirectory $KeyDirectory

    $useLiveEvents = -not $NoLiveStateEvents.IsPresent

    Confirm-RequiredKeyFiles `
        -Directory $resolvedKeyDirectory `
        -RequestedStateCodes $StateCodes `
        -UseLiveStateEvents $useLiveEvents

    # Docker Compose reads this variable and mounts the host directory
    # into /run/secrets/route-risk-keys inside the containers.
    #
    # Forward slashes are more reliable for Docker Desktop bind mounts.
    $env:ROUTE_RISK_KEYS_HOST_DIR = (
        $resolvedKeyDirectory -replace "\\", "/"
    )

    # Each worker container uses this many Celery processes.
    # The default is one so eight containers equal eight workers.
    $env:WORKER_CONCURRENCY = [string]$WorkerConcurrency

    Write-Host ""
    Write-Host "========================================" -ForegroundColor Cyan
    Write-Host "Distributed Route Risk Engine Demo" -ForegroundColor Cyan
    Write-Host "========================================" -ForegroundColor Cyan

    Write-Host (
        "Origin:       $OriginLabel " +
        "($($originCoordinate.Latitude), " +
        "$($originCoordinate.Longitude))"
    )

    Write-Host (
        "Destination:  $DestinationLabel " +
        "($($destinationCoordinate.Latitude), " +
        "$($destinationCoordinate.Longitude))"
    )

    Write-Host "Worker containers:       $Workers"
    Write-Host "Processes per container: $WorkerConcurrency"
    Write-Host "Total worker processes:  $($Workers * $WorkerConcurrency)"
    Write-Host "Routes:                  $RouteCount"
    Write-Host "Checkpoints:             $CheckpointCount per route"
    Write-Host "State feeds:             $($StateCodes -join ', ')"
    Write-Host "Live events:             $useLiveEvents"
    Write-Host "Night mode:              $($Night.IsPresent)"

    Write-Host (
        "External keys:           Mounted read-only from " +
        "$resolvedKeyDirectory"
    )

    Write-Host "========================================"
    Write-Host ""

    $composeArguments = @(
        "compose",
        "up"
    )

    if (-not $SkipBuild) {
        $composeArguments += "--build"
    }

    $composeArguments += @(
        "-d",
        "--scale",
        "worker=$Workers",
        "redis",
        "api",
        "worker"
    )

    Write-Host (
        "Starting Redis, API, and " +
        "$Workers worker container(s)..."
    )

    & docker @composeArguments

    if ($LASTEXITCODE -ne 0) {
        throw "Docker Compose failed to start the project services."
    }

    $containersStarted = $true

    Wait-ForApi -BaseUrl $ApiBaseUrl

    $requestBody = @{
        route_name               = "$OriginLabel to $DestinationLabel"
        origin_label             = $OriginLabel
        origin_latitude          = $originCoordinate.Latitude
        origin_longitude         = $originCoordinate.Longitude
        destination_label        = $DestinationLabel
        destination_latitude     = $destinationCoordinate.Latitude
        destination_longitude    = $destinationCoordinate.Longitude
        checkpoint_count         = $CheckpointCount
        target_route_count       = $RouteCount
        share_factor             = $ShareFactor
        weight_factor            = $WeightFactor
        use_live_state_events    = $useLiveEvents
        state_codes              = $StateCodes
        road_condition          = "normal"
        road_event_radius_miles = $RoadEventRadiusMiles
        road_events             = @()
        is_night                = $Night.IsPresent
    }

    Write-Host "Submitting route comparison job..."

    $job = Invoke-RestMethod `
        -Method Post `
        -Uri "$ApiBaseUrl/submit_route_comparison_job" `
        -ContentType "application/json" `
        -Body ($requestBody | ConvertTo-Json -Depth 8) `
        -TimeoutSec 90

    if ([string]::IsNullOrWhiteSpace([string]$job.job_id)) {
        throw "The API response did not contain a job ID."
    }

    Write-Host "Job ID: $($job.job_id)"

    if ($null -ne $job.route_candidate_count) {
        Write-Host (
            "Route candidates created: " +
            "$($job.route_candidate_count)"
        )
    }

    if ($null -ne $job.live_state_event_count) {
        Write-Host (
            "Live state events loaded: " +
            "$($job.live_state_event_count)"
        )
    }

    $terminalStatuses = @(
        "SUCCESS",
        "PARTIAL_FAILURE",
        "FAILURE",
        "FAILED",
        "REVOKED"
    )

    do {
        Start-Sleep -Seconds 1

        $status = Invoke-RestMethod `
            -Method Get `
            -Uri "$ApiBaseUrl/job_status/$($job.job_id)" `
            -TimeoutSec 30

        $completed = if ($null -ne $status.completed_tasks) {
            $status.completed_tasks
        }
        else {
            0
        }

        $total = if ($null -ne $status.total_tasks) {
            $status.total_tasks
        }
        else {
            "?"
        }

        $failed = if ($null -ne $status.failed_tasks) {
            $status.failed_tasks
        }
        else {
            0
        }

        $progress = if ($null -ne $status.progress_percent) {
            "$($status.progress_percent)%"
        }
        else {
            ""
        }

        Write-Host (
            "`rStatus: $($status.status) | " +
            "Completed: $completed/$total | " +
            "Failed: $failed | " +
            "Progress: $progress    "
        ) -NoNewline

    } while ($status.status -notin $terminalStatuses)

    Write-Host ""

    if (
        $status.status -in @(
            "FAILURE",
            "FAILED",
            "REVOKED"
        )
    ) {
        throw (
            "The route comparison job ended with status " +
            "$($status.status)."
        )
    }

    $result = Invoke-RestMethod `
        -Method Get `
        -Uri "$ApiBaseUrl/route_comparison_summary/$($job.job_id)" `
        -TimeoutSec 60

    Write-Host ""
    Write-Host "Route comparison results" -ForegroundColor Cyan
    Write-Host "------------------------"

    $routeRows = foreach ($route in @($result.routes)) {
        $segments = @(
            $route.aggregated_route_risk.segment_results
        )

        $constructionCount = @(
            $segments |
                Where-Object {
                    $_.road_condition -eq "construction"
                }
        ).Count

        $closureCount = @(
            $segments |
                Where-Object {
                    $_.road_condition -eq "closed"
                }
        ).Count

        [PSCustomObject]@{
            Route = $route.route_label

            Miles = if ($null -ne $route.distance_meters) {
                [math]::Round(
                    $route.distance_meters / 1609.344,
                    1
                )
            }
            else {
                $null
            }

            Minutes = if ($null -ne $route.duration_seconds) {
                [math]::Round(
                    $route.duration_seconds / 60,
                    1
                )
            }
            else {
                $null
            }

            Score        = $route.route_risk_score
            Risk         = $route.route_risk_level
            Construction = $constructionCount
            Closures     = $closureCount
        }
    }

    $routeRows |
        Format-Table -AutoSize

    $recommended = $result.recommended_route

    if ($null -ne $recommended) {
        Write-Host (
            "RECOMMENDED PATH: $($recommended.route_label)"
        ) -ForegroundColor Green

        Write-Host (
            "RECOMMENDATION SCORE: " +
            "$($recommended.route_risk_score)"
        )

        Write-Host (
            "RISK LEVEL: $($recommended.route_risk_level)"
        )

        Write-Host (
            "REASON: $(Get-RouteExplanation -Result $result)"
        )

        if (
            -not [string]::IsNullOrWhiteSpace(
                [string]$recommended.google_maps_url
            )
        ) {
            Write-Host (
                "GOOGLE MAPS: " +
                "$($recommended.google_maps_url)"
            )
        }

        if (
            -not [string]::IsNullOrWhiteSpace(
                [string]$recommended.apple_maps_url
            )
        ) {
            Write-Host (
                "APPLE MAPS: " +
                "$($recommended.apple_maps_url)"
            )
        }
    }
    else {
        Write-Warning (
            "The response did not contain a recommended_route object."
        )
    }

    if ($SaveJson) {
        $projectRoot = Split-Path -Parent $PSScriptRoot

        $outputDirectory = Join-Path `
            $projectRoot `
            "benchmarks\demo_results"

        New-Item `
            -ItemType Directory `
            -Force `
            $outputDirectory |
            Out-Null

        $timestamp = Get-Date -Format "yyyyMMdd_HHmmss"

        $outputPath = Join-Path `
            $outputDirectory `
            "route_comparison_$timestamp.json"

        $result |
            ConvertTo-Json -Depth 30 |
            Set-Content `
                -Path $outputPath `
                -Encoding UTF8

        Write-Host "Saved full result to: $outputPath"
    }

    Write-Host ""
    Write-Host "Demo completed successfully." -ForegroundColor Green
}
catch {
    Write-Host ""

    Write-Host (
        "ERROR: $($_.Exception.Message)"
    ) -ForegroundColor Red

    if (
        -not [string]::IsNullOrWhiteSpace(
            [string]$_.ErrorDetails.Message
        )
    ) {
        Write-Host (
            "API DETAILS: $($_.ErrorDetails.Message)"
        ) -ForegroundColor Yellow
    }

    Write-Host ""
    Write-Host "Recent API logs:" -ForegroundColor Yellow

    & docker compose logs api --tail 50

    exit 1
}
finally {
    if ($StopAfter -and $containersStarted) {
        Write-Host "Stopping project containers..."
        & docker compose down
    }
}