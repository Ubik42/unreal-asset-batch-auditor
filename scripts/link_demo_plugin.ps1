param(
    [string]$BuildLabel = "UE_5.8.1-v0.5.0-dev3"
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
    $item = Get-Item -LiteralPath $link
    $resolved = $item.Target
    if ($resolved -ne $target) {
        $allowedRoot = [System.IO.Path]::GetFullPath((Join-Path $repoRoot "artifacts\host-build"))
        $resolvedTarget = [System.IO.Path]::GetFullPath([string]$resolved)
        if ($item.LinkType -ne "Junction" -or
            -not $resolvedTarget.StartsWith($allowedRoot, [System.StringComparison]::OrdinalIgnoreCase)) {
            throw "Refusing to replace non-generated demo plugin path: $link -> $resolved"
        }
        Remove-Item -LiteralPath $link -Force
        New-Item -ItemType Junction -Path $link -Target $target | Out-Null
        Write-Output "Updated demo plugin link: $link -> $target"
        return
    }
    Write-Output "Demo plugin link already ready: $link"
    return
}

New-Item -ItemType Directory -Path $pluginsRoot -Force | Out-Null
New-Item -ItemType Junction -Path $link -Target $target | Out-Null
Write-Output "Linked demo plugin: $link -> $target"
