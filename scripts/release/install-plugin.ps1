param(
    [Parameter(Mandatory = $true)]
    [ValidateSet("Install", "Upgrade", "Uninstall")]
    [string]$Action,
    [Parameter(Mandatory = $true)]
    [string]$ProjectPath,
    [switch]$ConfirmUninstall
)

$ErrorActionPreference = "Stop"
$pluginName = "UnrealAssetBatchAuditor"
$sourcePlugin = Join-Path $PSScriptRoot $pluginName

function Resolve-ProjectRoot([string]$InputPath) {
    $resolved = Resolve-Path -LiteralPath $InputPath -ErrorAction Stop
    if ((Get-Item -LiteralPath $resolved).PSIsContainer) {
        $projects = @(Get-ChildItem -LiteralPath $resolved -Filter "*.uproject" -File)
        if ($projects.Count -ne 1) {
            throw "项目目录必须恰好包含一个 .uproject：$resolved"
        }
        return $resolved.Path
    }
    if ([IO.Path]::GetExtension($resolved.Path) -ne ".uproject") {
        throw "ProjectPath 必须是项目目录或 .uproject 文件：$resolved"
    }
    return Split-Path -Parent $resolved.Path
}

function Assert-OwnedPlugin([string]$Path) {
    $descriptor = Join-Path $Path "$pluginName.uplugin"
    if (-not (Test-Path -LiteralPath $descriptor -PathType Leaf)) {
        throw "拒绝操作：目标不是可识别的 $pluginName 插件目录：$Path"
    }
    $item = Get-Item -LiteralPath $Path
    if ($item.Attributes -band [IO.FileAttributes]::ReparsePoint) {
        throw "拒绝操作符号链接或 Junction，请先手动移除开发链接：$Path"
    }
    $payload = Get-Content -LiteralPath $descriptor -Raw | ConvertFrom-Json
    if (@($payload.Modules | ForEach-Object { $_.Name }) -notcontains $pluginName) {
        throw "拒绝操作：descriptor 不包含预期模块 $pluginName"
    }
    return $payload
}

$projectRoot = Resolve-ProjectRoot $ProjectPath
$projectFile = @(Get-ChildItem -LiteralPath $projectRoot -Filter "*.uproject" -File)[0].FullName
$pluginsRoot = Join-Path $projectRoot "Plugins"
$targetPlugin = Join-Path $pluginsRoot $pluginName
$backupRoot = Join-Path $projectRoot "PluginBackups"

function Set-ProjectPluginEnabled([bool]$Enabled) {
    $project = Get-Content -LiteralPath $projectFile -Raw | ConvertFrom-Json
    $entries = @($project.Plugins | Where-Object { $null -ne $_ })
    $matching = @($entries | Where-Object { $_.Name -eq $pluginName })
    if ($Enabled) {
        if ($matching.Count -eq 0) {
            $entries += [pscustomobject]@{ Name = $pluginName; Enabled = $true }
        } else {
            foreach ($entry in $matching) { $entry.Enabled = $true }
        }
    } else {
        $entries = @($entries | Where-Object { $_.Name -ne $pluginName })
    }
    $project | Add-Member -NotePropertyName Plugins -NotePropertyValue $entries -Force
    $descriptorBackups = Join-Path $backupRoot "ProjectDescriptors"
    New-Item -ItemType Directory -Path $descriptorBackups -Force | Out-Null
    $backup = Join-Path $descriptorBackups (
        ([IO.Path]::GetFileName($projectFile)) + "." + (Get-Date -Format "yyyyMMdd-HHmmssfff") + ".bak"
    )
    Copy-Item -LiteralPath $projectFile -Destination $backup
    $temporary = "$projectFile.uaba.tmp"
    try {
        $project | ConvertTo-Json -Depth 100 | Set-Content -LiteralPath $temporary -Encoding utf8
        Get-Content -LiteralPath $temporary -Raw | ConvertFrom-Json | Out-Null
        Move-Item -LiteralPath $temporary -Destination $projectFile -Force
    } finally {
        if (Test-Path -LiteralPath $temporary) {
            Remove-Item -LiteralPath $temporary -Force
        }
    }
}

if ($Action -in @("Install", "Upgrade")) {
    [void](Assert-OwnedPlugin $sourcePlugin)
    New-Item -ItemType Directory -Path $pluginsRoot -Force | Out-Null
    $staging = Join-Path $pluginsRoot (".$pluginName.install-" + [guid]::NewGuid().ToString("N"))
    Copy-Item -LiteralPath $sourcePlugin -Destination $staging -Recurse
    try {
        if ($Action -eq "Install") {
            if (Test-Path -LiteralPath $targetPlugin) {
                throw "插件已存在；请使用 -Action Upgrade：$targetPlugin"
            }
            Move-Item -LiteralPath $staging -Destination $targetPlugin
        } else {
            if (-not (Test-Path -LiteralPath $targetPlugin -PathType Container)) {
                throw "尚未安装插件；请使用 -Action Install：$targetPlugin"
            }
            $old = Assert-OwnedPlugin $targetPlugin
            New-Item -ItemType Directory -Path $backupRoot -Force | Out-Null
            $backup = Join-Path $backupRoot (
                "$pluginName-" + $old.VersionName + "-" + (Get-Date -Format "yyyyMMdd-HHmmss")
            )
            Move-Item -LiteralPath $targetPlugin -Destination $backup
            try {
                Move-Item -LiteralPath $staging -Destination $targetPlugin
            } catch {
                if (Test-Path -LiteralPath $targetPlugin) {
                    Remove-Item -LiteralPath $targetPlugin -Recurse -Force
                }
                Move-Item -LiteralPath $backup -Destination $targetPlugin
                throw
            }
            Write-Output "旧版本已备份：$backup"
        }
    } finally {
        if (Test-Path -LiteralPath $staging) {
            Remove-Item -LiteralPath $staging -Recurse -Force
        }
    }
    $installed = Assert-OwnedPlugin $targetPlugin
    Set-ProjectPluginEnabled $true
    Write-Output "插件 $Action 成功：$($installed.VersionName) -> $targetPlugin"
    Write-Output "项目 descriptor 已启用插件；请启动 Unreal Editor，必要时按提示重启。"
    exit 0
}

if (-not $ConfirmUninstall) {
    throw "卸载需要显式添加 -ConfirmUninstall；插件会先移动到项目 PluginBackups 以便恢复。"
}
if (-not (Test-Path -LiteralPath $targetPlugin -PathType Container)) {
    throw "插件尚未安装：$targetPlugin"
}
$installed = Assert-OwnedPlugin $targetPlugin
New-Item -ItemType Directory -Path $backupRoot -Force | Out-Null
$uninstallBackup = Join-Path $backupRoot (
    "$pluginName-$($installed.VersionName)-uninstalled-" + (Get-Date -Format "yyyyMMdd-HHmmss")
)
Move-Item -LiteralPath $targetPlugin -Destination $uninstallBackup
Set-ProjectPluginEnabled $false
Write-Output "插件已从项目卸载，并保留可恢复副本：$uninstallBackup"
