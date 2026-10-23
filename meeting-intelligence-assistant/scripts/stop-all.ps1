param(
    [switch]$KeepDb
)

$ErrorActionPreference = 'Stop'

function Get-DescendantIds {
    param([int]$ParentId)
    $children = @(Get-CimInstance Win32_Process -Filter "ParentProcessId=$ParentId" -ErrorAction SilentlyContinue)
    foreach ($child in $children) {
        $child.ProcessId
        Get-DescendantIds -ParentId $child.ProcessId
    }
}

foreach ($port in 3000, 8000, 8001, 8002) {
    $connections = @(Get-NetTCPConnection -LocalPort $port -State Listen -ErrorAction SilentlyContinue)
    foreach ($connection in $connections) {
        $process = Get-Process -Id $connection.OwningProcess -ErrorAction SilentlyContinue
        if ($null -eq $process) { continue }
        if ($process.ProcessName -notmatch 'python|node') {
            Write-Host "Skipping PID $($process.Id) ($($process.ProcessName)) on :$port" -ForegroundColor Yellow
            continue
        }
        $descendants = @(Get-DescendantIds -ParentId $process.Id)
        foreach ($childId in $descendants) {
            Stop-Process -Id $childId -Force -ErrorAction SilentlyContinue
        }
        Write-Host "Stopping $($process.ProcessName) PID $($process.Id) on :$port"
        Stop-Process -Id $process.Id -Force
    }
}

if (-not $KeepDb) {
    docker info 2>$null | Out-Null
    if ($LASTEXITCODE -eq 0) {
        Write-Host 'Stopping Postgres container meeting-db...'
        docker stop meeting-db | Out-Null
    }
}

Write-Host 'Stop complete.' -ForegroundColor Green
