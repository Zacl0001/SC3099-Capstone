<#
.SYNOPSIS
    End-to-end test of the transcript -> AI + RAG pipeline through module2.

.DESCRIPTION
    Uploads a transcript, processes it, then calls every AI endpoint exposed by
    the backend: summary, action items, decisions, topics, and RAG chat with
    citations. Requires the stack to be running:

        .\scripts\start-all.ps1

.EXAMPLE
    .\scripts\test-transcript.ps1

.EXAMPLE
    .\scripts\test-transcript.ps1 -Transcript .\my-meeting.txt -Delete
#>
param(
    [string]$BaseUrl = 'http://127.0.0.1:8000',
    [string]$Email = 'tester@example.com',
    [string]$Password = 'password123',
    [string]$Transcript = '',
    [string]$Title = '',
    [string]$Question = 'When is the new launch date, and what must QA do before it?',
    [int]$TimeoutSeconds = 300,
    [switch]$SkipChat,
    [switch]$Delete
)

$ErrorActionPreference = 'Stop'
$BaseUrl = $BaseUrl.TrimEnd('/')

$mi = Split-Path -Parent $PSScriptRoot
if (-not $Transcript) { $Transcript = Join-Path $PSScriptRoot 'sample-transcript.txt' }
if (-not $Title) { $Title = "Transcript test $(Get-Date -Format 'yyyy-MM-dd HH:mm:ss')" }

$script:results = @()

function Write-Head([string]$Text) {
    Write-Host "`n=== $Text ===" -ForegroundColor Cyan
}

function Assert-True([bool]$Condition, [string]$Message) {
    if (-not $Condition) { throw $Message }
}

function Test-Port([int]$Port, [string]$ComputerName = '127.0.0.1') {
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
        [scriptblock]$Action
    )
    Write-Head $Name
    $sw = [Diagnostics.Stopwatch]::StartNew()
    try {
        & $Action
        $sw.Stop()
        Write-Host ("[PASS] {0} ({1:N1}s)" -f $Name, $sw.Elapsed.TotalSeconds) -ForegroundColor Green
        $script:results += [pscustomobject]@{ Step = $Name; Status = 'PASS'; Seconds = [math]::Round($sw.Elapsed.TotalSeconds, 1) }
    } catch {
        $sw.Stop()
        Write-Host ("[FAIL] {0} ({1:N1}s): {2}" -f $Name, $sw.Elapsed.TotalSeconds, $_.Exception.Message) -ForegroundColor Red
        $script:results += [pscustomobject]@{ Step = $Name; Status = 'FAIL'; Seconds = [math]::Round($sw.Elapsed.TotalSeconds, 1) }
        throw
    }
}

function Show-Result([string]$Label, $Value) {
    $json = $Value | ConvertTo-Json -Depth 10 -Compress
    if ($json.Length -gt 1200) { $json = $json.Substring(0, 1200) + '…' }
    Write-Host ("  {0}: {1}" -f $Label, $json) -ForegroundColor DarkGray
}

# ---------------------------------------------------------------------------
# Preflight
# ---------------------------------------------------------------------------

if (-not (Test-Path -LiteralPath $Transcript)) {
    throw "Transcript not found: $Transcript"
}

Write-Head 'Preflight'
$services = @(
    @{ Name = 'backend (:8000)';   Port = 8000 },
    @{ Name = 'module3 AI (:8001)'; Port = 8001 },
    @{ Name = 'KAS (:8002)';       Port = 8002 },
    @{ Name = 'Postgres (:5432)';  Port = 5432 },
    @{ Name = 'Ollama (:11434)';   Port = 11434 }
)
$down = @($services | Where-Object { -not (Test-Port $_.Port) })
if ($down.Count -gt 0) {
    Write-Host 'The following services are not listening:' -ForegroundColor Red
    $down | ForEach-Object { Write-Host "  - $($_.Name)" }
    Write-Host "Start the stack with: .\scripts\start-all.ps1" -ForegroundColor Yellow
    exit 2
}
Write-Host "Using transcript: $Transcript" -ForegroundColor DarkGray

$session = $null
$meetingId = $null

