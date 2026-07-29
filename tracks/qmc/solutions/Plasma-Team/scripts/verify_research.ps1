$ErrorActionPreference = 'SilentlyContinue'
$root = Split-Path -Parent $PSScriptRoot
$python = Join-Path $root '.venv\Scripts\python.exe'
$results = Join-Path $root '..\..\results\20260729-chiral-graviton-strong'
$env:PYTHONPATH = Join-Path $root 'src'
$score = 0

if ((Test-Path (Join-Path $root 'src\chiral_graviton\chirality.py')) -and
    (Test-Path (Join-Path $root 'tests\test_chirality.py'))) { $score += 1 }

if ((Test-Path (Join-Path $root 'src\chiral_graviton\scalable_nqs.py')) -and
    (Test-Path (Join-Path $root 'tests\test_scalable_nqs.py'))) { $score += 1 }

if (Test-Path $python) {
    foreach ($testFile in @(
        'tests/test_chirality.py',
        'tests/test_scalable_nqs.py'
    )) {
        & $python -m pytest -q (Join-Path $root $testFile) *> $null
        if ($LASTEXITCODE -eq 0) { $score += 1 }
    }

    $chirality = Join-Path $results 'chirality-coulomb-n7.json'
    if (Test-Path $chirality) {
        & $python -c "import json,sys; p=json.load(open(sys.argv[1])); assert p['bright_to_dark_ratio']>100 and p['bright_lowest_l2_fraction']>0.5 and p['lowest_l2_bright_to_dark_ratio']>100" $chirality *> $null
        if ($LASTEXITCODE -eq 0) { $score += 1 }
    }

    $nqs = Join-Path $results 'nqs-sparse-n9.json'
    if (Test-Path $nqs) {
        & $python -c "import json,sys; p=json.load(open(sys.argv[1])); c=p['projection_certificate']; assert p['n_electrons']==9 and p['projection']=='sparse' and abs(p['l2_excited']-6)<1e-7 and c['l0']['raising_residual']<2e-10 and c['l2']['raising_residual']<2e-10 and p['sampled_gap_error']>0" $nqs *> $null
        if ($LASTEXITCODE -eq 0) { $score += 1 }
    }
}

Write-Output $score
