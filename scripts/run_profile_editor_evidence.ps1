param(
    [string]$EngineRoot = "C:\Program Files\Epic Games\UE_5.8",
    [string]$BuildLabel = "UE_5.8-v0.11.0-dev2",
    [int]$TimeoutSeconds = 120
)

$ErrorActionPreference = "Stop"
$repoRoot = Split-Path -Parent $PSScriptRoot
$editor = Join-Path $EngineRoot "Engine\Binaries\Win64\UnrealEditor-Cmd.exe"
$build = Join-Path $repoRoot "artifacts\host-build\$BuildLabel"
$output = Join-Path $repoRoot "docs\images\workflow\v0.11-profile-standards"
$evidenceRoot = Join-Path $repoRoot "artifacts\host-validation\m17"
foreach ($required in @($editor, (Join-Path $build "UnrealAssetBatchAuditor.uplugin"))) {
    if (-not (Test-Path -LiteralPath $required)) { throw "Required host input is missing: $required" }
}

$runId = Get-Date -Format "yyyyMMdd-HHmmss"
$runtime = Join-Path $repoRoot "artifacts\host-runtime\profile-editor-$runId"
$plugins = Join-Path $runtime "Plugins"
New-Item -ItemType Directory -Path $plugins -Force | Out-Null
Copy-Item -LiteralPath (Join-Path $repoRoot "tests\host\UnrealAssetBatchAuditorHost.uproject") -Destination $runtime
Copy-Item -LiteralPath $build -Destination (Join-Path $plugins "UnrealAssetBatchAuditor") -Recurse
New-Item -ItemType Directory -Path $output -Force | Out-Null
New-Item -ItemType Directory -Path $evidenceRoot -Force | Out-Null

$existing = @(Get-Process UnrealEditor, UnrealEditor-Cmd -ErrorAction SilentlyContinue | Select-Object -ExpandProperty Id)
$env:UABA_PROFILE_EDITOR_EVIDENCE_OUTPUT = $output
$project = Join-Path $runtime "UnrealAssetBatchAuditorHost.uproject"
$arguments = @(
    $project,
    '-ExecCmds="Automation RunTests UnrealAssetBatchAuditor.ProfileStandardEditorEvidence"',
    '-TestExit="Automation Test Queue Empty"',
    '-unattended', '-nop4', '-nosplash', '-RenderOffscreen'
)
$startedAt = [DateTimeOffset]::UtcNow
$process = Start-Process -FilePath $editor -ArgumentList $arguments -PassThru -WindowStyle Hidden
$deadline = [DateTimeOffset]::UtcNow.AddSeconds($TimeoutSeconds)
while (-not $process.HasExited -and [DateTimeOffset]::UtcNow -lt $deadline) {
    Start-Sleep -Milliseconds 250
}
$timedOut = -not $process.HasExited
if ($timedOut) { Stop-Process -Id $process.Id -Force -ErrorAction SilentlyContinue }
$finishedAt = [DateTimeOffset]::UtcNow
$logPath = Join-Path $runtime "Saved\Logs\UnrealAssetBatchAuditorHost.log"
$log = if (Test-Path -LiteralPath $logPath) { Get-Content -LiteralPath $logPath -Raw } else { "" }
$automationPassed = $log -match 'Test Completed\. Result=\{Success\} Name=\{ProfileStandardEditorEvidence\}'
$after = @(Get-Process UnrealEditor, UnrealEditor-Cmd -ErrorAction SilentlyContinue | Select-Object -ExpandProperty Id)
$screenshots = @(Get-ChildItem -LiteralPath $output -Filter '*.png' | Sort-Object Name | ForEach-Object {
    [ordered]@{
        path = [IO.Path]::GetRelativePath($repoRoot, $_.FullName).Replace('\', '/')
        bytes = $_.Length
        sha256 = (Get-FileHash -LiteralPath $_.FullName -Algorithm SHA256).Hash
    }
})
$reportSource = Join-Path $runtime "Saved\UnrealAssetBatchAuditor\ProfileEditorEvidence\Reports"
$reportEvidenceRoot = Join-Path $evidenceRoot "profile-editor-reports-$BuildLabel"
$resolvedReportEvidenceRoot = [IO.Path]::GetFullPath($reportEvidenceRoot)
$resolvedEvidenceRoot = [IO.Path]::GetFullPath($evidenceRoot)
if (-not $resolvedReportEvidenceRoot.StartsWith(
        $resolvedEvidenceRoot + [IO.Path]::DirectorySeparatorChar,
        [StringComparison]::OrdinalIgnoreCase)) {
    throw "Report evidence target escaped the M17 evidence directory"
}
if (Test-Path -LiteralPath $reportEvidenceRoot) { Remove-Item -LiteralPath $reportEvidenceRoot -Recurse -Force }
if (Test-Path -LiteralPath $reportSource) {
    Copy-Item -LiteralPath $reportSource -Destination $reportEvidenceRoot -Recurse
}
$reports = @(Get-ChildItem -LiteralPath $reportEvidenceRoot -Filter '*.json' -ErrorAction SilentlyContinue | Sort-Object Name | ForEach-Object {
    [ordered]@{
        path = [IO.Path]::GetRelativePath($repoRoot, $_.FullName).Replace('\', '/')
        bytes = $_.Length
        sha256 = (Get-FileHash -LiteralPath $_.FullName -Algorithm SHA256).Hash
    }
})
$result = [ordered]@{
    schema_version = "unreal-profile-editor-host-evidence@1.0.0"
    created_at = $finishedAt.ToString('o')
    engine = "UE 5.8.1"
    plugin_build = $BuildLabel
    execution = "independent hidden UnrealEditor-Cmd -RenderOffscreen"
    test_pid = $process.Id
    existing_unreal_pids_before = $existing
    existing_unreal_pids_after = @($after | Where-Object { $_ -ne $process.Id })
    preexisting_processes_managed_by_test = $false
    started_at = $startedAt.ToString('o')
    finished_at = $finishedAt.ToString('o')
    duration_seconds = [Math]::Round(($finishedAt - $startedAt).TotalSeconds, 3)
    timed_out = $timedOut
    exit_code = $process.ExitCode
    automation_passed = $automationPassed
    screenshot_count = $screenshots.Count
    screenshots = $screenshots
    report_count = $reports.Count
    reports = $reports
    validates = @(
        "native Slate model and texture Profile editor construction",
        "field-localized invalid state",
        "structured difference preview",
        "project-owned atomic save"
    )
    claims_manual_mouse_interaction = $false
}
$evidencePath = Join-Path $evidenceRoot "profile-editor-$BuildLabel.json"
$result | ConvertTo-Json -Depth 8 | Set-Content -LiteralPath $evidencePath -Encoding utf8
if ($timedOut -or $process.ExitCode -ne 0 -or -not $automationPassed -or
    $screenshots.Count -ne 6 -or $reports.Count -ne 2) {
    throw "Profile editor host evidence failed; inspect $evidencePath and $logPath"
}
Write-Output "Profile editor evidence passed: $evidencePath"
