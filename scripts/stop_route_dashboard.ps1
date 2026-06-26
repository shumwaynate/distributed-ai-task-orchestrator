$ErrorActionPreference = "SilentlyContinue"

Write-Host "Stopping dashboard server on port 8080..."

$connections = Get-NetTCPConnection -LocalPort 8080 -State Listen
foreach ($connection in $connections) {
    Stop-Process -Id $connection.OwningProcess -Force
}

Write-Host "Stopping Route Risk Docker services..."
docker compose down

Write-Host "Dashboard and Docker services stopped." -ForegroundColor Green
