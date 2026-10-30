
$ErrorActionPreference = 'Stop'

# Resolve directories
$mi = Split-Path -Parent $PSScriptRoot
$root = Split-Path -Parent $mi

$m1 = Join-Path $mi 'module1-frontend'
$m2 = Join-Path $mi 'module2-backend'
$m3 = Join-Path $mi 'module3-AI processing service'
$m4 = Join-Path $mi 'module4-knowledge assistant service'

Write-Host "`n=== Meeting Intelligence Assistant Setup ===" -ForegroundColor Cyan

# ------------------------------------------------
# Detect Python on the current machine
# ------------------------------------------------

$pythonExe = $null

$pyLauncher = Get-Command py -ErrorAction SilentlyContinue

if ($pyLauncher) {
    $pythonExe = (& $pyLauncher.Source -3.12 -c "import sys; print(sys.executable)" 2>$null).Trim()

    if ($LASTEXITCODE -ne 0) {
        $pythonExe = $null
    }
}

if (-not $pythonExe) {
    $pythonCommand = Get-Command python -ErrorAction SilentlyContinue

    if ($pythonCommand) {
        $pythonExe = $pythonCommand.Source
    }
}

if (-not $pythonExe -or -not (Test-Path $pythonExe)) {
    throw 'Python 3 is not installed or could not be located. Install Python and retry.'
}

Write-Host "Using Python: $pythonExe" -ForegroundColor Green

# ------------------------------------------------
# Create and configure environments
# ------------------------------------------------

$environments = @(
    @{
        Name = 'Module 2 Backend'
        Directory = $root
        Requirements = Join-Path $m2 'requirements.txt'
    },
    @{
        Name = 'Module 3 AI Processing'
        Directory = $m3
        Requirements = Join-Path $m3 'requirements.txt'
    },
    @{
        Name = 'Module 4 Knowledge Assistant'
        Directory = $m4
        Requirements = Join-Path $m4 'requirements.txt'
    }
)

foreach ($envConfig in $environments) {

    Write-Host "`nSetting up $($envConfig.Name)..." -ForegroundColor Cyan

    $venv = Join-Path $envConfig.Directory '.venv'
    $venvPython = Join-Path $venv 'Scripts\python.exe'

    if (-not (Test-Path $venvPython)) {

        Write-Host 'Creating virtual environment...'

        & $pythonExe -m venv $venv

        if ($LASTEXITCODE -ne 0) {
            throw "Could not create environment for $($envConfig.Name)"
        }
    }

    # Validate that the existing environment is usable
    & $venvPython -c "import sys; print(sys.executable)"

    if ($LASTEXITCODE -ne 0) {
        throw "Environment is broken: $venv. Remove it and rerun setup.ps1."
    }

    # Install dependencies
    if (Test-Path $envConfig.Requirements) {

        Write-Host "Installing dependencies for $($envConfig.Name)..."

        & $venvPython -m pip install -r $envConfig.Requirements

        if ($LASTEXITCODE -ne 0) {
            throw "Dependency installation failed: $($envConfig.Name)"
        }
    }
    else {
        Write-Warning "requirements.txt not found: $($envConfig.Requirements)"
    }

    Write-Host "$($envConfig.Name) ready." -ForegroundColor Green
}

# ------------------------------------------------
# Frontend dependencies
# ------------------------------------------------

Write-Host "`nSetting up frontend..." -ForegroundColor Cyan

if (-not (Test-Path (Join-Path $m1 'package.json'))) {
    throw "Frontend package.json not found in $m1"
}

Push-Location $m1

try {
    if (-not (Get-Command npm -ErrorAction SilentlyContinue)) {
        throw 'npm not found. Install Node.js LTS and retry.'
    }

    npm install

    if ($LASTEXITCODE -ne 0) {
        throw 'Frontend dependency installation failed.'
    }
}
finally {
    Pop-Location
}

Write-Host "`n========================================" -ForegroundColor Green
Write-Host "Setup completed successfully!" -ForegroundColor Green
Write-Host "You can now run .\scripts\start-all.ps1"
Write-Host "========================================`n"