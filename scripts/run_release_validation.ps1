param(
    [string]$EngineRoot = "C:\Program Files\Epic Games\UE_5.8",
    [Parameter(Mandatory = $true)]
    [string]$ArchivePath,
    [Parameter(Mandatory = $true)]
    [string]$PreviousArchivePath,
    [string]$ReleaseLabel = "v0.10.0-ue5.8.1-win64",
    [int]$TimeoutSeconds = 120
)

$ErrorActionPreference = "Stop"
$repoRoot = Split-Path -Parent $PSScriptRoot
$editorCmd = Join-Path $EngineRoot "Engine\Binaries\Win64\UnrealEditor-Cmd.exe"
$archive = (Resolve-Path -LiteralPath $ArchivePath).Path
$previousArchive = (Resolve-Path -LiteralPath $PreviousArchivePath).Path
$checksumPath = "$archive.sha256"
if (-not (Test-Path -LiteralPath $editorCmd -PathType Leaf)) {
    throw "UnrealEditor-Cmd.exe 不存在：$editorCmd"
}
if (-not (Test-Path -LiteralPath $checksumPath -PathType Leaf)) {
    throw "发布包校验文件不存在：$checksumPath"
}
$expectedArchiveHash = ((Get-Content -LiteralPath $checksumPath -Raw).Trim() -split '\s+')[0].ToUpperInvariant()
$actualArchiveHash = (Get-FileHash -LiteralPath $archive -Algorithm SHA256).Hash
if ($actualArchiveHash -ne $expectedArchiveHash) {
    throw "发布包 SHA-256 不匹配"
}

$runId = Get-Date -Format "yyyyMMdd-HHmmss"
$runtime = Join-Path $repoRoot "artifacts\host-runtime\release-$runId"
$releaseRoot = Join-Path $runtime "Release"
$previousReleaseRoot = Join-Path $runtime "PreviousRelease"
$projectRoot = Join-Path $runtime "FreshProject"
$projectFile = Join-Path $projectRoot "UABAReleaseValidation.uproject"
New-Item -ItemType Directory -Path $releaseRoot, $previousReleaseRoot, $projectRoot -Force | Out-Null
Expand-Archive -LiteralPath $archive -DestinationPath $releaseRoot
Expand-Archive -LiteralPath $previousArchive -DestinationPath $previousReleaseRoot
$projectJson = [ordered]@{
    FileVersion = 3
    EngineAssociation = "5.8"
    Category = "Testing"
    Description = "Fresh disposable host for Unreal Asset Batch Auditor release validation."
} | ConvertTo-Json -Depth 4
$projectJson | Set-Content -LiteralPath $projectFile -Encoding utf8

$installer = Join-Path $releaseRoot "install-plugin.ps1"
$previousInstaller = Join-Path $previousReleaseRoot "install-plugin.ps1"
$releaseManifestPath = Join-Path $releaseRoot "RELEASE-MANIFEST.json"
foreach ($required in @($installer, $previousInstaller, $releaseManifestPath, (Join-Path $releaseRoot "UnrealAssetBatchAuditor\UnrealAssetBatchAuditor.uplugin"))) {
    if (-not (Test-Path -LiteralPath $required -PathType Leaf)) {
        throw "发布包缺少必要文件：$required"
    }
}

$existing = @(Get-Process UnrealEditor, UnrealEditor-Cmd -ErrorAction SilentlyContinue | Select-Object -ExpandProperty Id)
$createdPids = [Collections.Generic.HashSet[int]]::new()

