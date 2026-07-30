param(
    [string]$CpmcRunDirectory = ""
)

$ErrorActionPreference = 'Stop'
Set-StrictMode -Version Latest
$root = Split-Path -Parent $PSScriptRoot
$repoRoot = [System.IO.Path]::GetFullPath((Join-Path $root '..\..\..\..'))
$python = Join-Path $root '.venv\Scripts\python.exe'
$env:PYTHONPATH = Join-Path $root 'src'
if (-not $CpmcRunDirectory) {
    $CpmcRunDirectory = Join-Path $root '..\..\results\20260728-165638-cpmc-lab-fig4a-three-point'
}
$CpmcRunDirectory = [System.IO.Path]::GetFullPath($CpmcRunDirectory)

if (-not (Test-Path -LiteralPath $python)) {
    throw "Python environment is missing: $python"
}

& $python -m pytest -q (Join-Path $root 'tests')
if ($LASTEXITCODE -ne 0) {
    throw "Python regression suite failed with exit code $LASTEXITCODE"
}

$finalizer = Join-Path $root 'cpmc_lab_fig4\finalize_cpmc_fig4abc.py'
& $python -X utf8 $finalizer $CpmcRunDirectory --check-only
if ($LASTEXITCODE -ne 0) {
    throw "CPMC scientific check failed with exit code $LASTEXITCODE"
}

foreach ($point in @('smoke', 'u0', 'u1', 'u2', 'u3', 'u4', 'u5', 'u6', 'u7', 'u8')) {
    $failed = Join-Path $CpmcRunDirectory "raw\$point\FAILED.json"
    if (Test-Path -LiteralPath $failed) {
        throw "Failure marker exists: $failed"
    }
}

$runData = Get-Content -Raw -Encoding utf8 (Join-Path $CpmcRunDirectory 'run.json') | ConvertFrom-Json
$figureIds = @($runData.figures | ForEach-Object { $_.id })
$expectedFigures = @(
    'Figure 4(a), full integer grid',
    'Figure 4(b), full integer grid',
    'Figure 4(c), full integer grid'
)
if (($figureIds.Count -ne 3) -or (Compare-Object $expectedFigures $figureIds)) {
    throw "run.json does not contain exactly the three full-grid Figure 4 panels"
}
if (@($runData.figures | Where-Object { $_.results.match -ne 'yes' }).Count -ne 0) {
    throw "At least one Figure 4 scientific comparison is not accepted"
}

foreach ($required in @(
    'derived_observables.csv', 'mc_diagnostics.csv', 'artifact_manifest.json',
    'figs\fig4a_total_energy.svg', 'figs\fig4b_potential_double_occupancy.svg',
    'figs\fig4c_kinetic.svg', 'report.html', 'FINALIZED.txt'
)) {
    if (-not (Test-Path -LiteralPath (Join-Path $CpmcRunDirectory $required))) {
        throw "Required reviewed artifact is missing: $required"
    }
}

$artifactManifest = Get-Content -Raw -Encoding utf8 (Join-Path $CpmcRunDirectory 'artifact_manifest.json') | ConvertFrom-Json
foreach ($entry in $artifactManifest.files.PSObject.Properties) {
    $artifact = Join-Path $CpmcRunDirectory ($entry.Name -replace '/', '\')
    $actual = (Get-FileHash -Algorithm SHA256 -LiteralPath $artifact).Hash.ToLowerInvariant()
    if ($actual -ne [string]$entry.Value) {
        throw "Artifact checksum mismatch: $($entry.Name)"
    }
}

$vendorRoot = Join-Path $repoRoot '.external\cpmc-lab\CPMC_Lab_20160129'
if (Test-Path -LiteralPath $vendorRoot) {
    $sourceManifest = Join-Path $root 'cpmc_lab_fig4\cpmc_lab_source_manifest.sha256'
    foreach ($line in Get-Content -Encoding utf8 $sourceManifest) {
        if ($line -notmatch '^([0-9a-f]{64})  (.+)$') {
            throw "Malformed CPMC-Lab source manifest line: $line"
        }
        $source = Join-Path $vendorRoot $Matches[2]
        $actual = (Get-FileHash -Algorithm SHA256 -LiteralPath $source).Hash.ToLowerInvariant()
        if ($actual -ne $Matches[1]) {
            throw "CPMC-Lab vendor source checksum mismatch: $($Matches[2])"
        }
    }
}

$parseTargets = @(
    (Join-Path $root 'scripts\verify.ps1'),
    (Join-Path $root 'scripts\verify_research.ps1'),
    (Join-Path $root 'scripts\verify_review_gate.ps1'),
    (Join-Path $root 'cpmc_lab_fig4\monitor_and_finalize.ps1')
)
foreach ($target in $parseTargets) {
    $tokens = $null
    $errors = $null
    [void][System.Management.Automation.Language.Parser]::ParseFile(
        $target, [ref]$tokens, [ref]$errors
    )
    if ($errors.Count -ne 0) {
        throw "PowerShell parse errors in $target`: $($errors -join '; ')"
    }
}

Write-Output 'QMC_REVIEW_GATE=PASS'
