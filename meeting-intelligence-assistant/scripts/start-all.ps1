param(
    [switch]$SkipFrontend,
    # Use another port when 3000 is taken (e.g. by another Docker container).
    [int]$FrontendPort = 3000
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

# winget/installers update the machine PATH, but already-running terminals keep
# the old value. Resolve npm explicitly so the launcher works before a reboot.
function Resolve-Npm {
    $cmd = Get-Command npm.cmd -ErrorAction SilentlyContinue
    if ($cmd) { return $cmd.Source }
    $candidates = @(
        (Join-Path $env:ProgramFiles 'nodejs\npm.cmd'),
        (Join-Path $env:LOCALAPPDATA 'Programs\nodejs\npm.cmd')
    )
    foreach ($candidate in $candidates) {
        if (Test-Path -LiteralPath $candidate) { return $candidate }
    }
    return $null
}

function Start-ServiceWindow {
    param(
        [string]$Title,
        [string]$WorkingDirectory,
        [string]$Command,
        [string]$PathPrefix = ''
    )
    $inner = "`$Host.UI.RawUI.WindowTitle = '$Title'; Set-Location -LiteralPath '$WorkingDirectory'; "
    if ($PathPrefix) { $inner += "`$env:PATH = '$PathPrefix;' + `$env:PATH; " }
    $inner += $Command
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
$npm = $null
if (-not $SkipFrontend) {
    $npm = Resolve-Npm
    if (-not $npm) {
        throw 'npm not found. Install Node.js LTS (winget install OpenJS.NodeJS.LTS) and reopen the terminal.'
    }
}

foreach ($port in 5432, 8000, 8001, 8002, $FrontendPort) {
    if ((Test-Port $port) -and $port -ne 5432) {
        Write-Host "Warning: port $port is already in use; the service may already be running." -ForegroundColor Yellow
    }
}

# A Docker container publishing the frontend port would be mistaken for the
# frontend, which is then never started.
if (-not $SkipFrontend) {
    $holder = docker ps --filter "publish=$FrontendPort" --format '{{.Names}}' 2>$null | Select-Object -First 1
    if ($holder) {
        throw "Port $FrontendPort is used by Docker container '$holder'. Stop it (docker stop $holder) or pick another port: .\scripts\start-all.ps1 -FrontendPort 3001"
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

if (-not $SkipFrontend -and -not (Test-Port $FrontendPort)) {
    Start-ServiceWindow -Title "frontend :$FrontendPort" -WorkingDirectory $m1 -Command "`$env:PORT = '$FrontendPort'; & '$npm' run dev" -PathPrefix (Split-Path -Parent $npm)
    Wait-Port -Port $FrontendPort -TimeoutSeconds 120 -Label 'frontend'
}

# ---------------------------------------------------------------------------
# Report
# ---------------------------------------------------------------------------

Write-Host "`nAll services requested are up:" -ForegroundColor Cyan
Write-Host '  Knowledge service  http://localhost:8002/docs'
Write-Host '  AI service         http://localhost:8001/docs'
Write-Host '  Backend            http://localhost:8000/docs'
if (-not $SkipFrontend) {
    Write-Host "  Frontend           http://localhost:$FrontendPort"
}
Write-Host "`nStop everything with: .\scripts\stop-all.ps1"
