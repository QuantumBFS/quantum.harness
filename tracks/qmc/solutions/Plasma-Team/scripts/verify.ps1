$ErrorActionPreference = 'SilentlyContinue'
$root = Split-Path -Parent $PSScriptRoot
$python = Join-Path $root '.venv\Scripts\python.exe'
$env:PYTHONPATH = Join-Path $root 'src'
$score = 0

if ((Test-Path (Join-Path $root 'DEV_DOCUMENT.md')) -and
    (Test-Path (Join-Path $root 'CHIRAL_GRAVITON_API.md')) -and
    (Test-Path (Join-Path $root 'CHIRAL_GRAVITON_STYLE.md'))) { $score += 1 }

if (Test-Path $python) {
    & $python -c "import numpy, scipy, sympy, chiral_graviton" *> $null
    if ($LASTEXITCODE -eq 0) { $score += 1 }

    foreach ($testFile in @(
        'tests/test_basis.py',
        'tests/test_angular_momentum.py',
        'tests/test_interactions.py',
        'tests/test_ed.py',
        'tests/test_nqs.py',
        'tests/test_observables.py'
    )) {
        & $python -m pytest -q (Join-Path $root $testFile) *> $null
        if ($LASTEXITCODE -eq 0) { $score += 1 }
    }
}

Write-Output $score
