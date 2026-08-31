param(
    [string]$EngineRoot = "C:\Program Files\Epic Games\UE_5.8",
    [string]$BuildLabel = "UE_5.8-v0.10.0-dev4",
    [int]$TimeoutSeconds = 180
)

$ErrorActionPreference = "Stop"
$repoRoot = Split-Path -Parent $PSScriptRoot
$editorCmd = Join-Path $EngineRoot "Engine\Binaries\Win64\UnrealEditor-Cmd.exe"
$project = Join-Path $repoRoot "Demo\UABADemo.uproject"
$generator = Join-Path $repoRoot "scripts\host\generate_texture_evidence.py"
$report = Join-Path $repoRoot "artifacts\demo\demo-texture-mobile-strict-v1-report.json"
$logPath = Join-Path $repoRoot "artifacts\host-validation\m15\texture-collector-$BuildLabel-log.txt"
$resultPath = Join-Path $repoRoot "artifacts\host-validation\m15\texture-collector-$BuildLabel.json"
foreach ($required in @($editorCmd, $project, $generator)) {
    if (-not (Test-Path -LiteralPath $required)) { throw "Missing texture host input: $required" }
}
New-Item -ItemType Directory -Path (Split-Path -Parent $logPath) -Force | Out-Null
$existing = @(Get-Process UnrealEditor, UnrealEditor-Cmd -ErrorAction SilentlyContinue | Select-Object -ExpandProperty Id)
$env:UABA_TEXTURE_REPORT = $report
$startedAt = [DateTimeOffset]::UtcNow
$arguments = @(
    $project,
    "-ExecutePythonScript=$generator",
    "-abslog=$logPath",
    "-unattended", "-nop4", "-nosplash"
)
$process = Start-Process -FilePath $editorCmd -ArgumentList $arguments -PassThru -WindowStyle Hidden
$deadline = [DateTimeOffset]::UtcNow.AddSeconds($TimeoutSeconds)
while (-not $process.HasExited -and [DateTimeOffset]::UtcNow -lt $deadline) {
    Start-Sleep -Milliseconds 250
}
$timedOut = -not $process.HasExited
if ($timedOut) { Stop-Process -Id $process.Id -Force -ErrorAction SilentlyContinue }
$process.WaitForExit()
$finishedAt = [DateTimeOffset]::UtcNow
Remove-Item Env:\UABA_TEXTURE_REPORT -ErrorAction SilentlyContinue
$after = @(Get-Process UnrealEditor, UnrealEditor-Cmd -ErrorAction SilentlyContinue |
    Where-Object { $_.Id -ne $process.Id } | Select-Object -ExpandProperty Id)
$existingSurvived = @($existing | Where-Object { $_ -notin $after }).Count -eq 0
$log = if (Test-Path -LiteralPath $logPath) { Get-Content -LiteralPath $logPath -Raw } else { "" }
$reportData = if (Test-Path -LiteralPath $report) {
    Get-Content -LiteralPath $report -Raw | ConvertFrom-Json
} else { $null }
$passed = -not $timedOut -and $process.ExitCode -eq 0 -and
    $log -match "UABA_TEXTURE_EVIDENCE_OK" -and $null -ne $reportData -and
    $reportData.real_unreal_validation -eq $true -and $reportData.asset_type -eq "texture2d" -and
    $reportData.asset_count -eq 3
$result = [ordered]@{
    schema_version = "unreal-texture-host-validation@1.0.0"
    created_at = $finishedAt.ToString("o")
    engine = if ($reportData) { $reportData.host_engine_version } else { $null }
    plugin_build = $BuildLabel
    execution = "independent hidden UnrealEditor-Cmd -ExecutePythonScript"
    test_pid = $process.Id
    existing_unreal_pids_before = $existing
    existing_unreal_pids_after = $after
    existing_processes_survived = $existingSurvived
    preexisting_processes_managed_by_test = $false
    started_at = $startedAt.ToString("o")
    finished_at = $finishedAt.ToString("o")
    duration_seconds = [Math]::Round(($finishedAt - $startedAt).TotalSeconds, 3)
    timed_out = $timedOut
    exit_code = $process.ExitCode
    process_exited = $process.HasExited
    passed = $passed
    asset_type = if ($reportData) { $reportData.asset_type } else { $null }
    asset_count = if ($reportData) { $reportData.asset_count } else { 0 }
    issue_count = if ($reportData) { $reportData.issue_count } else { 0 }
    collection_failure_count = if ($reportData) { $reportData.collection_failure_count } else { 0 }
    report_path = [IO.Path]::GetRelativePath($repoRoot, $report).Replace("\", "/")
    report_sha256 = if (Test-Path -LiteralPath $report) { (Get-FileHash -LiteralPath $report -Algorithm SHA256).Hash } else { $null }
    claims_runtime_performance = $false
    claims_asset_mutation_by_plugin = $false
}
$result | ConvertTo-Json -Depth 6 | Set-Content -LiteralPath $resultPath -Encoding utf8
if (-not $passed) { throw "Texture host validation failed; inspect $resultPath and $logPath" }
Write-Output "Texture host validation passed: $resultPath"
