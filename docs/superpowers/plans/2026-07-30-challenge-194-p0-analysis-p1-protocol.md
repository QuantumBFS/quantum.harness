# Challenge 194 P0 Analysis and P1 Protocol Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Download and locally verify the immutable P0 Pilot, produce a deterministic P0 analysis, and publish a frozen P1 refinement protocol without running P1.

**Architecture:** Keep transfer, scientific aggregation, deterministic window selection, and protocol publication in separate units. All readers consume only a verified P0 root; all outputs are canonical bounded JSON published once and bound to the P0 run-spec/progress hashes.

**Tech Stack:** Python 3.12, NumPy, h5py, pytest, rsync, existing `long_range_percolation` artifact and Pilot verifiers.

## Global Constraints

- P0 input contains exactly 96 verified trajectories.
- P0 progress SHA256 is `ea29a8163a5d3e85768842d64fac4c719f5aeadf965b3318b305fb7a2cc2d15f`.
- P0 data remain immutable and exploratory.
- Whole trajectories are the independent units for means and standard errors.
- P1 selection uses only nonzero P0 checkpoints.
- P1 uses the existing `pilot` phase, a new grid namespace/master seed, and 16 replicas per `(sigma, L)`.
- P1 grids contain exactly nine ordered binary64 points serialized with `float.hex()`.
- Missing common brackets for `sigma <= 1` fail closed and request a versioned P0 extension.
- Sigma `1.1` is a crossover control and never receives a transition claim.

---

### Task 1: Reproducible P0 Transfer and Local Verification

**Files:**
- Create: `tracks/qmc/solutions/frustration-free/challenge-194/scripts/download_pilot.sh`
- Modify: `tracks/qmc/solutions/frustration-free/challenge-194/README.md`
- Test: `tracks/qmc/solutions/frustration-free/challenge-194/tests/test_download_pilot.py`

**Interfaces:**
- Consumes: remote Pilot root, local destination, existing `scripts/run_pilot.py verify`.
- Produces: byte-preserving local Pilot root that passes semantic verification.

- [ ] **Step 1: Write failing shell-contract tests**

Test that the script requires absolute source/destination arguments, invokes
`rsync` with archive/checksum/partial-safe flags, refuses an existing
nonempty destination unless it is the same resumable root, and invokes the
exact local verifier after transfer.

- [ ] **Step 2: Run the transfer tests and verify RED**

Run:
`uv run --with pytest pytest tests/test_download_pilot.py -q`

Expected: failure because `scripts/download_pilot.sh` does not exist.

- [ ] **Step 3: Implement the transfer script**

The script accepts:

```text
download_pilot.sh <ssh-host> <absolute-remote-root> <absolute-local-root> <absolute-python>
```

It uses `rsync --archive --checksum --partial --itemize-changes`, never
deletes remote or local files, writes scheduler/transfer logs outside the
immutable root, then runs:

```bash
PYTHONPATH=<solution>/src <python> scripts/run_pilot.py verify \
  --run-spec <local-root>/run_spec.json
```

- [ ] **Step 4: Run focused tests and shell syntax**

Run:

```bash
uv run --with pytest pytest tests/test_download_pilot.py -q
bash -n scripts/download_pilot.sh
```

Expected: all pass.

- [ ] **Step 5: Download and verify the real P0 root**

Remote:
`wuzh02-jiangweiqi:/work/share/giggleliu/jiangweiqi/results/challenge-194/pilot-p0-739880d`

Local:
`results/challenge-194/pilot-p0-739880d`

Expected verifier result:
`{"cells": 96, "status": "verified", "trajectories": 96}`.

- [ ] **Step 6: Commit**

Commit message:
`Add reproducible P0 download verification`

### Task 2: Bounded P0 Aggregation

**Files:**
- Create: `tracks/qmc/solutions/frustration-free/challenge-194/src/long_range_percolation/pilot_analysis.py`
- Create: `tracks/qmc/solutions/frustration-free/challenge-194/tests/test_pilot_analysis.py`

**Interfaces:**
- Consumes: `Path` to verified P0 `run_spec.json`.
- Produces:
  - `PilotEstimate` immutable records;
  - `aggregate_p0(run_spec: Path) -> dict[str, object]`;
  - canonical analysis document with exact source hashes.

- [ ] **Step 1: Write failing aggregation tests**

Create tiny verified test trajectories for two sizes, two replicas, and three
couplings. Assert exact grouping by `(sigma, length, kappa)`, arithmetic mean,
sample standard error with `ddof=1`, replica/request identities, fixed
observable-column names, deterministic ordering, and rejection of missing or
duplicate replicas.

- [ ] **Step 2: Verify RED**

Run:
`uv run --with pytest pytest tests/test_pilot_analysis.py -q`

Expected: import failure for `pilot_analysis`.

- [ ] **Step 3: Implement streaming aggregation**

Use `load_pilot_run_spec` and `load_verified_trajectory`; hold one trajectory
at a time. Extract `Q_G`, four-sector crossing, `S1/L`, and `S2/L`. Accumulate
bounded per-cell vectors for eight replicas and emit:

```python
{
    "sigma_hex": float(sigma).hex(),
    "length": length,
    "kappa_hex": float(kappa).hex(),
    "replica_count": 8,
    "means": {...},
    "standard_errors": {...},
    "request_sha256": [...],
}
```

- [ ] **Step 4: Add source binding**

The document includes schema version, P0 run-spec SHA256, P0 progress SHA256,
source revision, analysis-plan SHA256, and an analysis-document SHA256 over
the unsigned canonical document.

- [ ] **Step 5: Run aggregation tests**

Run:
`uv run --with pytest pytest tests/test_pilot_analysis.py -q`

Expected: all pass.

