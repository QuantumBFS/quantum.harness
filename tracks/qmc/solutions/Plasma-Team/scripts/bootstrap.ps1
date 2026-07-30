param(
    [string]$Environment = ".venv",
    [switch]$SkipTests
)

$ErrorActionPreference = 'Stop'
Set-StrictMode -Version Latest
$root = Split-Path -Parent $PSScriptRoot
$environmentPath = if ([System.IO.Path]::IsPathRooted($Environment)) {
    $Environment
} else {
    Join-Path $root $Environment
}
$python = Join-Path $environmentPath 'Scripts\python.exe'

if (-not (Test-Path -LiteralPath $python)) {
    & py -3.12 -m venv $environmentPath
    if ($LASTEXITCODE -ne 0) {
        throw "Virtual-environment creation failed with exit code $LASTEXITCODE"
    }
}

& $python -m pip install --disable-pip-version-check -r (Join-Path $root 'requirements-lock.txt')
if ($LASTEXITCODE -ne 0) {
    throw "Locked dependency installation failed with exit code $LASTEXITCODE"
}

$env:PYTHONPATH = Join-Path $root 'src'
& $python -c "import numpy, scipy, sympy, chiral_graviton; print(chiral_graviton.__version__)"
if ($LASTEXITCODE -ne 0) {
    throw "Import check failed with exit code $LASTEXITCODE"
}

if (-not $SkipTests) {
    & $python -m pytest -q (Join-Path $root 'tests')
    if ($LASTEXITCODE -ne 0) {
        throw "Regression tests failed with exit code $LASTEXITCODE"
    }
}

Write-Output 'GRAVITON_BOOTSTRAP=PASS'
