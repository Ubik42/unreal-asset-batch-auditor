param(
    [Parameter(Mandatory = $true)]
    [string]$EngineRoot,
    [string]$Label = "local"
)

$ErrorActionPreference = "Stop"
$repoRoot = Split-Path -Parent $PSScriptRoot
$runUat = Join-Path $EngineRoot "Engine\Build\BatchFiles\RunUAT.bat"
$plugin = Join-Path $repoRoot "UnrealAssetBatchAuditor.uplugin"
$package = Join-Path $repoRoot "artifacts\host-build\$Label"
$stagingRoot = Join-Path ([System.IO.Path]::GetTempPath()) ("uaba-build-" + [guid]::NewGuid().ToString("N"))

if (-not (Test-Path -LiteralPath $runUat)) {
    throw "RunUAT.bat not found under the supplied EngineRoot: $EngineRoot"
}
if (-not (Test-Path -LiteralPath $plugin)) {
    throw "Plugin descriptor missing: $plugin"
}

try {
    New-Item -ItemType Directory -Path $stagingRoot -Force | Out-Null
    Copy-Item -LiteralPath $plugin -Destination $stagingRoot
    foreach ($directory in @("Source", "Content", "config", "Resources")) {
        Copy-Item -LiteralPath (Join-Path $repoRoot $directory) -Destination $stagingRoot -Recurse
    }
    $stagedPlugin = Join-Path $stagingRoot "UnrealAssetBatchAuditor.uplugin"
    & $runUat BuildPlugin "-Plugin=$stagedPlugin" "-Package=$package" -TargetPlatforms=Win64 -Rocket
    if ($LASTEXITCODE -ne 0) {
        throw "BuildPlugin failed with exit code $LASTEXITCODE"
    }
}
finally {
    $resolvedStaging = [System.IO.Path]::GetFullPath($stagingRoot)
    $resolvedTemp = [System.IO.Path]::GetFullPath([System.IO.Path]::GetTempPath())
    if ($resolvedStaging.StartsWith($resolvedTemp, [System.StringComparison]::OrdinalIgnoreCase) -and
        (Split-Path -Leaf $resolvedStaging).StartsWith("uaba-build-")) {
        Remove-Item -LiteralPath $resolvedStaging -Recurse -Force -ErrorAction SilentlyContinue
    }
}
