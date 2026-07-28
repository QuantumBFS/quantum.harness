# Challenge 81 Restartable Production Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make Challenge #81 finite-temperature TDVP cells crash-durable and resumable, calibrate their real cluster cost, and complete a validated `N_b=12`, β=16 production anchor.

**Architecture:** Separate numerical evolution state from orchestration. Julia exposes a step-boundary resume state and atomically serializes version-bound MPS checkpoints; Python owns cell locks, signal forwarding, checkpoint generations, and immutable completed-cell publication. Slurm only supplies an early warning signal and repeatedly invokes the same content-addressed cell until completion.

**Tech Stack:** Julia 1.11.6, ITensors/ITensorMPS, HDF5.jl, JSON3.jl, Python 3.12, pytest, jsonschema, POSIX signals and atomic rename, Slurm.

## Global Constraints

- Physical model is fixed to `D=1`, `U=0.8`, `Gamma=0.1`, `epsilon_d=-U/2`, and `mu=0`.
- Production uses deterministic purification of the complete grand-canonical interacting finite-bath Hamiltonian.
- The finite-bath MPS-versus-ED maximum absolute error gate remains `1e-6`.
- The shared Green-function grid is `tau/beta={0,1/4,1/2,3/4,1}`.
- A checkpoint is never accepted as a completed convergence cell.
- Resume is fail-closed on any request, bath, source, Julia project, Manifest, dependency-version, solver-setting, phase, or cursor mismatch.
- Checkpoints are atomically staged, fsynced, independently reloaded, and only then published.
- A scheduler timeout or SIGTERM is retryable only when a new validated checkpoint has been published.
- Scientific failures, nonfinite tensors, failed Krylov convergence, excessive truncation, maxdim saturation, and provenance mismatch remain non-retryable.
- `N_b=48` execution remains forbidden until QN purification and star-to-chain/compressed-MPO capability gates pass.
- No multi-hour production array is submitted until a reduced integration test resumes one cell across at least two scheduler jobs.

---

### Task 1: Establish the reviewed Challenge #81 baseline

**Files:**
- Verify: `tracks/mps/solutions/frustration-free/tests/`
- Verify: `tracks/mps/solutions/frustration-free/julia/test/runtests.jl`
- Commit: all existing Challenge #81 foundation files plus the approved design and this plan

**Interfaces:**
- Consumes: the currently reviewed MPS–ED acceptance gate and convergence runner.
- Produces: one clean baseline commit for task-scoped review diffs.

- [ ] **Step 1: Verify the Python foundation**

Run:

```bash
uv run --project tracks/mps/solutions/frustration-free --frozen \
  python -m pytest tracks/mps/solutions/frustration-free/tests -q
```

Expected: all tests pass with zero failures.

- [ ] **Step 2: Verify the Julia foundation**

Run:

```bash
julia +1.11.6 \
  --project=tracks/mps/solutions/frustration-free/julia \
  tracks/mps/solutions/frustration-free/julia/test/runtests.jl
```

Expected: all Julia testsets pass with zero errors or failures.

- [ ] **Step 3: Check repository integrity**

Run:

```bash
git diff --check
git status --short
```

Expected: `git diff --check` exits zero; status contains only intended Challenge #81 files and design records.

- [ ] **Step 4: Commit the reviewed foundation**

```bash
git add tracks/mps/solutions/frustration-free \
  docs/superpowers/specs/2026-07-29-challenge81-restartable-production-design.md \
  docs/superpowers/plans/2026-07-29-challenge81-restartable-production.md
git commit -m "Build validated finite-temperature impurity foundation"
```

Expected: one baseline commit and a clean worktree.

---

### Task 2: Add resumable step-boundary TDVP state

**Files:**
- Modify: `tracks/mps/solutions/frustration-free/julia/finite_bath_purification.jl`
- Modify: `tracks/mps/solutions/frustration-free/julia/test/finite_bath_purification.jl`

**Interfaces:**
- Produces:
  - `EvolutionResumeState`
  - `EvolutionInterrupted`
  - `_evolve_normalized_state(...; resume_state=nothing, step_callback=nothing, stop_requested=()->false)`
- Consumes: existing `_evolution_plan`, `TDVPStepMetricsObserver`, and `KrylovStepMetrics`.

- [ ] **Step 1: Write failing constructor and validation tests**

Add tests that construct a resume state after two steps and reject:

