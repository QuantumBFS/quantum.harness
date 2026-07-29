param(
    [string]$OutputDirectory = "",
    [switch]$Force
)

$ErrorActionPreference = 'Stop'
$root = Split-Path -Parent $PSScriptRoot
$python = Join-Path $root '.venv\Scripts\python.exe'
$env:PYTHONPATH = Join-Path $root 'src'
if (-not (Test-Path -LiteralPath $python)) {
    throw "Missing solution environment: $python"
}
if (-not $OutputDirectory) {
    $repository = Resolve-Path (Join-Path $root '..\..\..\..')
    $stamp = Get-Date -Format 'yyyyMMdd-HHmmss'
    $OutputDirectory = Join-Path $repository "tracks\qmc\results\$stamp-chiral-graviton"
}
if ((Test-Path -LiteralPath $OutputDirectory) -and -not $Force) {
    throw "Output directory exists; pass -Force or choose another path: $OutputDirectory"
}
New-Item -ItemType Directory -Force -Path $OutputDirectory | Out-Null

& $python -m pytest -q $root
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }

$edFiles = @()
$nqsFiles = @()
foreach ($n in 3..8) {
    $ed = Join-Path $OutputDirectory "ed-n$n.json"
    & $python -m chiral_graviton ed --n $n --output $ed
    if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
    $edFiles += $ed
    if ($n -le 7) {
        $nqs = Join-Path $OutputDirectory "nqs-n$n.json"
        & $python -m chiral_graviton nqs --n $n --samples 100000 --output $nqs
        if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
        $nqsFiles += $nqs
    }
}

$multiplet = Join-Path $OutputDirectory 'multiplet-n7.json'
& $python -m chiral_graviton multiplet --n 7 --output $multiplet
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }

& $python (Join-Path $PSScriptRoot 'summarize_results.py') `
    --ed $edFiles `
    --nqs $nqsFiles `
    --minimum-n 4 `
    --output-dir $OutputDirectory
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }

Write-Output "Acceptance artifacts: $OutputDirectory"
