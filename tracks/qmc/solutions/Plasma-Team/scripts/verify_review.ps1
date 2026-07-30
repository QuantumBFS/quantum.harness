$ErrorActionPreference = 'Stop'
Set-StrictMode -Version Latest
$root = Split-Path -Parent $PSScriptRoot
$python = Join-Path $root '.venv\Scripts\python.exe'
$env:PYTHONPATH = Join-Path $root 'src'
$score = 0

if (-not (Test-Path -LiteralPath $python)) {
    throw "Python environment is missing: $python"
}

foreach ($testFile in @(
    'tests\test_cli.py',
    'tests\test_provenance.py',
    'tests\test_independent_oracle.py',
    'tests\test_nqs_chirality.py'
)) {
    & $python -m pytest -q (Join-Path $root $testFile) *> $null
    if ($LASTEXITCODE -eq 0) {
        $score += 1
    }
}

& powershell -NoProfile -ExecutionPolicy Bypass -File (Join-Path $root 'scripts\verify.ps1') *> $null
if ($LASTEXITCODE -eq 0) {
    $score += 1
}

$emptyResults = Join-Path ([System.IO.Path]::GetTempPath()) (
    'graviton-empty-results-' + [System.Guid]::NewGuid().ToString('N')
)
[void](New-Item -ItemType Directory -Path $emptyResults)
try {
    $savedErrorPreference = $ErrorActionPreference
    $ErrorActionPreference = 'SilentlyContinue'
    & powershell -NoProfile -ExecutionPolicy Bypass `
        -File (Join-Path $root 'scripts\verify_research.ps1') `
        -ResultsDirectory $emptyResults *> $null
    $expectedFailureExit = $LASTEXITCODE
    $ErrorActionPreference = $savedErrorPreference
    if ($expectedFailureExit -ne 0) {
        $score += 1
    }
} finally {
    $resolvedTemp = [System.IO.Path]::GetFullPath($emptyResults)
    $systemTemp = [System.IO.Path]::GetFullPath([System.IO.Path]::GetTempPath())
    if ($resolvedTemp.StartsWith($systemTemp, [System.StringComparison]::OrdinalIgnoreCase)) {
        Remove-Item -LiteralPath $resolvedTemp -Recurse -Force
    }
}

$documents = @(
    (Join-Path $root 'README.md'),
    (Join-Path $root 'REPORT.md'),
    (Join-Path $root 'DEV_DOCUMENT.md'),
    (Join-Path $root 'CHIRAL_GRAVITON_API.md')
)
$documentText = ($documents | ForEach-Object { Get-Content -Raw -Encoding utf8 $_ }) -join "`n"
$forbidden = @(
    'SO\(3\)-equivariant NQS',
    'pass, bounded',
    'both optional strong deliverables',
    'thermodynamic-scale VMC implementation is complete'
)
$truthful = $true
foreach ($pattern in $forbidden) {
    if ($documentText -match $pattern) {
        $truthful = $false
    }
}
if ($truthful -and
    (Test-Path (Join-Path $root 'requirements-lock.txt')) -and
    (Test-Path (Join-Path $root 'scripts\bootstrap.ps1'))) {
    $score += 1
}

& $python -m pytest -q (Join-Path $root 'tests') *> $null
if ($LASTEXITCODE -eq 0) {
    $score += 1
}

Write-Output $score
if ($score -ne 8) {
    Write-Error "Graviton review verification failed: score $score/8"
    exit 1
}
