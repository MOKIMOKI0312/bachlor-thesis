# Codex polling script.
# Runs every 60 seconds via Windows Task Scheduler.
# Pulls latest from origin/master, checks status.json for pending Codex tasks,
# triggers a beep + flag file alert when a new task is detected.
#
# Owner: agent_comms protocol v1. Do not modify without coordinating with Claude.

$ErrorActionPreference = "Continue"
$RepoRoot = "C:\Users\18430\Desktop\毕业设计代码"
$LogPath = Join-Path $RepoRoot "agent_comms\_poll.log"

function Log {
    param([string]$Message)
    $line = "[$(Get-Date -Format 'yyyy-MM-dd HH:mm:ss')] $Message"
    Add-Content -Path $LogPath -Value $line -Encoding utf8
    Write-Host $line
}

if (-not (Test-Path $RepoRoot)) {
    Log "ERROR: repo not found: $RepoRoot"
    exit 1
}

Set-Location $RepoRoot

# Pull latest. Don't fail catastrophically — just retry next tick.
$pullOutput = git pull origin master --quiet 2>&1
if ($LASTEXITCODE -ne 0) {
    Log "git pull failed: $pullOutput"
    exit 0
}

$statusPath = Join-Path $RepoRoot "agent_comms\status.json"
if (-not (Test-Path $statusPath)) {
    Log "no status.json yet, skip"
    exit 0
}

try {
    $status = Get-Content -Raw -Encoding utf8 $statusPath | ConvertFrom-Json
} catch {
    Log "ERROR: cannot parse status.json: $_"
    exit 0
}

# Idempotency: track last seen turn to avoid re-alerting on same task.
$lastSeenPath = Join-Path $RepoRoot "agent_comms\_last_seen_turn.txt"
$lastSeen = if (Test-Path $lastSeenPath) {
    (Get-Content -Encoding utf8 $lastSeenPath).Trim()
} else { "0" }

$shouldAlert = ($status.next_action -eq "codex_to_process") `
    -and ($status.codex_inbox.status -eq "pending") `
    -and ("$($status.current_turn)" -ne $lastSeen)

if ($shouldAlert) {
    $turn = $status.current_turn
    $topic = $status.codex_inbox.topic
    Log "*** NEW TASK *** turn=$turn topic=$topic"

    # Audible beep, twice
    [Console]::Beep(880, 400)
    Start-Sleep -Milliseconds 200
    [Console]::Beep(880, 400)

    # Flag file the user (or a UI watcher) can pick up
    $flagPath = Join-Path $RepoRoot "agent_comms\_new_task_for_codex.flag"
    @"
turn=$turn
topic=$topic
written_at=$(Get-Date -Format 'o')
codex_inbox=agent_comms/codex_inbox.md
"@ | Set-Content -Path $flagPath -Encoding utf8

    "$turn" | Set-Content -Path $lastSeenPath -Encoding utf8

    # Check timeout (>24h since written, still pending)
    try {
        $writtenAt = [DateTime]::Parse($status.last_writer_timestamp_utc).ToUniversalTime()
        $age = (Get-Date).ToUniversalTime() - $writtenAt
        if ($age.TotalHours -gt 24) {
            Log "WARN: task pending >24h, escalating"
            [Console]::Beep(440, 800)  # Lower, longer beep for escalation
        }
    } catch {
        Log "WARN: cannot parse last_writer_timestamp_utc"
    }
} elseif ($status.next_action -eq "idle") {
    # Quiet path; nothing to do.
} else {
    # Other states: claude_to_review, or codex_to_process but already alerted.
    Log "state=$($status.next_action) codex=$($status.codex_inbox.status) claude=$($status.claude_inbox.status) seen=$lastSeen"
}