```julia
@test_throws ArgumentError EvolutionResumeState(
  completed_steps = -1,
  beta_endpoint = 0.0,
  log_unnormalized_norm = 0.0,
  maximum_link_dimensions_by_bond = Int[],
  step_history = NamedTuple[],
)
```

Also assert rejection of nonfinite cumulative log norm, a cursor beyond the planned step count, a beta endpoint inconsistent with the effective step, and history length different from `completed_steps`.

- [ ] **Step 2: Run the focused tests and observe RED**

```bash
julia +1.11.6 --project=tracks/mps/solutions/frustration-free/julia \
  -e 'include("tracks/mps/solutions/frustration-free/julia/test/finite_bath_purification.jl")'
```

Expected: failure because `EvolutionResumeState` is undefined.

- [ ] **Step 3: Implement the resume state**

Define an immutable state carrying:

```julia
struct EvolutionResumeState
    completed_steps::Int
    beta_endpoint::Float64
    log_unnormalized_norm::Float64
    maximum_link_dimensions_by_bond::Vector{Int}
    step_history::Vector{NamedTuple}
    expansion_applied::Bool
end

struct EvolutionInterrupted <: Exception
    psi::MPS
    state::EvolutionResumeState
end
```

Add a validating keyword constructor. `expansion_applied` prevents replaying global Krylov expansion after resume.

- [ ] **Step 4: Write failing interrupted-versus-uninterrupted tests**

For the existing smallest nontrivial bath:

1. evolve uninterrupted to β=0.2;
2. request stop after two completed steps through `stop_requested`;
3. capture `EvolutionInterrupted`;
4. resume from its `psi` and `state`;
5. compare final norm, cumulative log norm, link dimensions, history, and dense state overlap.

Require:

```julia
@test abs(inner(full.psi, resumed.psi)) ≈ 1.0 atol=1e-11
@test full.diagnostics.log_unnormalized_norm ≈
      resumed.diagnostics.log_unnormalized_norm atol=1e-12
```

- [ ] **Step 5: Implement resumable loop behavior**

Update `_evolve_normalized_state` so it:

- starts at `resume_state.completed_steps + 1`;
- restores cumulative norm, bond maxima, and history;
- skips global expansion when `expansion_applied=true`;
- invokes `step_callback(psi, state)` only after normalization and complete diagnostics;
- throws `EvolutionInterrupted(copy(psi), state)` after callback when `stop_requested()` is true;
- preserves existing return shape for uninterrupted callers.

- [ ] **Step 6: Verify Task 2**

Run the full Julia purification tests. Expected: all pass.

- [ ] **Step 7: Commit**

```bash
git add tracks/mps/solutions/frustration-free/julia/finite_bath_purification.jl \
  tracks/mps/solutions/frustration-free/julia/test/finite_bath_purification.jl
git commit -m "Add resumable TDVP step state"
```

---

### Task 3: Implement atomic version-bound MPS checkpoints

**Files:**
- Create: `tracks/mps/solutions/frustration-free/julia/finite_bath_checkpoint.jl`
- Create: `tracks/mps/solutions/frustration-free/julia/test/finite_bath_checkpoint.jl`
- Modify: `tracks/mps/solutions/frustration-free/julia/Project.toml`
- Modify: `tracks/mps/solutions/frustration-free/julia/Manifest.toml`
- Modify: `tracks/mps/solutions/frustration-free/julia/test/runtests.jl`

**Interfaces:**
- Produces:
  - `CheckpointIdentity`
  - `CheckpointCursor`
  - `write_checkpoint_generation(root, identity, cursor, psi, resume_state)`
  - `load_current_checkpoint(root, expected_identity)`
- Consumes: `EvolutionResumeState`.

- [ ] **Step 1: Add HDF5 through Julia Pkg**

Run:

```bash
julia +1.11.6 --project=tracks/mps/solutions/frustration-free/julia \
  -e 'using Pkg; Pkg.add("HDF5"); Pkg.resolve(); Pkg.instantiate()'
```

Expected: `HDF5` appears as a direct dependency and Manifest remains valid under Julia 1.11.6.

- [ ] **Step 2: Write failing checkpoint round-trip tests**

Tests must verify:

- exact identity/cursor/resume metadata round trip;
- MPS norm and overlap after HDF5 reload;
- current pointer advances only after generation validation;
- old valid generation remains readable;
- `.stage-*` interruption does not advance current;
- symlink, nonregular file, malformed JSON, HDF5 corruption, and hash mismatch are rejected;
- dependency-version, source-hash, and request mismatch are rejected.

