param(
    [string]$EngineRoot = "C:\Program Files\Epic Games\UE_5.8",
    [string]$BuildLabel = "UE_5.8.1-v0.6.0-dev1",
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
    "generate_demo_assets.py",
    "run_demo_balanced.py",
    "run_demo_mobile.py",
    "run_demo_lenient.py"
)
foreach ($scriptName in $demoScripts) {
    $scriptPath = Join-Path $repoRoot "Demo\Scripts\$scriptName"
    & $editorCmd $project "-ExecutePythonScript=$scriptPath" -unattended -nop4 -nosplash -NullRHI
    if ($LASTEXITCODE -ne 0) {
        throw "Demo host script failed: $scriptName"
    }
}

Write-Output "Demo kit ready: $project"
Write-Output "Recorded reports: $(Join-Path $repoRoot 'artifacts\demo')"
