[CmdletBinding()]
param(
    [ValidateRange(1, 32)]
    [int]$Workers = 8,

    [ValidateRange(1, 32)]
    [int]$WorkerConcurrency = 1,

    [string]$KeyDirectory = "",

    [switch]$SkipBuild,

    [string]$DashboardUrl = "http://127.0.0.1:8080",
    [string]$BackendUrl = "http://127.0.0.1:8000"
)

$ErrorActionPreference = "Stop"

function Resolve-KeyDirectory {
    param([string]$RequestedDirectory)

    $candidates = @()

    if (-not [string]::IsNullOrWhiteSpace($RequestedDirectory)) {
        $candidates += $RequestedDirectory
    }

    if (-not [string]::IsNullOrWhiteSpace([string]$env:ROUTE_RISK_KEYS_HOST_DIR)) {
        $candidates += $env:ROUTE_RISK_KEYS_HOST_DIR
    }

    $candidates += @(
        (Join-Path $HOME "OneDrive\Desktop\ORS Key"),
        (Join-Path $HOME "Desktop\ORS Key"),
        (Join-Path $HOME ".route-risk-keys")
    )

    foreach ($candidate in $candidates) {
        if (
            -not [string]::IsNullOrWhiteSpace([string]$candidate) -and
            (Test-Path -LiteralPath $candidate -PathType Container)
        ) {
            return (Resolve-Path -LiteralPath $candidate).Path
        }
    }

    throw "Could not find the external API-key directory."
}

function Wait-ForUrl {
    param(
        [Parameter(Mandatory = $true)]
        [string]$Url,

        [int]$Attempts = 60,
        [int]$DelaySeconds = 1
    )

    for ($attempt = 1; $attempt -le $Attempts; $attempt++) {
        try {
            Invoke-RestMethod -Method Get -Uri $Url -TimeoutSec 5 | Out-Null
            return
        }
        catch {
            Write-Host "`rWaiting for $Url ($attempt/$Attempts)" -NoNewline
            Start-Sleep -Seconds $DelaySeconds
        }
    }

    Write-Host ""
    throw "The service did not become ready: $Url"
}

$projectRoot = Split-Path -Parent $PSScriptRoot
Set-Location $projectRoot

if (-not (Get-Command docker -ErrorAction SilentlyContinue)) {
    throw "Docker was not found. Start Docker Desktop first."
}

$keyPath = Resolve-KeyDirectory -RequestedDirectory $KeyDirectory
$env:ROUTE_RISK_KEYS_HOST_DIR = $keyPath -replace "\\", "/"
$env:WORKER_CONCURRENCY = [string]$WorkerConcurrency
$env:ROUTE_RISK_BACKEND_URL = $BackendUrl

$composeArguments = @("compose", "up")
if (-not $SkipBuild) {
    $composeArguments += "--build"
}
$composeArguments += @(
    "-d",
    "--scale", "worker=$Workers",
    "redis", "api", "worker"
)

Write-Host "Starting Redis, API, and $Workers worker container(s)..." -ForegroundColor Cyan
& docker @composeArguments
if ($LASTEXITCODE -ne 0) {
    throw "Docker Compose failed to start the Route Risk services."
}

Write-Host "Waiting for the backend API..."
Wait-ForUrl -Url "$BackendUrl/"
Write-Host "Backend API is ready." -ForegroundColor Green

$pythonPath = Join-Path $projectRoot ".venv\Scripts\python.exe"
if (-not (Test-Path -LiteralPath $pythonPath -PathType Leaf)) {
    $pythonCommand = Get-Command python -ErrorAction SilentlyContinue
    if (-not $pythonCommand) {
        throw "Python was not found. Activate the project virtual environment first."
    }
    $pythonPath = $pythonCommand.Source
}

$existingDashboard = $false
try {
    $health = Invoke-RestMethod -Method Get -Uri "$DashboardUrl/health" -TimeoutSec 3
    if ($health.dashboard_status -eq "ready") {
        $existingDashboard = $true
    }
}
catch {
    $existingDashboard = $false
}

if (-not $existingDashboard) {
    $logDirectory = Join-Path $projectRoot "logs"
    New-Item -ItemType Directory -Force $logDirectory | Out-Null

    $stdoutPath = Join-Path $logDirectory "dashboard_stdout.log"
    $stderrPath = Join-Path $logDirectory "dashboard_stderr.log"

    Write-Host "Starting the browser dashboard server..."

    Start-Process `
        -FilePath $pythonPath `
        -ArgumentList @(
            "-m", "uvicorn",
            "app.dashboard.server:app",
            "--host", "127.0.0.1",
            "--port", "8080"
        ) `
        -WorkingDirectory $projectRoot `
        -WindowStyle Hidden `
        -RedirectStandardOutput $stdoutPath `
        -RedirectStandardError $stderrPath | Out-Null

    Wait-ForUrl -Url "$DashboardUrl/health"
}

Write-Host "Dashboard is ready: $DashboardUrl" -ForegroundColor Green
Start-Process $DashboardUrl