- [ ] **Step 3: Run focused tests and observe RED**

Expected: module/file-not-found failure.

- [ ] **Step 4: Implement checkpoint directory format**

Use:

```text
checkpoint-root/
  current.json
  generations/
    checkpoint-<metadata-sha256>/
      metadata.json
      state.h5
      completion.json
```

`metadata.json` is canonical JSON. `state.h5` stores `psi` through ITensor
HDF5 support. `completion.json` binds metadata and state SHA256. The current
pointer binds generation, metadata, state, and completion hashes.

`CheckpointIdentity` includes request/input payload SHA256, bath SHA256,
solver settings, source hashes, Project/Manifest hashes, Julia,
ITensors/ITensorMPS/HDF5 versions, checkpoint schema, and writer version.

- [ ] **Step 5: Implement crash-durable publication**

Write a unique `.stage-*` generation, flush and fsync files, reload and validate
it, rename to `generations/checkpoint-<hash>`, fsync both directories, then
atomically replace and fsync `current.json`.

- [ ] **Step 6: Verify Task 3**

Run checkpoint tests and full Julia tests. Expected: all pass.

- [ ] **Step 7: Commit**

```bash
git add tracks/mps/solutions/frustration-free/julia
git commit -m "Add atomic MPS checkpoint generations"
```

---

### Task 4: Resume the thermal and Green-function workflow

**Files:**
- Modify: `tracks/mps/solutions/frustration-free/julia/finite_bath_observables.jl`
- Modify: `tracks/mps/solutions/frustration-free/julia/test/finite_bath_observables.jl`
- Modify: `tracks/mps/solutions/frustration-free/julia/finite_bath_checkpoint.jl`
- Modify: `tracks/mps/solutions/frustration-free/julia/test/finite_bath_checkpoint.jl`

**Interfaces:**
- Produces:
  - `ObservableCursor(phase, tau_index, spin, segment)`
  - `finite_bath_observables(...; checkpoint_manager=nothing, resume=nothing, stop_requested=()->false)`
- Consumes: Task 2 evolution state and Task 3 checkpoint manager.

- [ ] **Step 1: Write failing cursor tests**

Cover all legal transitions:

```text
thermal
green_up/tau-index/before
green_up/tau-index/after
green_down/tau-index/before
green_down/tau-index/after
complete
```

Endpoint tau values skip TDVP branches. Duplicate and caller-ordered tau values remain distinct by index.

- [ ] **Step 2: Write failing branch-resume equivalence tests**

Interrupt and resume independently in:

- thermal evolution;
- creation-branch before evolution;
- creation-branch after evolution;
- annihilation-branch before evolution;
- annihilation-branch after evolution;
- between two tau points;
- between spin branches.

Compare `n_d`, double occupancy, every `G_up/G_down` value, diagnostics, and
final log partition with uninterrupted output at `atol=1e-10`.

- [ ] **Step 3: Implement cursor and partial-result state**

Checkpoint completed observables and diagnostics alongside the active MPS.
Apply the impurity operator exactly once: the `after` cursor must include the
operator log norm and must never replay insertion after resume.

- [ ] **Step 4: Integrate checkpoint callbacks**

Thermal and `_green_branch` pass step callbacks to `_evolve_normalized_state`.
At branch boundaries publish a checkpoint even when no TDVP step occurs.

- [ ] **Step 5: Verify Task 4**

Run the full Julia test suite. Expected: all tests pass.

- [ ] **Step 6: Commit**

```bash
git add tracks/mps/solutions/frustration-free/julia
git commit -m "Resume complete impurity observable workflow"
```

---

### Task 5: Add runner-level cooperative shutdown

**Files:**
- Modify: `tracks/mps/solutions/frustration-free/julia/finite_bath_mps_runner.jl`
- Modify: `tracks/mps/solutions/frustration-free/julia/test/finite_bath_mps_runner.jl`
- Modify: `tracks/mps/solutions/frustration-free/acceptance.py`
- Modify: `tracks/mps/solutions/frustration-free/tests/test_acceptance.py`

**Interfaces:**
- Runner invocation becomes:

```text
finite_bath_mps_runner.jl INPUT.json OUTPUT.json CHECKPOINT_ROOT
```

