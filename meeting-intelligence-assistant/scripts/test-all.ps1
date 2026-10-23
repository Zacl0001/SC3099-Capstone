param(
    [switch]$Live,
    [switch]$FullLive
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

$script:results = @()

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

function Invoke-Step {
    param(
        [string]$Name,
        [string]$WorkingDirectory,
        [scriptblock]$Action
    )
    Write-Host "`n=== $Name ===" -ForegroundColor Cyan
    $threw = $false
    $global:LASTEXITCODE = 0
    Push-Location -LiteralPath $WorkingDirectory
    try {
        & $Action
    } catch {
        Write-Host "  ERROR: $($_.Exception.Message)" -ForegroundColor Red
        $threw = $true
    } finally {
        Pop-Location
    }
    $ok = (-not $threw) -and ($LASTEXITCODE -eq 0)
    if ($ok) {
        Write-Host "[PASS] $Name" -ForegroundColor Green
        $script:results += [pscustomobject]@{ Step = $Name; Status = 'PASS' }
    } else {
        Write-Host "[FAIL] $Name" -ForegroundColor Red
        $script:results += [pscustomobject]@{ Step = $Name; Status = 'FAIL' }
    }
}

# ---------------------------------------------------------------------------
# Preflight
# ---------------------------------------------------------------------------

$missing = @()
if (-not (Test-Path $py2)) {
    $missing += "root .venv missing: py -3.13 -m venv .venv; .\.venv\Scripts\python.exe -m pip install -r meeting-intelligence-assistant\module2-backend\requirements-dev.txt"
}
if (-not (Test-Path $py3)) {
    $missing += "module3 .venv missing: py -3.13 -m venv 'meeting-intelligence-assistant\module3-AI processing service\.venv'; .\.venv\Scripts\python.exe -m pip install -r requirements.txt"
}
if (-not (Test-Path $py4)) {
    $missing += "module4 .venv missing: py -3.13 -m venv 'meeting-intelligence-assistant\module4-knowledge assistant service\.venv'; .\.venv\Scripts\python.exe -m pip install -r requirements.txt"
}
if (-not (Test-Path (Join-Path $m1 'node_modules'))) {
    $missing += "module1 node_modules missing: cd 'module1-frontend'; npm install"
}
if ($missing.Count -gt 0) {
    Write-Host "Preflight failed:" -ForegroundColor Red
    $missing | ForEach-Object { Write-Host "  - $_" }
    exit 2
}

if ($Live) {
    $problems = @()
    if (-not (Test-Port 5432)) {
        $problems += 'Postgres not on :5432 - run: docker start meeting-db'
    }
    if (-not (Test-Port 8002)) {
        $problems += "KAS not on :8002 - run 'uvicorn app:app --port 8002' in 'module4-knowledge assistant service'"
    }
    if (-not (Test-Port 11434)) {
        $problems += 'Ollama not on :11434 - start Ollama and pull qwen2.5:7b-instruct + nomic-embed-text'
    }
    if ($problems.Count -gt 0) {
        Write-Host "Live tier cannot run:" -ForegroundColor Red
        $problems | ForEach-Object { Write-Host "  - $_" }
        exit 2
    }
}

# ---------------------------------------------------------------------------
# T0/T1/T2: offline and static checks
# ---------------------------------------------------------------------------

Invoke-Step -Name 'module1: eslint' -WorkingDirectory $m1 -Action {
    npm run lint
}

Invoke-Step -Name 'module1: typecheck' -WorkingDirectory $m1 -Action {
    npm run typecheck
}

Invoke-Step -Name 'module2: pytest' -WorkingDirectory $m2 -Action {
    & $py2 -m pytest tests -q
}

Invoke-Step -Name 'module3: pytest (offline)' -WorkingDirectory $m3 -Action {
    & $py3 -m pytest -q --ignore=tests/test_integration_live.py
}

Invoke-Step -Name 'module4: import app' -WorkingDirectory $m4 -Action {
    & $py4 -c "import app"
}

# ---------------------------------------------------------------------------
# T2/T3: live service + AI checks (requires running services)
# ---------------------------------------------------------------------------

if ($Live) {
    Invoke-Step -Name 'module4: HTTP acceptance' -WorkingDirectory $m4 -Action {
        $kas = 'http://127.0.0.1:8002'
        $sample = Get-Content 'data\sample_meeting1.json' -Raw

        $null = Invoke-RestMethod "$kas/health" -Method Post -TimeoutSec 15

        $first = Invoke-RestMethod "$kas/ingest" -Method Post -ContentType 'application/json' -Body $sample -TimeoutSec 180
        $second = Invoke-RestMethod "$kas/ingest" -Method Post -ContentType 'application/json' -Body $sample -TimeoutSec 180
        if ($first.chunks -ne $second.chunks) {
            throw "ingest is not idempotent ($($first.chunks) vs $($second.chunks) chunks)"
        }

        $searchBody = @{
            meeting_id = 'meeting-001-kas-failure-debug'
            query      = 'database connection error'
            top_k      = 3
        } | ConvertTo-Json
        $search = Invoke-RestMethod "$kas/search" -Method Post -ContentType 'application/json' -Body $searchBody -TimeoutSec 60
        if (-not $search.results) {
            throw 'search returned no results'
        }
        $wrong = @($search.results | Where-Object { $_.meeting_id -ne 'meeting-001-kas-failure-debug' })
        if ($wrong.Count -gt 0) {
            throw 'search leaked results from another meeting'
        }

        $chunkBody = @{
            transcript = 'Alice: We discussed the budget. Bob: We approved it for Q3.'
        } | ConvertTo-Json
        $chunk = Invoke-RestMethod "$kas/chunk" -Method Post -ContentType 'application/json' -Body $chunkBody -TimeoutSec 60
        if (-not $chunk.chunks) {
            throw 'chunk returned no chunks'
        }

        $badRequest = $false
        try {
            $null = Invoke-RestMethod "$kas/chunk" -Method Post -ContentType 'application/json' -Body '{}' -TimeoutSec 15
        } catch {
            if ($_.Exception.Response.StatusCode.value__ -eq 400) {
                $badRequest = $true
            }
        }
        if (-not $badRequest) {
            throw 'empty request body did not return 400'
        }
    }

    Invoke-Step -Name 'module3: smoke (live)' -WorkingDirectory $m3 -Action {
        & $py3 run_tests.py --tier smoke
    }

    $liveArgs = @('run_tests.py', '--tier', 'live')
    if ($FullLive) {
        $liveArgs += '--full-live'
    }

    Invoke-Step -Name 'module3: live integration' -WorkingDirectory $m3 -Action {
        & $py3 @liveArgs
    }
}

# ---------------------------------------------------------------------------
# Summary
# ---------------------------------------------------------------------------

Write-Host "`n=== SUMMARY ===" -ForegroundColor Cyan
$script:results | Format-Table -AutoSize | Out-String | Write-Host

$failed = @($script:results | Where-Object { $_.Status -eq 'FAIL' })
if ($failed.Count -gt 0) {
    Write-Host "OVERALL: FAIL ($($failed.Count) step(s))" -ForegroundColor Red
    exit 1
}

Write-Host 'OVERALL: PASS' -ForegroundColor Green
exit 0