function Invoke-ReleaseSmoke([string]$Phase) {
    $installedRoot = Join-Path $projectRoot "Plugins\UnrealAssetBatchAuditor"
    $env:UABA_RELEASE_PLUGIN_ROOT = $installedRoot
    $arguments = @(
        $projectFile,
        '-ExecCmds="Automation RunTests UnrealAssetBatchAuditor.ReleaseInstallSmoke"',
        '-TestExit="Automation Test Queue Empty"',
        '-unattended', '-nop4', '-nosplash', '-RenderOffscreen'
    )
    $startedAt = [DateTimeOffset]::UtcNow
    $process = Start-Process -FilePath $editorCmd -ArgumentList $arguments -PassThru -WindowStyle Hidden
    [void]$createdPids.Add($process.Id)
    $deadline = [DateTimeOffset]::UtcNow.AddSeconds($TimeoutSeconds)
    while (-not $process.HasExited -and [DateTimeOffset]::UtcNow -lt $deadline) {
        Start-Sleep -Milliseconds 250
    }
    $timedOut = -not $process.HasExited
    if ($timedOut) {
        Stop-Process -Id $process.Id -Force -ErrorAction SilentlyContinue
    }
    $finishedAt = [DateTimeOffset]::UtcNow
    $logPath = Join-Path $projectRoot "Saved\Logs\UABAReleaseValidation.log"
    $log = if (Test-Path -LiteralPath $logPath) { Get-Content -LiteralPath $logPath -Raw } else { "" }
    $passed = $log -match 'Test Completed\. Result=\{Success\} Name=\{ReleaseInstallSmoke\}'
    $phaseLog = Join-Path $runtime "$Phase-log.txt"
    $logPatterns = @(
        'engineversion=', 'Command Line:', 'Found 1 automation', 'Test Started',
        'Test Completed', 'Automation Test Queue Empty', 'Engine exit requested'
    )
    @(Select-String -LiteralPath $logPath -Pattern $logPatterns | ForEach-Object {
        $_.Line.Replace($repoRoot, "<repo>")
    }) |
        Set-Content -LiteralPath $phaseLog -Encoding utf8
    if ($timedOut -or $process.ExitCode -ne 0 -or -not $passed) {
        throw "发布包 $Phase 宿主验证失败；请检查 $logPath"
    }
    return [ordered]@{
        phase = $Phase
        pid = $process.Id
        started_at = $startedAt.ToString('o')
        finished_at = $finishedAt.ToString('o')
        duration_seconds = [Math]::Round(($finishedAt - $startedAt).TotalSeconds, 3)
        timed_out = $timedOut
        exit_code = $process.ExitCode
        automation_test = "UnrealAssetBatchAuditor.ReleaseInstallSmoke"
        automation_passed = $passed
        log_path = [IO.Path]::GetRelativePath($repoRoot, $logPath).Replace('\', '/')
        log_excerpt_path = [IO.Path]::GetRelativePath($repoRoot, $phaseLog).Replace('\', '/')
        log_excerpt_sha256 = (Get-FileHash -LiteralPath $phaseLog -Algorithm SHA256).Hash
    }
}

function Invoke-UnattendedReleaseSmoke {
    $installedRoot = Join-Path $projectRoot "Plugins\UnrealAssetBatchAuditor"
    $wrapper = Join-Path $releaseRoot "run-unattended-audit.ps1"
    $preset = Join-Path $installedRoot "Resources\ProjectPresets\engine-basic-shapes-ci.v1.json"
    $summaryPath = Join-Path $projectRoot "Saved\UnrealAssetBatchAuditor\CI\latest-run-summary.json"
    foreach ($required in @($wrapper, $preset)) {
        if (-not (Test-Path -LiteralPath $required -PathType Leaf)) {
            throw "随包无人值守文件不存在：$required"
        }
    }
    $startInfo = [Diagnostics.ProcessStartInfo]::new()
    $startInfo.FileName = Join-Path $PSHOME "pwsh.exe"
    $startInfo.UseShellExecute = $false
    $startInfo.CreateNoWindow = $true
    $startInfo.RedirectStandardOutput = $true
    $startInfo.RedirectStandardError = $true
    $startInfo.StandardOutputEncoding = [Text.UTF8Encoding]::new($false)
    $startInfo.StandardErrorEncoding = [Text.UTF8Encoding]::new($false)
    foreach ($argument in @(
        '-NoProfile', '-File', $wrapper,
        '-EngineRoot', $EngineRoot,
        '-ProjectPath', $projectFile,
        '-PresetPath', $preset,
        '-SummaryPath', $summaryPath,
        '-TimeoutSeconds', '120'
    )) { [void]$startInfo.ArgumentList.Add($argument) }
    $startedAt = [DateTimeOffset]::UtcNow
    $process = [Diagnostics.Process]::Start($startInfo)
    $stdoutTask = $process.StandardOutput.ReadToEndAsync()
    $stderrTask = $process.StandardError.ReadToEndAsync()
    if (-not $process.WaitForExit($TimeoutSeconds * 1000)) {
        $process.Kill($true)
        throw "随包无人值守烟雾超时"
    }
    $finishedAt = [DateTimeOffset]::UtcNow
    $stdout = $stdoutTask.Result.Trim()
    $stderr = $stderrTask.Result.Trim()
    if ($process.ExitCode -ne 0 -or -not (Test-Path -LiteralPath $summaryPath)) {
        throw "随包无人值守烟雾失败；exit=$($process.ExitCode) stdout=$stdout stderr=$stderr"
    }
    $summary = Get-Content -LiteralPath $summaryPath -Raw | ConvertFrom-Json
    $reportPath = [string]$summary.report_path
    if ($summary.status -ne 'passed' -or $summary.exit_code -ne 0 -or
        $summary.collection_failure_count -ne 0 -or -not (Test-Path -LiteralPath $reportPath)) {
        throw "随包无人值守摘要不符合通过合同：$summaryPath"
    }
    $report = Get-Content -LiteralPath $reportPath -Raw | ConvertFrom-Json
    if (-not $report.real_unreal_validation -or @($report.assets).Count -lt 4) {
        throw "随包无人值守 Report 缺少真实 Unreal 采集证据"
    }
    return [ordered]@{
        wrapper_pid = $process.Id
        exit_code = $process.ExitCode
        status = $summary.status
        asset_count = $summary.asset_count
        issue_count = $summary.issue_count
        collection_failure_count = $summary.collection_failure_count
        stdout = $stdout
        stderr = $stderr
        started_at = $startedAt.ToString('o')
        finished_at = $finishedAt.ToString('o')
        duration_seconds = [Math]::Round(($finishedAt - $startedAt).TotalSeconds, 3)
        runtime_summary_path = $summaryPath
        runtime_report_path = $reportPath
    }
}

& $installer -Action Install -ProjectPath $projectFile
$installedRoot = Join-Path $projectRoot "Plugins\UnrealAssetBatchAuditor"
$installedDescriptor = Join-Path $installedRoot "UnrealAssetBatchAuditor.uplugin"
if (-not (Test-Path -LiteralPath $installedDescriptor -PathType Leaf)) {
    throw "安装脚本未创建插件目录"
}
$installedItem = Get-Item -LiteralPath $installedRoot
if ($installedItem.Attributes -band [IO.FileAttributes]::ReparsePoint) {
    throw "全新安装错误地创建了链接而不是独立插件目录"
}
$projectAfterInstall = Get-Content -LiteralPath $projectFile -Raw | ConvertFrom-Json
$enabledAfterInstall = @($projectAfterInstall.Plugins | Where-Object {
    $_.Name -eq "UnrealAssetBatchAuditor" -and $_.Enabled
}).Count -eq 1
if (-not $enabledAfterInstall) { throw "安装脚本未在 .uproject 中启用插件" }
$installSmoke = Invoke-ReleaseSmoke "install"
$unattendedSmoke = Invoke-UnattendedReleaseSmoke

$reportPath = Join-Path $projectRoot "Saved\UnrealAssetBatchAuditor\ReleaseInstallEvidence\latest-report.json"
$textureReportPath = Join-Path $projectRoot "Saved\UnrealAssetBatchAuditor\ReleaseInstallEvidence\latest-texture-report.json"
foreach ($requiredReport in @($reportPath, $textureReportPath)) {
    if (-not (Test-Path -LiteralPath $requiredReport -PathType Leaf)) {
        throw "全新安装宿主缺少双轨 Report：$requiredReport"
    }
}
$freshReport = Get-Content -LiteralPath $reportPath -Raw | ConvertFrom-Json
$freshTextureReport = Get-Content -LiteralPath $textureReportPath -Raw | ConvertFrom-Json
if (-not $freshReport.real_unreal_validation -or @($freshReport.assets).Count -ne 1 -or
    -not $freshTextureReport.real_unreal_validation -or $freshTextureReport.asset_type -ne 'texture2d' -or
    @($freshTextureReport.assets).Count -ne 1 -or @($freshTextureReport.collection_failures).Count -ne 0) {
    throw "全新安装双轨 Report 不符合真实单资产采集合同"
}
$freshStaticRuntime = Join-Path $runtime "fresh-static-mesh-report.json"
$freshTextureRuntime = Join-Path $runtime "fresh-texture-report.json"
Copy-Item -LiteralPath $reportPath -Destination $freshStaticRuntime -Force
Copy-Item -LiteralPath $textureReportPath -Destination $freshTextureRuntime -Force

& $installer -Action Uninstall -ProjectPath $projectFile -ConfirmUninstall
$freshUninstallBackups = @(Get-ChildItem -LiteralPath (Join-Path $projectRoot "PluginBackups") -Directory |
    Where-Object { $_.Name -like "*-uninstalled-*" })
if ((Test-Path -LiteralPath $installedRoot) -or $freshUninstallBackups.Count -lt 1) {
    throw "全新安装后的可恢复卸载验证失败"
}

& $previousInstaller -Action Install -ProjectPath $projectFile
$previousDescriptor = Get-Content -LiteralPath $installedDescriptor -Raw | ConvertFrom-Json
if ($previousDescriptor.VersionName -ne '0.9.0') {
    throw "升级基线必须是公开 v0.9.0，实际为 $($previousDescriptor.VersionName)"
}

& $installer -Action Upgrade -ProjectPath $projectFile
$upgradeBackups = @(Get-ChildItem -LiteralPath (Join-Path $projectRoot "PluginBackups") -Directory |
    Where-Object { $_.Name -like "UnrealAssetBatchAuditor-0.9.0-*" })
if ($upgradeBackups.Count -lt 1) { throw "升级没有留下旧插件备份" }
$upgradeSmoke = Invoke-ReleaseSmoke "upgrade"

foreach ($requiredReport in @($reportPath, $textureReportPath)) {
    if (-not (Test-Path -LiteralPath $requiredReport -PathType Leaf)) {
        throw "v0.9 升级后缺少双轨 Report：$requiredReport"
    }
}
$report = Get-Content -LiteralPath $reportPath -Raw | ConvertFrom-Json
$textureReport = Get-Content -LiteralPath $textureReportPath -Raw | ConvertFrom-Json
if (-not $report.real_unreal_validation -or @($report.assets).Count -ne 1 -or
    -not $textureReport.real_unreal_validation -or $textureReport.asset_type -ne 'texture2d' -or
    @($textureReport.assets).Count -ne 1 -or @($textureReport.collection_failures).Count -ne 0) {
    throw "v0.9 升级后的双轨 Report 不符合真实单资产采集合同"
}

& $installer -Action Uninstall -ProjectPath $projectFile -ConfirmUninstall
$uninstallBackups = @(Get-ChildItem -LiteralPath (Join-Path $projectRoot "PluginBackups") -Directory |
    Where-Object { $_.Name -like "*-uninstalled-*" })
$projectAfterUninstall = Get-Content -LiteralPath $projectFile -Raw | ConvertFrom-Json
$disabledAfterUninstall = @($projectAfterUninstall.Plugins | Where-Object {
    $_.Name -eq "UnrealAssetBatchAuditor"
}).Count -eq 0
if ((Test-Path -LiteralPath $installedRoot) -or $uninstallBackups.Count -lt 1 -or -not $disabledAfterUninstall) {
    throw "卸载或可恢复备份验证失败"
}

$cleanupDeadline = [DateTimeOffset]::UtcNow.AddSeconds(15)
do {
    $after = @(Get-Process UnrealEditor, UnrealEditor-Cmd -ErrorAction SilentlyContinue | Select-Object -ExpandProperty Id)
    $residualCreated = @($after | Where-Object { $_ -in $createdPids })
    if ($residualCreated.Count -gt 0) { Start-Sleep -Milliseconds 250 }
} while ($residualCreated.Count -gt 0 -and [DateTimeOffset]::UtcNow -lt $cleanupDeadline)
$existingSurvived = @($existing | Where-Object { $_ -notin $after }).Count -eq 0
$residualOwned = @(
    Get-CimInstance Win32_Process -Filter "Name='UnrealEditor.exe' OR Name='UnrealEditor-Cmd.exe'" |
        Where-Object { $_.CommandLine -and $_.CommandLine.Contains($projectRoot) } |
        Select-Object -ExpandProperty ProcessId
)
if ($residualCreated.Count -gt 0 -or $residualOwned.Count -gt 0) {
    throw "发布验证留下了本轮全新项目对应的 Unreal 进程"
}

$evidenceRoot = Join-Path $repoRoot "artifacts\host-validation\m16"
New-Item -ItemType Directory -Path $evidenceRoot -Force | Out-Null
$committedFreshStaticReport = Join-Path $evidenceRoot "$ReleaseLabel-fresh-static-mesh-report.json"
$committedFreshTextureReport = Join-Path $evidenceRoot "$ReleaseLabel-fresh-texture-report.json"
$committedUpgradeStaticReport = Join-Path $evidenceRoot "$ReleaseLabel-upgrade-static-mesh-report.json"
$committedUpgradeTextureReport = Join-Path $evidenceRoot "$ReleaseLabel-upgrade-texture-report.json"
$installLogEvidence = Join-Path $evidenceRoot "$ReleaseLabel-install-log.txt"
$upgradeLogEvidence = Join-Path $evidenceRoot "$ReleaseLabel-upgrade-log.txt"
$unattendedSummaryEvidence = Join-Path $evidenceRoot "$ReleaseLabel-unattended-summary.json"
$unattendedReportEvidence = Join-Path $evidenceRoot "$ReleaseLabel-unattended-report.json"
Copy-Item -LiteralPath $freshStaticRuntime -Destination $committedFreshStaticReport -Force
Copy-Item -LiteralPath $freshTextureRuntime -Destination $committedFreshTextureReport -Force
Copy-Item -LiteralPath $reportPath -Destination $committedUpgradeStaticReport -Force
Copy-Item -LiteralPath $textureReportPath -Destination $committedUpgradeTextureReport -Force
Copy-Item -LiteralPath (Join-Path $runtime "install-log.txt") -Destination $installLogEvidence -Force
Copy-Item -LiteralPath (Join-Path $runtime "upgrade-log.txt") -Destination $upgradeLogEvidence -Force
Copy-Item -LiteralPath $unattendedSmoke.runtime_report_path -Destination $unattendedReportEvidence -Force
$unattendedSummaryPayload = Get-Content -LiteralPath $unattendedSmoke.runtime_summary_path -Raw | ConvertFrom-Json
$unattendedSummaryPayload.report_path = [IO.Path]::GetRelativePath(
    $repoRoot, $unattendedReportEvidence).Replace('\', '/')
$unattendedSummaryPayload | ConvertTo-Json -Depth 8 |
    Set-Content -LiteralPath $unattendedSummaryEvidence -Encoding utf8
$installSmoke.log_excerpt_path = [IO.Path]::GetRelativePath($repoRoot, $installLogEvidence).Replace('\', '/')
$installSmoke.log_excerpt_sha256 = (Get-FileHash -LiteralPath $installLogEvidence -Algorithm SHA256).Hash
$upgradeSmoke.log_excerpt_path = [IO.Path]::GetRelativePath($repoRoot, $upgradeLogEvidence).Replace('\', '/')
$upgradeSmoke.log_excerpt_sha256 = (Get-FileHash -LiteralPath $upgradeLogEvidence -Algorithm SHA256).Hash

$releaseManifest = Get-Content -LiteralPath $releaseManifestPath -Raw | ConvertFrom-Json
$evidence = [ordered]@{
    schema_version = "unreal-audit-release-validation@1.0.0"
    created_at = [DateTimeOffset]::UtcNow.ToString('o')
    release_label = $ReleaseLabel
    plugin_version = $releaseManifest.plugin_version
    tested_engine_version = "5.8.1"
    platform = "Win64"
    archive_path = [IO.Path]::GetRelativePath($repoRoot, $archive).Replace('\', '/')
    archive_bytes = (Get-Item -LiteralPath $archive).Length
    archive_sha256 = $actualArchiveHash
    payload_tree_sha256 = $releaseManifest.payload_tree_sha256
    payload_file_count = $releaseManifest.payload_file_count
    source_revision = $releaseManifest.source_revision
    fresh_project_created = $true
    install = [ordered]@{
        independent_copy = $true
        project_descriptor_enabled = $enabledAfterInstall
        plugin_is_reparse_point = $false
        smoke = $installSmoke
        static_mesh_report_path = [IO.Path]::GetRelativePath($repoRoot, $committedFreshStaticReport).Replace('\', '/')
        static_mesh_report_sha256 = (Get-FileHash -LiteralPath $committedFreshStaticReport -Algorithm SHA256).Hash
        texture_report_path = [IO.Path]::GetRelativePath($repoRoot, $committedFreshTextureReport).Replace('\', '/')
        texture_report_sha256 = (Get-FileHash -LiteralPath $committedFreshTextureReport -Algorithm SHA256).Hash
        recoverable_uninstall_passed = $freshUninstallBackups.Count -ge 1
    }
    upgrade = [ordered]@{
        previous_archive_source = "github-release:v0.9.0/$([IO.Path]::GetFileName($previousArchive))"
        previous_archive_sha256 = (Get-FileHash -LiteralPath $previousArchive -Algorithm SHA256).Hash
        previous_plugin_version = [string]$previousDescriptor.VersionName
        backup_created = $upgradeBackups.Count -ge 1
        smoke = $upgradeSmoke
        static_mesh_report_path = [IO.Path]::GetRelativePath($repoRoot, $committedUpgradeStaticReport).Replace('\', '/')
        static_mesh_report_sha256 = (Get-FileHash -LiteralPath $committedUpgradeStaticReport -Algorithm SHA256).Hash
        texture_report_path = [IO.Path]::GetRelativePath($repoRoot, $committedUpgradeTextureReport).Replace('\', '/')
        texture_report_sha256 = (Get-FileHash -LiteralPath $committedUpgradeTextureReport -Algorithm SHA256).Hash
    }
    unattended = [ordered]@{
        wrapper_exit_code = $unattendedSmoke.exit_code
        status = $unattendedSmoke.status
        asset_count = $unattendedSmoke.asset_count
        issue_count = $unattendedSmoke.issue_count
        collection_failure_count = $unattendedSmoke.collection_failure_count
        stdout = $unattendedSmoke.stdout.Replace($repoRoot, "<repo>")
        duration_seconds = $unattendedSmoke.duration_seconds
        summary_path = [IO.Path]::GetRelativePath($repoRoot, $unattendedSummaryEvidence).Replace('\', '/')
        summary_sha256 = (Get-FileHash -LiteralPath $unattendedSummaryEvidence -Algorithm SHA256).Hash
        report_path = [IO.Path]::GetRelativePath($repoRoot, $unattendedReportEvidence).Replace('\', '/')
        report_sha256 = (Get-FileHash -LiteralPath $unattendedReportEvidence -Algorithm SHA256).Hash
    }
    uninstall = [ordered]@{
        plugin_directory_removed = -not (Test-Path -LiteralPath $installedRoot)
        recoverable_backup_created = $uninstallBackups.Count -ge 1
        project_descriptor_entry_removed = $disabledAfterUninstall
    }
    report_path = [IO.Path]::GetRelativePath($repoRoot, $committedUpgradeStaticReport).Replace('\', '/')
    report_sha256 = (Get-FileHash -LiteralPath $committedUpgradeStaticReport -Algorithm SHA256).Hash
    existing_unreal_pids_before = $existing
    created_unreal_pids = @($createdPids | Sort-Object)
    existing_unreal_pids_after = $after
    existing_processes_survived = $existingSurvived
    residual_created_processes = $residualCreated
    residual_owned_processes = $residualOwned
    preexisting_processes_managed_by_test = $false
    claims_user_interaction = $false
    claims_visible_editor_review = $false
    claims_cross_version_compatibility = $false
}
$evidencePath = Join-Path $evidenceRoot "$ReleaseLabel-validation.json"
$evidence | ConvertTo-Json -Depth 10 | Set-Content -LiteralPath $evidencePath -Encoding utf8
Write-Output "发布包全新安装、升级、卸载与双宿主验证通过：$evidencePath"
