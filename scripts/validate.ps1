param(
    [ValidateSet("quick")]
    [string]$Tier = "quick"
)

$ErrorActionPreference = "Stop"
$repoRoot = Split-Path -Parent $PSScriptRoot
$python = Join-Path $repoRoot ".venv\Scripts\python.exe"
if (-not (Test-Path -LiteralPath $python)) {
    throw "Missing .venv. Run: python -m venv .venv"
}

& $python (Join-Path $repoRoot "scripts\validate_goal_state.py")
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
& $python -m pytest -q
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
& $python -m ruff check Content/Python Demo/Scripts tests scripts
exit $LASTEXITCODE
