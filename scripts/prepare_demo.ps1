param(
    [string]$EngineRoot = "C:\Program Files\Epic Games\UE_5.8",
    [string]$BuildLabel = "UE_5.8.1-v0.8.0-dev3",
    [switch]$SkipBuild
)

$ErrorActionPreference = "Stop"
$repoRoot = Split-Path -Parent $PSScriptRoot
$editorCmd = Join-Path $EngineRoot "Engine\Binaries\Win64\UnrealEditor-Cmd.exe"
$project = Join-Path $repoRoot "Demo\UABADemo.uproject"

if (-not (Test-Path -LiteralPath $editorCmd)) {
    throw "UnrealEditor-Cmd.exe not found: $editorCmd"
}
if (-not $SkipBuild) {
    & (Join-Path $PSScriptRoot "build_plugin.ps1") -EngineRoot $EngineRoot -Label $BuildLabel
    if ($LASTEXITCODE -ne 0) {
        throw "Plugin BuildPlugin failed"
    }
}
& (Join-Path $PSScriptRoot "link_demo_plugin.ps1") -BuildLabel $BuildLabel

$demoScripts = @(
    @{ Variant = "baseline"; Name = "generate_demo_assets.py" },
    @{ Variant = "baseline"; Name = "run_demo_baseline.py" },
    @{ Variant = "current"; Name = "generate_demo_assets.py" },
    @{ Variant = "current"; Name = "run_demo_balanced.py" },
    @{ Variant = "current"; Name = "run_demo_mobile.py" },
    @{ Variant = "current"; Name = "run_demo_lenient.py" }
)
foreach ($entry in $demoScripts) {
    $scriptName = $entry.Name
    $env:UABA_DEMO_VARIANT = $entry.Variant
    $scriptPath = Join-Path $repoRoot "Demo\Scripts\$scriptName"
    & $editorCmd $project "-ExecutePythonScript=$scriptPath" -unattended -nop4 -nosplash -NullRHI
    if ($LASTEXITCODE -ne 0) {
        throw "Demo host script failed: $scriptName"
    }
}
Remove-Item Env:\UABA_DEMO_VARIANT -ErrorAction SilentlyContinue
& (Join-Path $repoRoot ".venv\Scripts\python.exe") `
    (Join-Path $repoRoot "Demo\Scripts\build_demo_session_history.py")
if ($LASTEXITCODE -ne 0) {
    throw "Demo session history build failed"
}

Write-Output "Demo kit ready: $project"
Write-Output "Recorded reports: $(Join-Path $repoRoot 'artifacts\demo')"
