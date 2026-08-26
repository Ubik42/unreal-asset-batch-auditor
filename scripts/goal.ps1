param(
    [ValidateSet("Resume", "Doctor", "Audit")]
    [string]$Action = "Resume"
)

$ErrorActionPreference = "Stop"
$repoRoot = Split-Path -Parent $PSScriptRoot
$statePath = Join-Path $repoRoot "config\goal-state.json"
$python = Join-Path $repoRoot ".venv\Scripts\python.exe"

if (-not (Test-Path -LiteralPath $statePath)) {
    throw "Missing goal state: $statePath"
}
$state = Get-Content -LiteralPath $statePath -Raw -Encoding UTF8 | ConvertFrom-Json

if ($Action -eq "Resume") {
    [pscustomobject]@{
        Goal = $state.goalId
        Status = $state.status
        Revision = $state.stateRevision
        Milestone = $state.currentMilestone
        NextSlice = $state.nextSlice.id
        Checkpoint = $state.lastCheckpoint
        EvidenceCeiling = $state.nextSlice.evidenceCeiling
    } | Format-List
    exit 0
}

if (-not (Test-Path -LiteralPath $python)) {
    throw "Missing .venv. Create it before $Action."
}
& $python (Join-Path $repoRoot "scripts\validate_goal_state.py")
exit $LASTEXITCODE