- [ ] **Step 6: Commit**

Commit message:
`Add bounded P0 observable aggregation`

### Task 3: Deterministic Bracket Selection

**Files:**
- Modify: `tracks/qmc/solutions/frustration-free/challenge-194/src/long_range_percolation/pilot_analysis.py`
- Modify: `tracks/qmc/solutions/frustration-free/challenge-194/tests/test_pilot_analysis.py`

**Interfaces:**
- Consumes: validated P0 aggregate document.
- Produces:
  - `select_p1_brackets(analysis: Mapping[str, object]) -> dict[str, object]`;
  - explicit P0-extension failure document when a required bracket is absent.

- [ ] **Step 1: Write failing selector tests**

Cover:

- a unique common `Q_G`/crossing-probability interval;
- multiple marked intervals selecting the narrowest, then lower coupling;
- no common interval for `sigma <= 1` producing `requires_p0_extension=true`;
- sigma `1.1` selecting maximum absolute crossing-probability slope;
- exact rejection of zero-coupling selection, reordered couplings, NaN, and
  missing largest-size estimates.

- [ ] **Step 2: Verify RED**

Run the selector tests and confirm failure because the selector is absent.

- [ ] **Step 3: Implement the frozen rule**

Use the two largest lengths. Mark adjacent intervals exactly as specified in
the design. Never interpolate a transition estimate during P0 selection.
Serialize selected endpoint values with `float.hex()`, estimator evidence, and
tie-break metadata.

- [ ] **Step 4: Verify GREEN**

Run:
`uv run --with pytest pytest tests/test_pilot_analysis.py -q`

Expected: all aggregation and selector tests pass.

- [ ] **Step 5: Commit**

Commit message:
`Freeze deterministic P1 bracket selection`

### Task 4: Immutable P1 Protocol Publication

**Files:**
- Modify: `tracks/qmc/solutions/frustration-free/challenge-194/src/long_range_percolation/pilot_analysis.py`
- Create: `tracks/qmc/solutions/frustration-free/challenge-194/scripts/analyze_pilot.py`
- Modify: `tracks/qmc/solutions/frustration-free/challenge-194/tests/test_pilot_analysis.py`
- Create: `tracks/qmc/solutions/frustration-free/challenge-194/tests/test_analyze_pilot_cli.py`

**Interfaces:**
- Consumes: verified P0 root and selected brackets.
- Produces:
  - immutable `p0_analysis.json`;
  - immutable `p1_protocol.json`;
  - `build_p1_protocol(...) -> dict[str, object]`.

- [ ] **Step 1: Write failing protocol tests**

Assert four sigma entries, three lengths, 16 fresh replicas, exact nine-point
grids, recursive bisection ordering, no P0 replica reuse, unique request/RNG
identities, canonical paths, protocol hash, no-clobber publication, and
rejection when any `sigma <= 1` bracket requires extension.

- [ ] **Step 2: Verify RED**

Run:

```bash
uv run --with pytest pytest \
  tests/test_pilot_analysis.py tests/test_analyze_pilot_cli.py -q
```

Expected: protocol/CLI symbols are absent.

- [ ] **Step 3: Implement recursive binary64 grids**

Generate midpoint levels in order, deduplicate by binary64 bit identity, sort
strictly, require exactly nine points including endpoints, and store only
canonical hex strings in the protocol.

- [ ] **Step 4: Implement fresh RNG assignment**

Freeze a new master seed and P1 grid ID in the protocol. Derive every stream
identity using existing `derive_stream_material`, require uniqueness across
all P1 requests, and hash the complete ordered assignment.

- [ ] **Step 5: Implement atomic CLI publication**

Commands:

```text
analyze-pilot.py analyze --run-spec ... --output p0_analysis.json
analyze-pilot.py build-p1 --analysis ... --output p1_protocol.json
analyze-pilot.py verify --analysis ... --p1-protocol ...
```

Use bounded descriptor reads and `_publish_json_once`; existing outputs verify
byte-for-byte or fail.

- [ ] **Step 6: Run focused and full tests**

Run:

```bash
uv run --with pytest pytest \
  tests/test_pilot_analysis.py tests/test_analyze_pilot_cli.py -q
uv run --with pytest pytest -q
```

Expected: focused and full suites pass.

- [ ] **Step 7: Analyze real P0 and publish P1 protocol**

Run all three CLI commands against the downloaded P0 root. Record selected
windows, document hashes, and whether a P0 extension is required.

- [ ] **Step 8: Commit**

Commit message:
`Publish deterministic P1 refinement protocol`

### Task 5: P0/P1 Documentation Boundary

**Files:**
- Modify: `tracks/qmc/solutions/frustration-free/challenge-194/PILOT_PLAN.md`
- Modify: `tracks/qmc/solutions/frustration-free/challenge-194/README.md`
- Modify: `tracks/qmc/solutions/frustration-free/challenge-194/tests/test_runtime.py`

**Interfaces:**
- Consumes: implemented transfer/analysis/protocol commands.
- Produces: exact collaborator workflow and documentation contract tests.

- [ ] **Step 1: Write failing documentation tests**

Assert README contains exact P0 transfer, verify, analysis, P1 protocol, hash
inspection, and failure/extension commands without claiming P1 was executed.

- [ ] **Step 2: Update documentation**

Document the frozen selection rule, exploratory/confirmatory separation,
resource provenance, current hashes, restart behavior, and exact commands.

- [ ] **Step 3: Run verification**

Run:

```bash
uv run --with pytest pytest tests/test_runtime.py -q
uv run --with pytest pytest -q
git diff --check
```

Expected: all pass and no whitespace errors.

- [ ] **Step 4: Commit**

Commit message:
`Document P0 analysis and P1 protocol workflow`
