param(
    [string]$EngineRoot = "C:\Program Files\Epic Games\UE_5.8",
    [string]$BuildLabel = "UE_5.8.1-v0.6.0-dev1",
    [string]$ReportPath = "",
    [string]$OutputDirectory = "",
    [int]$ExpectedAssets = 26,
    [int]$ExpectedIssues = 47,
    [int]$TimeoutSeconds = 120
)

$ErrorActionPreference = "Stop"
$repoRoot = Split-Path -Parent $PSScriptRoot
$editorCmd = Join-Path $EngineRoot "Engine\Binaries\Win64\UnrealEditor-Cmd.exe"
$build = Join-Path $repoRoot "artifacts\host-build\$BuildLabel"
if (-not $ReportPath) {
    $ReportPath = Join-Path $repoRoot "artifacts\demo\demo-desktop-balanced-v2-report.json"
}
if (-not $OutputDirectory) {
    $OutputDirectory = Join-Path $repoRoot "docs\images\workflow\v0.6"
}
foreach ($required in @($editorCmd, (Join-Path $build "UnrealAssetBatchAuditor.uplugin"), $ReportPath)) {
    if (-not (Test-Path -LiteralPath $required)) {
        throw "Required panel evidence input does not exist: $required"
    }
}

$runId = Get-Date -Format "yyyyMMdd-HHmmss"
$runtime = Join-Path $repoRoot "artifacts\host-runtime\panel-$runId"
$plugins = Join-Path $runtime "Plugins"
New-Item -ItemType Directory -Path $plugins -Force | Out-Null
Copy-Item -LiteralPath (Join-Path $repoRoot "tests\host\UnrealAssetBatchAuditorHost.uproject") -Destination $runtime
Copy-Item -LiteralPath $build -Destination (Join-Path $plugins "UnrealAssetBatchAuditor") -Recurse
New-Item -ItemType Directory -Path $OutputDirectory -Force | Out-Null

$existing = @(Get-Process UnrealEditor, UnrealEditor-Cmd -ErrorAction SilentlyContinue | Select-Object -ExpandProperty Id)
$env:UABA_PANEL_EVIDENCE_REPORT = $ReportPath
$env:UABA_PANEL_EVIDENCE_OUTPUT = $OutputDirectory
$env:UABA_PANEL_EVIDENCE_MODE = "v2"
$env:UABA_PANEL_EVIDENCE_EXPECTED_ASSETS = [string]$ExpectedAssets
$env:UABA_PANEL_EVIDENCE_EXPECTED_ISSUES = [string]$ExpectedIssues

$project = Join-Path $runtime "UnrealAssetBatchAuditorHost.uproject"
$arguments = @(
    $project,
    '-ExecCmds="Automation RunTests UnrealAssetBatchAuditor.PanelEvidence"',
    '-TestExit="Automation Test Queue Empty"',
    '-unattended', '-nop4', '-nosplash', '-RenderOffscreen'
)
$startedAt = [DateTimeOffset]::UtcNow
$process = Start-Process -FilePath $editorCmd -ArgumentList $arguments -PassThru -WindowStyle Hidden
$ownedPids = [Collections.Generic.HashSet[int]]::new()
[void]$ownedPids.Add($process.Id)
$deadline = [DateTimeOffset]::UtcNow.AddSeconds($TimeoutSeconds)
while (-not $process.HasExited -and [DateTimeOffset]::UtcNow -lt $deadline) {
    foreach ($id in @(Get-Process UnrealEditor, UnrealEditor-Cmd -ErrorAction SilentlyContinue | Select-Object -ExpandProperty Id)) {
        if ($id -notin $existing) { [void]$ownedPids.Add($id) }
    }
    Start-Sleep -Milliseconds 250
}
$timedOut = -not $process.HasExited
if ($timedOut) {
    foreach ($id in $ownedPids) {
        Stop-Process -Id $id -Force -ErrorAction SilentlyContinue
    }
} else {
    $cleanupDeadline = [DateTimeOffset]::UtcNow.AddSeconds(10)
    do {
        $newUnreal = @(
            Get-Process UnrealEditor, UnrealEditor-Cmd -ErrorAction SilentlyContinue |
                Where-Object { $_.Id -notin $existing } |
                Select-Object -ExpandProperty Id
        )
        foreach ($id in $newUnreal) { [void]$ownedPids.Add($id) }
        if ($newUnreal.Count -gt 0) { Start-Sleep -Milliseconds 250 }
    } while ($newUnreal.Count -gt 0 -and [DateTimeOffset]::UtcNow -lt $cleanupDeadline)
}
$finishedAt = [DateTimeOffset]::UtcNow
$logPath = Join-Path $runtime "Saved\Logs\UnrealAssetBatchAuditorHost.log"
$log = if (Test-Path -LiteralPath $logPath) { Get-Content -LiteralPath $logPath -Raw } else { "" }
$automationPassed = $log -match 'Test Completed\. Result=\{Success\} Name=\{PanelEvidence\}'
$logEvidencePath = Join-Path $repoRoot "artifacts\host-validation\m5\panel-lifecycle-v0.6.0-dev1-log.txt"
$logPatterns = @(
    'engineversion=', 'Command Line:', 'Found 1 automation', 'Test Started',
    'Test Completed', 'Automation Test Queue Empty', 'Engine exit requested'
)
@(Select-String -LiteralPath $logPath -Pattern $logPatterns | ForEach-Object { $_.Line }) |
    Set-Content -LiteralPath $logEvidencePath -Encoding utf8
