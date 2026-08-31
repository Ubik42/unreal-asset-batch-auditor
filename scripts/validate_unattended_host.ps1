param(
    [string]$EngineRoot = "C:\Program Files\Epic Games\UE_5.8",
    [string]$BuildLabel = "UE_5.8.1-v0.9.0-release1",
    [int]$TimeoutSeconds = 150
)

$ErrorActionPreference = "Stop"
$repoRoot = Split-Path -Parent $PSScriptRoot
$buildRoot = Join-Path $repoRoot "artifacts\host-build\$BuildLabel"
$pluginDescriptor = Join-Path $buildRoot "UnrealAssetBatchAuditor.uplugin"
$sourceProject = Join-Path $repoRoot "tests\host\UnrealAssetBatchAuditorHost.uproject"
$wrapper = Join-Path $PSScriptRoot "run_unattended_audit.ps1"
foreach ($required in @($pluginDescriptor, $sourceProject, $wrapper)) {
    if (-not (Test-Path -LiteralPath $required)) { throw "宿主验证输入不存在：$required" }
}

$runId = Get-Date -Format "yyyyMMdd-HHmmss"
$runtime = Join-Path $repoRoot "artifacts\host-runtime\unattended-$runId"
$pluginTarget = Join-Path $runtime "Plugins\UnrealAssetBatchAuditor"
New-Item -ItemType Directory -Path (Split-Path -Parent $pluginTarget) -Force | Out-Null
Copy-Item -LiteralPath $sourceProject -Destination $runtime
Copy-Item -LiteralPath $buildRoot -Destination $pluginTarget -Recurse

$project = Join-Path $runtime "UnrealAssetBatchAuditorHost.uproject"
$preset = Join-Path $pluginTarget "Resources\ProjectPresets\engine-basic-shapes-ci.v1.json"
$summary = Join-Path $runtime "Saved\UnrealAssetBatchAuditor\CI\latest-run-summary.json"
$existing = @(Get-Process UnrealEditor, UnrealEditor-Cmd -ErrorAction SilentlyContinue | Select-Object -ExpandProperty Id)
$startedAt = [DateTimeOffset]::UtcNow

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
    '-ProjectPath', $project,
    '-PresetPath', $preset,
    '-SummaryPath', $summary,
    '-TimeoutSeconds', '120'
)) {
    [void]$startInfo.ArgumentList.Add($argument)
}
$process = [Diagnostics.Process]::Start($startInfo)
$stdoutTask = $process.StandardOutput.ReadToEndAsync()
$stderrTask = $process.StandardError.ReadToEndAsync()
$finished = $process.WaitForExit($TimeoutSeconds * 1000)
if (-not $finished) {
    $process.Kill($true)
    throw "无人值守宿主验证超时；只结束验证包装进程 $($process.Id)"
}
$stdout = $stdoutTask.Result.Trim()
$stderr = $stderrTask.Result.Trim()
$finishedAt = [DateTimeOffset]::UtcNow
$after = @(Get-Process UnrealEditor, UnrealEditor-Cmd -ErrorAction SilentlyContinue | Select-Object -ExpandProperty Id)
$newUnrealPids = @($after | Where-Object { $_ -notin $existing })
$residualOwnedPids = @(
    Get-CimInstance Win32_Process -Filter "Name='UnrealEditor.exe' OR Name='UnrealEditor-Cmd.exe'" |
        Where-Object { $_.CommandLine -and $_.CommandLine.Contains($runtime) } |
        Select-Object -ExpandProperty ProcessId
)

if (-not (Test-Path -LiteralPath $summary)) {
    throw "无人值守摘要未生成；exit=$($process.ExitCode) stdout=$stdout stderr=$stderr"
}
$summaryData = Get-Content -LiteralPath $summary -Raw | ConvertFrom-Json
$report = [IO.Path]::GetFullPath([string]$summaryData.report_path)
if (-not (Test-Path -LiteralPath $report)) { throw "无人值守 Report 不存在：$report" }
$reportData = Get-Content -LiteralPath $report -Raw | ConvertFrom-Json

$evidenceRoot = Join-Path $repoRoot "artifacts\host-validation\m10"
New-Item -ItemType Directory -Path $evidenceRoot -Force | Out-Null
$summaryEvidence = Join-Path $evidenceRoot "unattended-summary.json"
$reportEvidence = Join-Path $evidenceRoot "unattended-report.json"
Copy-Item -LiteralPath $summary -Destination $summaryEvidence -Force
Copy-Item -LiteralPath $report -Destination $reportEvidence -Force
$log = Join-Path $runtime "Saved\Logs\UnrealAssetBatchAuditorHost.log"
$logEvidence = Join-Path $evidenceRoot "unattended-host-log.txt"
if (Test-Path -LiteralPath $log) {
    @(Select-String -LiteralPath $log -Pattern @(
        'engineversion=', 'Command Line:', 'UABA_UNATTENDED_RESULT', 'Engine exit requested'
    ) | ForEach-Object { $_.Line }) | Set-Content -LiteralPath $logEvidence -Encoding utf8
}

$passed = (
    $process.ExitCode -eq 0 -and
    $summaryData.schema_version -eq 'unreal-asset-audit-run@1.0.0' -and
    $summaryData.status -eq 'passed' -and
    $summaryData.exit_code -eq 0 -and
    $summaryData.asset_count -ge 4 -and
    $summaryData.collection_failure_count -eq 0 -and
    $reportData.real_unreal_validation -eq $true -and
    $residualOwnedPids.Count -eq 0
)
$manifest = [ordered]@{
    schema_version = "unreal-unattended-host-evidence@1.0.0"
    created_at = $finishedAt.ToString('o')
    passed = $passed
    engine = $reportData.host_engine_version
    plugin_build = $BuildLabel
    execution = "independent hidden UnrealEditor-Cmd through stable-exit wrapper"
    wrapper_pid = $process.Id
    wrapper_exit_code = $process.ExitCode
    stdout = $stdout
    stderr = $stderr
    started_at = $startedAt.ToString('o')
    finished_at = $finishedAt.ToString('o')
    duration_seconds = [Math]::Round(($finishedAt - $startedAt).TotalSeconds, 3)
    existing_unreal_pids_before = $existing
    existing_unreal_pids_after = $after
    preexisting_processes_managed_by_test = $false
    concurrently_observed_new_unreal_pids = $newUnrealPids
    residual_owned_unreal_pids = $residualOwnedPids
    preset_path = "Resources/ProjectPresets/engine-basic-shapes-ci.v1.json"
    summary_path = "artifacts/host-validation/m10/unattended-summary.json"
    summary_sha256 = (Get-FileHash -LiteralPath $summaryEvidence -Algorithm SHA256).Hash
    report_path = "artifacts/host-validation/m10/unattended-report.json"
    report_sha256 = (Get-FileHash -LiteralPath $reportEvidence -Algorithm SHA256).Hash
    log_path = if (Test-Path -LiteralPath $logEvidence) { "artifacts/host-validation/m10/unattended-host-log.txt" } else { $null }
    evidence_ceiling = "Explicit Engine BasicShapes scope on UE 5.8.1; not external CI integration, cross-version compatibility, or production-scale performance."
}
$manifestPath = Join-Path $evidenceRoot "unattended-host-$BuildLabel.json"
$manifest | ConvertTo-Json -Depth 6 | Set-Content -LiteralPath $manifestPath -Encoding utf8
if (-not $passed) { throw "无人值守宿主验证失败；检查 $manifestPath" }
Write-Output "无人值守宿主验证通过：$manifestPath"
