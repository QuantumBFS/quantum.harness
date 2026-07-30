# Challenge 15 report assets

The checked-in figures are deterministic SVG text/shape renderings:

- `challenge15-method-flow.svg` — architecture plus editorial status boundary;
- `challenge15-evidence.svg` — N=6 CPU smoke coverage and DCU job 719801 facts;
- `challenge15-report-evidence.json` — canonical compact evidence envelope.

## Evidence and trust boundary

By default, `tools/generate_challenge15_report_figures.py` reads the compact
manifest. A fresh checkout therefore does not need `.production-results` to
reproduce both SVGs. The manifest contains the exact 40 displayed CPU energies,
five result/payload hashes, all CPU source hashes, runtime/fingerprint and
wall/RSS facts, successful and failed DCU job facts, timings, lineage,
download-file hashes, runtime-lock facts, deterministic receipt timestamp, and
hashed editorial source/review records. It contains no checkpoint/model blobs.

The manifest has a canonical-JSON envelope and payload self-hash. It proves
figure/report consistency; it is not a substitute for the full raw artifacts
needed for scientific re-verification. Supplying `--artifact-root` independently
audits the manifest against all five CPU result envelopes and both DCU bundles.
That audit verifies each CPU envelope payload hash and source/fingerprint facts,
and every file listed by each DCU `local-verification.download_sha256`, plus
bundle/job/status/test/timing/runtime/accounting/lineage fields.

Figure 1 combines artifact facts with editorial status constants. The generator
validates package-relative README, DESIGN, chiral/Torch source and runtime-lock
hashes. Archived review/progress hashes identify the records used when freezing
the constants; those records need not exist in a fresh checkout.

## Default fresh-checkout generation

Run from the Challenge 15 package root:

```bash
REPO_ROOT=${REPO_ROOT:?set REPO_ROOT to a quantum.harness checkout}
CLEAN_PKG="$REPO_ROOT/tracks/qmc/solutions/frustration-free/challenge-15"
test -f "$CLEAN_PKG/report_assets/challenge15-report-evidence.json"
cd "$CLEAN_PKG"
python3 tools/generate_challenge15_report_figures.py \
  --output-dir report_assets
```

Expected summary:

```text
validated compact manifest: 5 CPU results, 20 smoke cells, DCU jobs 719801/719643
```

## Optional raw-artifact audit

The original audited location is described generically as
`<WORKTREE_ROOT>/.production-results`; it is not published by this report.

```bash
REPO_ROOT=${REPO_ROOT:?set REPO_ROOT to a quantum.harness checkout}
ARTIFACT_ROOT=${ARTIFACT_ROOT:?set ARTIFACT_ROOT to the full .production-results directory}
CLEAN_PKG="$REPO_ROOT/tracks/qmc/solutions/frustration-free/challenge-15"
cd "$CLEAN_PKG"
python3 tools/generate_challenge15_report_figures.py \
  --artifact-root "$ARTIFACT_ROOT" \
  --output-dir report_assets
```

Expected additional line:

```text
raw artifact audit matched compact evidence manifest
```

## Exact-byte verification

Exact-byte hashes below were tested with CPython 3.14.4. The generator uses
only the standard library and is intended to remain logically compatible with
modern CPython 3, including 3.12.x, but exact-byte reproduction is claimed only
for the tested 3.14.4 runtime because JSON float rendering is part of the byte
contract.

```bash
REPO_ROOT=${REPO_ROOT:?set REPO_ROOT to a quantum.harness checkout}
CLEAN_PKG="$REPO_ROOT/tracks/qmc/solutions/frustration-free/challenge-15"
TMP_ONE=$(mktemp -d)
TMP_TWO=$(mktemp -d)
cd "$CLEAN_PKG"
python3 tools/generate_challenge15_report_figures.py --output-dir "$TMP_ONE"
python3 tools/generate_challenge15_report_figures.py --output-dir "$TMP_TWO"
cmp "$TMP_ONE/challenge15-method-flow.svg" "$TMP_TWO/challenge15-method-flow.svg"
cmp "$TMP_ONE/challenge15-evidence.svg" "$TMP_TWO/challenge15-evidence.svg"
python3 - <<'PY'
from pathlib import Path
import hashlib
import xml.etree.ElementTree as ET

expected = {
    "challenge15-report-evidence.json": "16b9b96140993edb043f4c76d88d9445d5083616e82491d3ecfdc7ea16751383",
    "challenge15-method-flow.svg": "f60369fc054093e8477ecbb0322d042b02da52bebd2fad11a9cbe5547db7ba78",
    "challenge15-evidence.svg": "c03a0448d6bcc32156c4e4bf756a336cc42b7947240cc88e860b58627d36a7b8",
}
for name, wanted in expected.items():
    path = Path("report_assets") / name
    got = hashlib.sha256(path.read_bytes()).hexdigest()
    assert got == wanted, (name, got)
    if name.endswith(".svg"):
        ET.parse(path)
    print(name, got)
PY
python3 - <<'PY'
from pathlib import Path
p = Path("tools/generate_challenge15_report_figures.py")
compile(p.read_text(), str(p), "exec")
print("PYTHON_COMPILE_OK")
PY
```

SVG metadata embeds the compact-manifest hash, generic raw source locations,
CPU/DCU source identities, package source hashes and editorial review-record
hashes. There is no raster content, gradient or external font.
