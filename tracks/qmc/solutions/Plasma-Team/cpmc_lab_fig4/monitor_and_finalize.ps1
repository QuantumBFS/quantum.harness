param(
    [Parameter(Mandatory = $true)]
    [string]$RunDir,
    [Parameter(Mandatory = $true)]
    [string]$RepoRoot,
    [string]$PythonExe = 'C:\Python314\python.exe',
    [int]$PollSeconds = 30,
    [double]$MaxWaitHours = 30,
    [switch]$OpenReport
)

$ErrorActionPreference = 'Stop'
Set-StrictMode -Version Latest

$RunDir = [System.IO.Path]::GetFullPath($RunDir)
$RepoRoot = [System.IO.Path]::GetFullPath($RepoRoot)
$points = @('u0', 'u1', 'u2', 'u3', 'u4', 'u5', 'u6', 'u7', 'u8')
$monitorLog = Join-Path $RunDir 'logs\monitor-fig4abc.log'
Start-Transcript -LiteralPath $monitorLog -Append | Out-Null

Write-Output "MONITOR_START=$(Get-Date -Format o)"
Write-Output "RUN_DIR=$RunDir"
$deadline = (Get-Date).AddHours($MaxWaitHours)

while ($true) {
    foreach ($point in $points) {
        $failedPath = Join-Path $RunDir "raw\$point\FAILED.json"
        if (Test-Path -LiteralPath $failedPath) {
            Write-Output "POINT_FAILED=$point"
            Get-Content -Raw -LiteralPath $failedPath
            Stop-Transcript | Out-Null
            exit 2
        }
    }

    $pending = @($points | Where-Object {
        -not (Test-Path -LiteralPath (Join-Path $RunDir "raw\$_\DONE.json"))
    })
    if ($pending.Count -eq 0) {
        break
    }
    if ((Get-Date) -ge $deadline) {
        Stop-Transcript | Out-Null
        throw "Timed out after $MaxWaitHours hours waiting for: $($pending -join ',')"
    }

    Write-Output "PENDING=$($pending -join ',') AT=$(Get-Date -Format o)"
    Start-Sleep -Seconds $PollSeconds
}

$finalizer = Join-Path $RepoRoot 'tracks\qmc\solutions\Plasma-Team\cpmc_lab_fig4\finalize_cpmc_fig4abc.py'
$buildReport = Join-Path $RepoRoot 'skills\reproduce-paper\build_report.py'
$renderReport = Join-Path $RepoRoot 'skills\report\render_report.py'

& $PythonExe -X utf8 $finalizer $RunDir
if ($LASTEXITCODE -ne 0) { throw "Finalizer failed with exit code $LASTEXITCODE" }
& $PythonExe -X utf8 $buildReport $RunDir
if ($LASTEXITCODE -ne 0) { throw "Report builder failed with exit code $LASTEXITCODE" }
& $PythonExe -X utf8 $renderReport $RunDir
if ($LASTEXITCODE -ne 0) { throw "Report renderer failed with exit code $LASTEXITCODE" }

$completedPath = Join-Path $RunDir 'FINALIZED.txt'
"FINALIZED=$(Get-Date -Format o)" | Set-Content -LiteralPath $completedPath -Encoding utf8
Write-Output "FINALIZED=$completedPath"

$reportPath = Join-Path $RunDir 'report.html'
if ($OpenReport -and (Test-Path -LiteralPath $reportPath)) {
    Start-Process -FilePath $reportPath
}
Stop-Transcript | Out-Null
