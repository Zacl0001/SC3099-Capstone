param(
    [switch]$SkipFrontend
)

$ErrorActionPreference = 'Stop'

$mi   = Split-Path -Parent $PSScriptRoot
$root = Split-Path -Parent $mi
$m1   = Join-Path $mi 'module1-frontend'
$m2   = Join-Path $mi 'module2-backend'
$m3   = Join-Path $mi 'module3-AI processing service'
$m4   = Join-Path $mi 'module4-knowledge assistant service'

$py2 = Join-Path $root '.venv\Scripts\python.exe'
$py3 = Join-Path $m3 '.venv\Scripts\python.exe'
$py4 = Join-Path $m4 '.venv\Scripts\python.exe'

function Test-Port {
    param([int]$Port, [string]$ComputerName = '127.0.0.1')
    $client = New-Object System.Net.Sockets.TcpClient
    try {
        $client.Connect($ComputerName, $Port)
        return $true
    } catch {
        return $false
    } finally {
        $client.Dispose()
    }
}

function Wait-Port {
    param([int]$Port, [int]$TimeoutSeconds = 90, [string]$Label = 'service')
    $deadline = (Get-Date).AddSeconds($TimeoutSeconds)
    while (-not (Test-Port $Port)) {
        if ((Get-Date) -gt $deadline) {
            throw "$Label did not open :$Port within $TimeoutSeconds seconds"
        }
        Start-Sleep -Seconds 1
    }
}

function Start-ServiceWindow {
    param(
        [string]$Title,
        [string]$WorkingDirectory,
        [string]$Command
    )
    $inner = "`$Host.UI.RawUI.WindowTitle = '$Title'; Set-Location -LiteralPath '$WorkingDirectory'; $Command"
    Start-Process -FilePath 'powershell.exe' -ArgumentList '-NoExit', '-Command', $inner -WindowStyle Normal | Out-Null
    Write-Host "Started $Title" -ForegroundColor Green
}

# ---------------------------------------------------------------------------
# Preflight
# ---------------------------------------------------------------------------

docker info 2>$null | Out-Null
if ($LASTEXITCODE -ne 0) {
    throw 'Docker engine is not running. Start Docker Desktop and retry.'
}
if (-not (Test-Path $py2)) { throw "Missing root .venv ($py2). See docs/testing-guide.md." }
if (-not (Test-Path $py3)) { throw "Missing module3 .venv ($py3). See docs/testing-guide.md." }
if (-not (Test-Path $py4)) { throw "Missing module4 .venv ($py4). See docs/testing-guide.md." }
if (-not $SkipFrontend -and -not (Test-Path (Join-Path $m1 'node_modules'))) {
    throw "Missing module1 node_modules. Run 'npm install' in module1-frontend."
}

foreach ($port in 5432, 8000, 8001, 8002, 3000) {
    if ((Test-Port $port) -and $port -ne 5432) {
        Write-Host "Warning: port $port is already in use; the service may already be running." -ForegroundColor Yellow
    }
}

# ---------------------------------------------------------------------------
# Start the stack in dependency order
# ---------------------------------------------------------------------------

Write-Host "`nStarting Postgres (meeting-db)..." -ForegroundColor Cyan
docker start meeting-db | Out-Null
Wait-Port -Port 5432 -TimeoutSeconds 60 -Label 'Postgres'

if (-not (Test-Port 8002)) {
    Start-ServiceWindow -Title 'KAS :8002' -WorkingDirectory $m4 -Command "& '$py4' -m uvicorn app:app --port 8002"
    Wait-Port -Port 8002 -Label 'KAS'
}

if (-not (Test-Port 8001)) {
    Start-ServiceWindow -Title 'module3 AI :8001' -WorkingDirectory $m3 -Command "& '$py3' -m uvicorn app.main:app --port 8001"
    Wait-Port -Port 8001 -Label 'module3 AI'
}

if (-not (Test-Port 8000)) {
    Start-ServiceWindow -Title 'module2 backend :8000' -WorkingDirectory $m2 -Command "& '$py2' -m uvicorn app.main:app --reload --port 8000"
    Wait-Port -Port 8000 -Label 'module2 backend'
}

if (-not $SkipFrontend -and -not (Test-Port 3000)) {
    Start-ServiceWindow -Title 'frontend :3000' -WorkingDirectory $m1 -Command 'npm run dev'
    Wait-Port -Port 3000 -TimeoutSeconds 120 -Label 'frontend'
}

# ---------------------------------------------------------------------------
# Report
# ---------------------------------------------------------------------------

Write-Host "`nAll services requested are up:" -ForegroundColor Cyan
Write-Host '  Knowledge service  http://localhost:8002/docs'
Write-Host '  AI service         http://localhost:8001/docs'
Write-Host '  Backend            http://localhost:8000/docs'
if (-not $SkipFrontend) {
    Write-Host '  Frontend           http://localhost:3000'
}
Write-Host "`nStop everything with: .\scripts\stop-all.ps1"