$after = @(Get-Process UnrealEditor, UnrealEditor-Cmd -ErrorAction SilentlyContinue | Select-Object -ExpandProperty Id)
$existingSurvived = @($existing | Where-Object { $_ -notin $after }).Count -eq 0
$screenshots = @(Get-ChildItem -LiteralPath $OutputDirectory -Filter '*.png' | Sort-Object Name | ForEach-Object {
    [ordered]@{
        path = [IO.Path]::GetRelativePath($repoRoot, $_.FullName).Replace('\', '/')
        bytes = $_.Length
        sha256 = (Get-FileHash -LiteralPath $_.FullName -Algorithm SHA256).Hash
    }
})
$result = [ordered]@{
    schema_version = "unreal-panel-lifecycle@1.0.0"
    created_at = $finishedAt.ToString('o')
    engine = "UE 5.8.1"
    plugin_build = $BuildLabel
    execution = "independent hidden UnrealEditor-Cmd -RenderOffscreen"
    test_pid = $process.Id
    created_unreal_pids = @($ownedPids | Sort-Object)
    existing_unreal_pids_before = $existing
    existing_unreal_pids_after = $after
    existing_processes_survived = $existingSurvived
    started_at = $startedAt.ToString('o')
    finished_at = $finishedAt.ToString('o')
    duration_seconds = [Math]::Round(($finishedAt - $startedAt).TotalSeconds, 3)
    timed_out = $timedOut
    exit_code = $process.ExitCode
    process_exited = $process.HasExited
    automation_test = "UnrealAssetBatchAuditor.PanelEvidence"
    automation_passed = $automationPassed
    report_path = [IO.Path]::GetRelativePath($repoRoot, $ReportPath).Replace('\', '/')
    report_sha256 = (Get-FileHash -LiteralPath $ReportPath -Algorithm SHA256).Hash
    log_path = [IO.Path]::GetRelativePath($repoRoot, $logPath).Replace('\', '/')
    committed_log_excerpt = [IO.Path]::GetRelativePath($repoRoot, $logEvidencePath).Replace('\', '/')
    committed_log_excerpt_sha256 = (Get-FileHash -LiteralPath $logEvidencePath -Algorithm SHA256).Hash
    screenshot_count = $screenshots.Count
    screenshots = $screenshots
    claims_user_interaction = $false
    claims_visible_editor_review = $false
}
$evidencePath = Join-Path $repoRoot "artifacts\host-validation\m5\panel-lifecycle-v0.6.0-dev1.json"
$result | ConvertTo-Json -Depth 8 | Set-Content -LiteralPath $evidencePath -Encoding utf8

if ($timedOut -or $process.ExitCode -ne 0 -or -not $automationPassed -or
    -not $existingSurvived -or $screenshots.Count -ne 10) {
    throw "Panel evidence failed; inspect $evidencePath and $logPath"
}
Write-Output "Panel evidence passed: $evidencePath"