try {
    # -----------------------------------------------------------------------
    # Auth
    # -----------------------------------------------------------------------

    Invoke-Step -Name 'auth: register / login' -Action {
        try {
            $null = Invoke-RestMethod "$BaseUrl/api/auth/register" -Method Post `
                -ContentType 'application/json' `
                -Body (@{ email = $Email; password = $Password } | ConvertTo-Json) -TimeoutSec 30
            Write-Host "  Registered $Email" -ForegroundColor DarkGray
        } catch {
            $code = $_.Exception.Response.StatusCode.value__
            if ($code -ne 409) { throw }
            Write-Host "  $Email already exists" -ForegroundColor DarkGray
        }

        $login = Invoke-RestMethod "$BaseUrl/api/auth/login" -Method Post `
            -ContentType 'application/json' `
            -Body (@{ email = $Email; password = $Password } | ConvertTo-Json) -TimeoutSec 30
        Assert-True ([bool]$login.access_token) 'login did not return an access token'
        $script:session = $login.access_token
    }

    $headers = @{ Authorization = "Bearer $session" }

    # -----------------------------------------------------------------------
    # Upload + process
    # -----------------------------------------------------------------------

    Invoke-Step -Name 'meeting: upload transcript' -Action {
        $raw = & curl.exe -s -X POST "$BaseUrl/api/meetings/upload" `
            -H "Authorization: Bearer $session" `
            -F "title=$Title" `
            -F "file=@$Transcript;type=text/plain" 2>$null
        if ($LASTEXITCODE -ne 0 -or -not $raw) { throw 'upload request failed' }
        $meeting = $raw | ConvertFrom-Json
        Assert-True ([bool]$meeting.id) 'upload did not return a meeting id'
        $script:meetingId = $meeting.id
        Write-Host "  Meeting id=$($meeting.id) title=$($meeting.title)" -ForegroundColor DarkGray
    }

    Invoke-Step -Name 'meeting: process transcript' -Action {
        $processed = Invoke-RestMethod "$BaseUrl/api/meetings/$meetingId/transcript/process" `
            -Method Post -Headers $headers -TimeoutSec $TimeoutSeconds
        Assert-True ($processed.sections.Count -gt 0) 'processing returned no speaker sections'
        Write-Host "  $($processed.sections.Count) sections" -ForegroundColor DarkGray
    }

    Invoke-Step -Name 'rag: index transcript' -Action {
        $indexed = Invoke-RestMethod "$BaseUrl/api/meetings/$meetingId/index" `
            -Method Post -Headers $headers -TimeoutSec $TimeoutSeconds
        Assert-True ([bool]$indexed.meeting_id) 'indexing did not return a meeting id'
        Write-Host "  Indexed as $($indexed.meeting_id) ($($indexed.chunks) chunks)" -ForegroundColor DarkGray
    }

    # -----------------------------------------------------------------------
    # AI outputs
    # -----------------------------------------------------------------------

    Invoke-Step -Name 'ai: summary' -Action {
        $summary = Invoke-RestMethod "$BaseUrl/api/meetings/$meetingId/summary" `
            -Headers $headers -TimeoutSec $TimeoutSeconds
        Assert-True ([bool]$summary.summary) 'summary was empty'
        Assert-True ($null -ne $summary.key_points) 'key_points missing'
        Show-Result 'summary' $summary
    }

    Invoke-Step -Name 'ai: action items' -Action {
        $actions = Invoke-RestMethod "$BaseUrl/api/meetings/$meetingId/action-items" `
            -Headers $headers -TimeoutSec $TimeoutSeconds
        Assert-True ($actions.action_items.Count -gt 0) 'no action items returned'
        foreach ($item in $actions.action_items) {
            Assert-True ([bool]$item.task) 'action item without a task'
        }
        Show-Result 'action_items' $actions
    }

    Invoke-Step -Name 'ai: decisions' -Action {
        $decisions = Invoke-RestMethod "$BaseUrl/api/meetings/$meetingId/decisions" `
            -Headers $headers -TimeoutSec $TimeoutSeconds
        Assert-True ($decisions.decisions.Count -gt 0) 'no decisions returned'
        Show-Result 'decisions' $decisions
    }

    Invoke-Step -Name 'ai: topics' -Action {
        $topics = Invoke-RestMethod "$BaseUrl/api/meetings/$meetingId/topics" `
            -Headers $headers -TimeoutSec $TimeoutSeconds
        Assert-True ($topics.topics.Count -gt 0) 'no topics returned'
        Show-Result 'topics' $topics
    }

    # -----------------------------------------------------------------------
    # RAG chat
    # -----------------------------------------------------------------------

    if (-not $SkipChat) {
        Invoke-Step -Name 'rag: chat with citations' -Action {
            $chat = Invoke-RestMethod "$BaseUrl/api/meetings/$meetingId/chat" -Method Post `
                -Headers $headers -ContentType 'application/json' `
                -Body (@{ question = $Question } | ConvertTo-Json) -TimeoutSec $TimeoutSeconds

            Assert-True ([bool]$chat.answer) 'chat returned an empty answer'
            Assert-True ($chat.answer -notmatch 'could not find this information') 'chat found no relevant transcript content'
            Assert-True ($chat.citations.Count -gt 0) 'chat returned no citations'
            foreach ($citation in $chat.citations) {
                Assert-True ([bool]$citation.chunk_id) 'citation without chunk_id'
                Assert-True ([bool]$citation.text) 'citation without text'
            }
            Show-Result 'chat' $chat
        }
    }

    # -----------------------------------------------------------------------
    # UI hint
    # -----------------------------------------------------------------------

    Write-Head 'Where to look'
    Write-Host "  http://localhost:3000/meetings/$meetingId" -ForegroundColor Green
    Write-Host '  Summary, Action items, Decisions, Ask AI (answers cite transcript lines).' -ForegroundColor DarkGray
}
finally {
    if ($Delete -and $meetingId -and $session) {
        # curl avoids the Windows PowerShell quirk where a 204 response is
        # reported as an exception even though the delete succeeded.
        $code = & curl.exe -s -o NUL -w '%{http_code}' -X DELETE `
            -H "Authorization: Bearer $session" "$BaseUrl/api/meetings/$meetingId" 2>$null
        if ($code -eq '204') {
            Write-Host "`nDeleted test meeting $meetingId" -ForegroundColor DarkGray
        } else {
            Write-Host "`nCould not delete test meeting ${meetingId} (HTTP $code)" -ForegroundColor Yellow
        }
    }
}

# ---------------------------------------------------------------------------
# Summary
# ---------------------------------------------------------------------------

Write-Head 'SUMMARY'
$script:results | Format-Table -AutoSize | Out-String | Write-Host

$failed = @($script:results | Where-Object { $_.Status -eq 'FAIL' })
if ($failed.Count -gt 0) {
    Write-Host "OVERALL: FAIL ($($failed.Count) step(s))" -ForegroundColor Red
    exit 1
}

Write-Host 'OVERALL: PASS' -ForegroundColor Green
exit 0
