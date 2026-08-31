param(
    [string]$EngineRoot = "C:\Program Files\Epic Games\UE_5.8",
    [string]$BuildLabel = "UE_5.8-v0.11.0-dev3",
    [int]$TimeoutSeconds = 180
)

$ErrorActionPreference = "Stop"
$repoRoot = Split-Path -Parent $PSScriptRoot
$editor = Join-Path $EngineRoot "Engine\Binaries\Win64\UnrealEditor-Cmd.exe"
$build = Join-Path $repoRoot "artifacts\host-build\$BuildLabel"
$generator = Join-Path $repoRoot "scripts\host\generate_material_evidence.py"
$report = Join-Path $repoRoot "artifacts\demo\demo-material-desktop-balanced-v1-report.json"
$manifest = Join-Path $repoRoot "artifacts\demo\demo-material-asset-manifest.json"
$evidenceRoot = Join-Path $repoRoot "artifacts\host-validation\m18"
foreach ($required in @($editor, (Join-Path $build "UnrealAssetBatchAuditor.uplugin"), $generator)) {
    if (-not (Test-Path -LiteralPath $required)) { throw "Missing material host input: $required" }
}

$runId = Get-Date -Format "yyyyMMdd-HHmmss"
$runtime = Join-Path $repoRoot "artifacts\host-runtime\material-$runId"
$plugins = Join-Path $runtime "Plugins"
New-Item -ItemType Directory -Path $plugins -Force | Out-Null
Copy-Item -LiteralPath (Join-Path $repoRoot "tests\host\UnrealAssetBatchAuditorHost.uproject") -Destination $runtime
Copy-Item -LiteralPath $build -Destination (Join-Path $plugins "UnrealAssetBatchAuditor") -Recurse
New-Item -ItemType Directory -Path $evidenceRoot -Force | Out-Null

$existing = @(Get-Process UnrealEditor, UnrealEditor-Cmd -ErrorAction SilentlyContinue | Select-Object -ExpandProperty Id)
$env:UABA_MATERIAL_REPORT = $report
$project = Join-Path $runtime "UnrealAssetBatchAuditorHost.uproject"
$logPath = Join-Path $runtime "Saved\Logs\UnrealAssetBatchAuditorHost.log"
$arguments = @($project, "-ExecutePythonScript=$generator", "-abslog=$logPath", "-unattended", "-nop4", "-nosplash")
$startedAt = [DateTimeOffset]::UtcNow
$process = Start-Process -FilePath $editor -ArgumentList $arguments -PassThru -WindowStyle Hidden
$deadline = [DateTimeOffset]::UtcNow.AddSeconds($TimeoutSeconds)
while (-not $process.HasExited -and [DateTimeOffset]::UtcNow -lt $deadline) { Start-Sleep -Milliseconds 250 }
$timedOut = -not $process.HasExited
if ($timedOut) { Stop-Process -Id $process.Id -Force -ErrorAction SilentlyContinue }
$process.WaitForExit()
Start-Sleep -Milliseconds 750
$finishedAt = [DateTimeOffset]::UtcNow
Remove-Item Env:\UABA_MATERIAL_REPORT -ErrorAction SilentlyContinue
$after = @(Get-Process UnrealEditor, UnrealEditor-Cmd -ErrorAction SilentlyContinue |
    Where-Object { $_.Id -ne $process.Id } | Select-Object -ExpandProperty Id)
$existingSurvived = @($existing | Where-Object { $_ -notin $after }).Count -eq 0
$log = if (Test-Path -LiteralPath $logPath) { Get-Content -LiteralPath $logPath -Raw } else { "" }
$reportData = if (Test-Path -LiteralPath $report) { Get-Content -LiteralPath $report -Raw | ConvertFrom-Json } else { $null }
$passed = -not $timedOut -and $process.ExitCode -eq 0 -and
    $log -match "UABA_MATERIAL_EVIDENCE_OK" -and $null -ne $reportData -and
    $reportData.real_unreal_validation -eq $true -and
    $reportData.asset_type -eq "material_interface" -and $reportData.asset_count -eq 9 -and
    $reportData.collection_failure_count -eq 0

$result = [ordered]@{
    schema_version = "unreal-material-host-validation@1.0.0"
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
    manifest_path = [IO.Path]::GetRelativePath($repoRoot, $manifest).Replace("\", "/")
    manifest_sha256 = if (Test-Path -LiteralPath $manifest) { (Get-FileHash -LiteralPath $manifest -Algorithm SHA256).Hash } else { $null }
    generated_content_path = [IO.Path]::GetRelativePath($repoRoot, (Join-Path $runtime "Content\UABAMaterialDemo")).Replace("\", "/")
    claims_shader_or_gpu_performance = $false
    claims_asset_mutation_by_plugin = $false
}
$evidencePath = Join-Path $evidenceRoot "material-collector-$BuildLabel.json"
$result | ConvertTo-Json -Depth 6 | Set-Content -LiteralPath $evidencePath -Encoding utf8
if (-not $passed) { throw "Material host validation failed; inspect $evidencePath and $logPath" }
Write-Output "Material host validation passed: $evidencePath"
Write-Output "Material content path: $(Join-Path $runtime 'Content\UABAMaterialDemo')"
