param(
    [string]$BuildLabel = "UE_5.8.1-v0.3.0"
)

$ErrorActionPreference = "Stop"
$repoRoot = Split-Path -Parent $PSScriptRoot
$target = Join-Path $repoRoot "artifacts\host-build\$BuildLabel"
$pluginsRoot = Join-Path $repoRoot "Demo\Plugins"
$link = Join-Path $pluginsRoot "UnrealAssetBatchAuditor"

if (-not (Test-Path -LiteralPath (Join-Path $target "UnrealAssetBatchAuditor.uplugin"))) {
    throw "Packaged plugin not found: $target"
}
if (Test-Path -LiteralPath $link) {
    $resolved = (Get-Item -LiteralPath $link).Target
    if ($resolved -ne $target) {
        throw "Existing demo plugin link targets a different build: $resolved"
    }
    Write-Output "Demo plugin link already ready: $link"
    return
}

New-Item -ItemType Directory -Path $pluginsRoot -Force | Out-Null
New-Item -ItemType Junction -Path $link -Target $target | Out-Null
Write-Output "Linked demo plugin: $link -> $target"