- Exit codes:
  - `0`: completed result published;
  - `75`: validated checkpoint published; retryable continuation;
  - all other nonzero codes: non-retryable failure.

- [ ] **Step 1: Write failing strict-request and signal tests**

Test that runner schema version increments and the request binds checkpoint
identity. Send `SIGUSR1` during a reduced evolution and require exit 75, no
final output, and one valid current checkpoint.

- [ ] **Step 2: Extend canonical request construction**

`acceptance._make_mps_request` adds a canonical `checkpoint` object containing
the checkpoint schema and identity hashes but no host-specific path. The path
remains a runner CLI argument.

- [ ] **Step 3: Implement cooperative Julia signal state**

Install a signal-safe flag for `SIGUSR1` and `SIGTERM`; the next completed
step/boundary publishes a checkpoint. Do not serialize from inside the signal
handler.

- [ ] **Step 4: Implement resume-aware runner main**

Load and validate the current checkpoint before evolution. On cooperative
interruption, publish checkpoint, print a flushed continuation line, and exit
75. Only complete results create `OUTPUT.json`.

- [ ] **Step 5: Verify Task 5**

Run runner tests, acceptance tests, and the complete Julia suite.

- [ ] **Step 6: Commit**

```bash
git add tracks/mps/solutions/frustration-free/acceptance.py \
  tracks/mps/solutions/frustration-free/tests/test_acceptance.py \
  tracks/mps/solutions/frustration-free/julia
git commit -m "Handle cooperative MPS runner continuation"
```

---

### Task 6: Make convergence cells and Slurm retryable

**Files:**
- Modify: `tracks/mps/solutions/frustration-free/convergence.py`
- Modify: `tracks/mps/solutions/frustration-free/convergence.schema.json`
- Modify: `tracks/mps/solutions/frustration-free/convergence_slurm_array.sh`
- Modify: `tracks/mps/solutions/frustration-free/tests/test_convergence.py`
- Modify: `tracks/mps/solutions/frustration-free/README.md`

**Interfaces:**
- Produces:
  - `ContinuationAvailable`
  - checkpoint namespace `RUN/checkpoints/<cell-id>/`
  - CLI exit code 75 for retryable cells
- Consumes: runner exit code 75 and Task 3 checkpoint validation.

- [ ] **Step 1: Write failing process-group and continuation tests**

Test:

- child starts in a new process group;
- parent `SIGUSR1` forwards to Julia;
- timeout first requests checkpoint, waits a bounded grace period, then kills;
- exit 75 requires a newly validated checkpoint;
- exit 75 without a new checkpoint is a hard failure;
- RSS breach remains non-retryable;
- completed cells still skip;
- checkpoint files cannot appear inside immutable completed-cell directories.

- [ ] **Step 2: Implement monitored graceful shutdown**

`invoke_julia_runner_monitored` accepts checkpoint validation and grace-period
callbacks, starts the child in a process group, forwards cooperative signals,
and raises `ContinuationAvailable` only after checkpoint validation.

- [ ] **Step 3: Implement durable checkpoint namespace**

Use `RUN/checkpoints/<cell-id>/` under the per-cell advisory lock. Extend run
validation to recognize only hash-valid checkpoint roots for planned cell IDs.
Invalid or stale checkpoints are archived and fail closed.

- [ ] **Step 4: Update cell lifecycle**

Do not delete resumable state on `ContinuationAvailable`. Delete/archive the
checkpoint root only after immutable completed-cell publication succeeds.
CLI `run-cell` maps continuation to exit 75.

- [ ] **Step 5: Update Slurm wrapper**

Trap `SIGUSR1` and `SIGTERM`, forward them to Python, preserve exit 75, and
document submission with:

```bash
sbatch --signal=B:USR1@300 --array=... \
  --export=ALL,HARNESS_SOLUTION_DIR=...,HARNESS_RUN_SPEC=... \
  tracks/mps/solutions/frustration-free/convergence_slurm_array.sh
```

The wrapper remains profile-neutral and does not hardcode partition, account,
hostname, credentials, memory, or wall time.

- [ ] **Step 6: Verify Task 6**

Run:

```bash
uv run --project tracks/mps/solutions/frustration-free --frozen \
  python -m pytest \
  tracks/mps/solutions/frustration-free/tests/test_convergence.py \
  tracks/mps/solutions/frustration-free/tests/test_acceptance.py -q
```

Expected: all pass.

