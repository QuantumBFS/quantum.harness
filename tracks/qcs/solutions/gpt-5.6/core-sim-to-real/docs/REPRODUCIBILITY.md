# Reproducibility guide

Status: final package
Last updated: 2026-07-29

## Audited environment

```text
Ubuntu 26.04 under WSL2
Python 3.13.14
JAX/JAXlib 0.4.38, x64 CPU
NumPy 2.2.6
SciPy 1.15.3
Matplotlib 3.11.1
```

The formal numerical claim uses CPU/x64. A GPU environment is not part of the
audited result.

## Installation

From the repository root:

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
python -m pip install -r core-sim-to-real/requirements.txt
```

After installation, the audit and simulation require no network.

## Three levels of reproduction

### 1. Static independent audit

```bash
python core-sim-to-real/code/attempt50_result_audit.py --verify-only
```

This does not import the simulator or open a truth instance. It reconstructs
the 288-run grid, paired seeds, truth-cell aggregation, 20,000-draw
family-stratified bootstrap, paired intervals, resource formulas, safety
interval, gates, source seals, and artifact hashes from the immutable formal
result. Expected result: `pass; checks=18/18`.

### 2. Fast minimal working example

```bash
python core-sim-to-real/run_challenge.py --mwe
```

This runs `k=15`, completed `k=40`, and raw `k=40` on one public development
truth. It retains all 66/166/166 query rows and writes `run.json`,
`metrics.json`, and `mwe.png`. It verifies the software and ledger contract;
it is not statistical confirmation evidence.

### 3. Queries-to-target deliverable

```bash
python core-sim-to-real/code/attempt51_queries_to_target.py --verify-only
```

This independently derives the required dimension-sweep and fresh
queries-to-target statistics from sealed Attempt-44/49 results. It performs no
simulator or device query. Run without `--verify-only` to regenerate the JSON,
PNG, SVG, and Markdown report.

### 4. Failure-boundary and cross-size-invariant audit

```bash
python core-sim-to-real/code/attempt52_gap_invariant_audit.py --verify-only
```

This closes 22 source, failure-boundary, conditional-rank-invariant, numerical
artifact, and honest-negative-result checks. It performs no simulator query
and opens no confirmation truth.

### 5. Full public replay

```bash
python core-sim-to-real/run_challenge.py --full
```

This replays all 24 truth cells × four nested replicates × three methods and
requires the recomputed summary to match archived Attempt 49 exactly. The
truths are now public, so this is a replay, not another independent fresh
confirmation.

Both run modes create a new ignored timestamped directory under
`core-sim-to-real/run_outputs/`. Use `--output EMPTY_DIRECTORY` to select a
different empty destination. Existing non-empty directories are never
overwritten.

## Final artifact checks

```bash
python -m unittest core-sim-to-real/tests/test_final_contract.py
```

The tests check the CLI contract, static audit, queries-to-target derivation,
failure-boundary/invariant audit, JSON finiteness and schema, all three
completed figure results, the four required report sections, self-contained
UTF-8 HTML, absence of personal absolute paths, and absence of the protected
notebook.

## Determinism and provenance

- JAX CPU and x64 are selected before importing JAX.
- Truth seeds and nested measurement-noise seeds are recorded separately.
- Immutable protocol, configuration, source, and artifacts are hashed.
- Text source seals canonicalize CRLF/LF; binary artifacts use byte hashes.
- Every scalar query and shot is counted, including validation and rejected
  moves.
- Failures and exceptions remain in the aggregate; no replacement seed or
  automatic scientific retry is allowed.
- Formal Attempt-49 outputs are immutable. Every replay writes elsewhere.

## Known limitations

The formal result compacts each query ledger to row count, shot total,
per-purpose totals, and a canonical full-row hash. Aggregate cost is
reconstructible, but the full stored row hash cannot be independently rebuilt
from the compact artifact alone. The MWE therefore retains complete rows.

For drift-only rows, `control_map_minus_identity_spectral_norm` records a
sampled candidate control map that was not applied. The applied control-map
perturbation is zero. This is a metadata-label issue and does not affect the
simulator, scores, bootstrap, or gates.

## Windows and WSL notes

- Read and write JSON/Markdown as UTF-8.
- Render the final HTML with a UTF-8-capable Python environment; the official
  renderer may inherit the Windows console code page.
- Known WSL warnings about untranslated Windows `PATH` entries do not affect
  this package.
- Never use broad `git add` in the official solution directory. The protected
  upstream notebook is outside this public package and must remain untouched.
