param(
    [Parameter(Mandatory = $true)]
    [string]$EngineRoot,
    [Parameter(Mandatory = $true)]
    [string]$ProjectPath,
    [Parameter(Mandatory = $true)]
    [string]$PresetPath,
    [string]$SummaryPath = "",
    [int]$TimeoutSeconds = 180
)

$ErrorActionPreference = "Stop"
[Console]::OutputEncoding = [Text.UTF8Encoding]::new($false)
$editorCmd = Join-Path $EngineRoot "Engine\Binaries\Win64\UnrealEditor-Cmd.exe"
$entryScript = Join-Path (Split-Path -Parent $PSScriptRoot) "Content\Python\run_unattended_audit.py"
foreach ($required in @($editorCmd, $ProjectPath, $PresetPath, $entryScript)) {
    if (-not (Test-Path -LiteralPath $required)) {
        throw "无人值守审计所需路径不存在：$required"
    }
}
$projectInput = Get-Item -LiteralPath $ProjectPath
if ($projectInput.PSIsContainer) {
    $candidates = @(Get-ChildItem -LiteralPath $projectInput.FullName -Filter '*.uproject' -File)
    if ($candidates.Count -ne 1) {
        throw "项目目录必须恰好包含一个 .uproject；当前找到 $($candidates.Count) 个"
    }
    $projectFile = $candidates[0]
} elseif ($projectInput.Extension -eq '.uproject') {
    $projectFile = $projectInput
} else {
    throw "ProjectPath 必须指向 .uproject 或只包含一个 .uproject 的目录"
}
$projectRoot = $projectFile.Directory.FullName
if (-not $SummaryPath) {
    $SummaryPath = Join-Path $projectRoot "Saved\UnrealAssetBatchAuditor\CI\latest-run-summary.json"
}
$summaryFull = [IO.Path]::GetFullPath($SummaryPath)
New-Item -ItemType Directory -Path (Split-Path -Parent $summaryFull) -Force | Out-Null
if (Test-Path -LiteralPath $summaryFull) {
    Remove-Item -LiteralPath $summaryFull -Force
}

$env:UABA_UNATTENDED_PRESET = [IO.Path]::GetFullPath($PresetPath)
$env:UABA_UNATTENDED_SUMMARY = $summaryFull
$arguments = @(
    $projectFile.FullName,
    "-ExecutePythonScript=$entryScript",
    '-unattended', '-nop4', '-nosplash', '-RenderOffscreen'
)
$process = Start-Process -FilePath $editorCmd -ArgumentList $arguments -PassThru -WindowStyle Hidden
$deadline = [DateTimeOffset]::UtcNow.AddSeconds($TimeoutSeconds)
while (-not $process.HasExited -and [DateTimeOffset]::UtcNow -lt $deadline) {
    Start-Sleep -Milliseconds 250
}
if (-not $process.HasExited) {
    Stop-Process -Id $process.Id -Force -ErrorAction SilentlyContinue
    Remove-Item Env:\UABA_UNATTENDED_PRESET -ErrorAction SilentlyContinue
    Remove-Item Env:\UABA_UNATTENDED_SUMMARY -ErrorAction SilentlyContinue
    Write-Output "无人值守审计超时；只结束本轮创建的 PID $($process.Id)"
    exit 40
}
Remove-Item Env:\UABA_UNATTENDED_PRESET -ErrorAction SilentlyContinue
Remove-Item Env:\UABA_UNATTENDED_SUMMARY -ErrorAction SilentlyContinue
if (-not (Test-Path -LiteralPath $summaryFull)) {
    Write-Output "Unreal 进程未生成运行摘要；宿主退出码为 $($process.ExitCode)"
    exit 40
}
$summary = Get-Content -LiteralPath $summaryFull -Raw | ConvertFrom-Json
Write-Output ("UABA {0}: {1}；资产 {2}，问题 {3}，采集失败 {4}；摘要 {5}" -f `
    $summary.status, $summary.message, $summary.asset_count, $summary.issue_count, `
    $summary.collection_failure_count, $summaryFull)
exit [int]$summary.exit_code