- [ ] **Step 7: Commit**

```bash
git add tracks/mps/solutions/frustration-free
git commit -m "Make convergence cells scheduler-resumable"
```

---

### Task 7: Calibrate runtime resources from checkpoint telemetry

**Files:**
- Modify: `tracks/mps/solutions/frustration-free/convergence.py`
- Modify: `tracks/mps/solutions/frustration-free/convergence.schema.json`
- Modify: `tracks/mps/solutions/frustration-free/tests/test_convergence.py`
- Modify: `tracks/mps/solutions/frustration-free/README.md`

**Interfaces:**
- Produces immutable `calibration.json` and a new plan-bound
  `resources-calibrated.json`; never mutates the original `resources.json`.

- [ ] **Step 1: Write failing calibration tests**

Given measured 4/8/16-thread segments, require:

- throughput in completed beta per second and steps per second;
- time-per-step grouped by observed maximum link dimension;
- checkpoint write/read overhead and size;
- peak RSS and actual Julia/BLAS threads;
- selection of the smallest allocation within 10% of best throughput;
- conservative predicted wall time with measured uncertainty;
- rejection of mixed input/source/runtime identities.

- [ ] **Step 2: Implement telemetry extraction**

Read validated checkpoint generations and Slurm accounting exports. Bind every
measurement to plan, cell, request, checkpoint, source, and runtime hashes.

- [ ] **Step 3: Implement immutable calibrated resources**

Publish a new content-addressed resource artifact. Require its SHA256 as an
explicit production acknowledgment. Existing resources and completion
pointers remain unchanged.

- [ ] **Step 4: Verify Task 7**

Run the convergence tests. Expected: all pass.

- [ ] **Step 5: Commit**

```bash
git add tracks/mps/solutions/frustration-free
git commit -m "Calibrate impurity solver cluster resources"
```

---

### Task 8: Prove two-job resume and launch the β=16 anchor

**Files:**
- Modify only if defects are found: Challenge #81 solution and tests
- Generate remotely: reduced integration run and production run artifacts
- Download locally: validated calibration and completed-cell artifacts

**Interfaces:**
- Consumes all prior tasks.
- Produces the first restartable `N_b=12`, β=16 anchor.

- [ ] **Step 1: Run complete local verification**

Run Python tests, Julia tests, `git diff --check`, and IDE lints. Expected: all pass.

- [ ] **Step 2: Deploy exact source and locked runtimes**

Sync the committed Challenge #81 worktree to LASG02. Verify source hashes,
Julia 1.11.6, Project/Manifest hashes, Python environment, and exact plan
before submission.

- [ ] **Step 3: Run reduced two-job continuation integration**

Submit a reduced `N_b=1` cell with a deliberately short first wall limit and
`--signal=B:USR1@60`. Require:

1. first job exits 75 with a valid checkpoint;
2. second job validates and resumes it;
3. final output matches an uninterrupted local reference within `1e-10`;
4. completed cell publication removes no audit evidence and is independently valid.

- [ ] **Step 4: Benchmark CPU scaling**

Run identical bounded `N_b=12` segments at 4, 8, and 16 threads. Publish and
validate calibration artifacts; choose the smallest allocation within 10% of
best throughput.

- [ ] **Step 5: Submit the production anchor**

Submit `N_b=12`, β=16, `dt=0.05`, `maxdim=512` with calibrated memory/wall time,
early signal, and repeatable continuation. Monitor queue transition, first
progress, every checkpoint, and terminal state.

- [ ] **Step 6: Fetch and validate**

Download the completed cell and calibration artifacts, revalidate hashes and
scientific diagnostics locally, and record actual wall time, peak RSS,
per-bond dimensions, truncation, and Krylov summaries.

- [ ] **Step 7: Commit any integration fixes**

Only if integration revealed defects, commit tested fixes separately from
generated/gitignored results.

## Completion gate

This plan is complete when:

- one cell has resumed successfully across two scheduler jobs;
- 4/8/16-thread calibration is published and validated;
- the `N_b=12`, β=16, `dt=0.05`, `maxdim=512` anchor is complete and locally revalidated;
- all Python and Julia tests pass;
- no checkpoint is represented as a completed scientific result.

The subsequent plan will cover β=16/32 timestep/maxdim sweeps, `N_b=24`,
QN/star-to-chain optimization, `N_b=48`, CT-HYB production, and the final
three-method error report.
