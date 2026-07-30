# Phase 6 DMRG Optimization Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use
> superpowers:subagent-driven-development (recommended) or
> superpowers:executing-plans to implement this plan task-by-task. Steps use
> checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add provenance-safe MPS checkpoints, parity-resolved Gamma
continuation, exact zero-channel pruning, and staged-chi DMRG, then benchmark
the bounded local workflow without changing the Phase 6 physics protocol.

**Architecture:** Keep Hamiltonian construction, state optimization,
checkpoint persistence, and benchmark orchestration in separate modules.
Continuation supplies only the initial MPS to the unchanged DMRG solver.
Production remains disabled until exact MPO and observable gates pass.

**Tech Stack:** Python 3.11, TeNPy 1.1.0, NumPy, SciPy, h5py through TeNPy's
`hdf5_io`, pytest, existing `mps` conda environment.

## Global Constraints

- Hamiltonian, periodic Hurwitz-zeta convention, rotated operators, and parity
  sectors remain unchanged.
- The immutable Phase 6 Gamma grid and crossing/gap analyses remain unchanged.
- ED validation is limited to `L <= 12`.
- No approximate MPO compression is allowed.
- Remove only coefficients satisfying exact floating-point equality `c_k == 0`.
- Checkpoints record sigma, L, Gamma, K, alpha, r_fit, parity, requested and
  reached chi, sweep state/statistics, and code revision/hash.
- Forward/reverse continuation disagreement cannot be resolved by selecting
  the path closer to a literature value.
- Larger continuation benchmarks are cost-gated and deferred when they exceed
  local resources.
- Do not submit cluster jobs while executing this plan.

---

### Task 1: Provenance-safe atomic MPS checkpoints

**Files:**
- Create: `src/lrtfim/checkpoints.py`
- Modify: `src/lrtfim/__init__.py`
- Create: `tests/test_checkpoints.py`

**Interfaces:**
- Produce:
  `CheckpointProvenance(sigma, length, gamma, num_exponentials, alpha, r_fit, sector, requested_chi, reached_chi, sweep_statistics, code_hash, fit_hash, active_channels)`
- Produce:
  `save_checkpoint(directory: Path, psi: MPS, provenance: CheckpointProvenance, diagnostics: dict) -> None`
- Produce:
  `load_checkpoint(directory: Path, expected: CheckpointProvenance) -> tuple[MPS, dict]`
- Consume TeNPy `hdf5_io.save()` and `hdf5_io.load()`.

- [ ] **Step 1: Write checkpoint identity and mismatch tests**

  Build an `L=4` parity MPS and require:

  ```python
  save_checkpoint(path, psi, provenance, diagnostics)
  loaded, metadata = load_checkpoint(path, provenance)
  assert abs(loaded.overlap(psi)) == pytest.approx(1.0, abs=1e-13)
  assert loaded.chinfo == psi.chinfo
  assert metadata["provenance"]["sector"] == "even"
  ```

  Change each consequential field (`gamma`, sector, fit hash, code hash, chi)
  individually and require `CheckpointMismatch`.

- [ ] **Step 2: Verify RED**

  Run:

  ```bash
  PYTHONPATH=src conda run -n mps python -m pytest \
    tests/test_checkpoints.py -q
  ```

  Expected: import failure for `lrtfim.checkpoints`.

- [ ] **Step 3: Implement canonical provenance and atomic writes**

  Hash canonical JSON with sorted keys:

  ```python
  payload = json.dumps(asdict(provenance), sort_keys=True, separators=(",", ":"))
  provenance_id = hashlib.sha256(payload.encode()).hexdigest()
  ```

  Write `state.h5.tmp` and `checkpoint.json.tmp`, then replace final paths.
  The JSON sidecar contains the provenance ID, full provenance, diagnostics,
  `status="success"`, and checkpoint format version. Delete temporary files
  after a caught write failure without removing a previous valid checkpoint.

- [ ] **Step 4: Implement strict loading**

  Compare every expected field except `sweep_statistics` and `reached_chi`,
  which are outputs. Require the stored reached chi to be at least the
  requested input chi when a checkpoint is used for same-chi continuation.
  Reject non-success metadata, missing HDF5 data, wrong sector, and code/fit
  hash mismatches.

- [ ] **Step 5: Verify GREEN**

  Run the focused tests twice, including a simulated interrupted write that
  proves the prior checkpoint remains loadable.

---

### Task 2: Warm-startable parity-sector DMRG

**Files:**
- Modify: `src/lrtfim/parity_dmrg.py`
- Modify: `src/lrtfim/__init__.py`
- Modify: `tests/test_rotated_basis.py`
- Create: `tests/test_continuation.py`

**Interfaces:**
- Change:
  `_run_sector(model, options, sector, initial_psi: MPS | None = None) -> ParityStateResult`
- Produce:
  `run_parity_ground(model, options, initial_psi=None)`
- Produce:
  `run_parity_spectrum(model, options, even_initial=None, odd_initial=None)`
- Produce:
  `validate_initial_state(model, psi, sector) -> None`.

- [ ] **Step 1: Write failing warm-start validation tests**

  Require a supplied MPS to have the same length, site charge structure,
  finite boundary condition, and parity sector as the target. Require an odd
  checkpoint passed to the even sector to fail before `dmrg.run`.

- [ ] **Step 2: Verify RED**

  Run `tests/test_continuation.py`; expected failure because the runners do not
  accept initial MPS arguments.

- [ ] **Step 3: Implement initialization-only continuation**

  Use:

  ```python
  psi = _initial_state(model, sector) if initial_psi is None else initial_psi.copy()
  validate_initial_state(model, psi, sector)
  info = dmrg.run(psi, model, dict(options))
  ```

  Do not modify `model`, Gamma, MPO coefficients, DMRG convergence tolerances,
  observable definitions, or analysis code.

- [ ] **Step 4: Add L<=12 ED-backed continuation tests**

  At `L=8,10,12`, optimize a neighboring-Gamma state, use it to initialize the
  locked target Gamma, and compare final even/odd energies, gap, and physical
  correlations with cold-start DMRG and dense ED using existing Phase 6
  tolerances.

- [ ] **Step 5: Verify GREEN**

  Run continuation, rotated-basis, and Phase 5 validation tests.

---

### Task 3: Exact zero-channel pruning

**Files:**
- Modify: `src/lrtfim/mpo.py`
- Modify: `src/lrtfim/__init__.py`
- Modify: `tests/test_mpo.py`
- Modify: `tests/test_validation.py`
- Modify: `tests/test_rotated_basis.py`

**Interfaces:**
- Produce:
  `active_exponential_channels(lambdas, coefficients) -> (lambdas, coefficients, indices)`
- Add keyword:
  `prune_zero_channels: bool = False` to periodized MPO graph/build functions.

- [ ] **Step 1: Write failing graph-dimension and equality tests**

  Use a fit with three exact zeros and require:

  ```python
  full = build_rotated_periodized_mpo(..., prune_zero_channels=False)
  pruned = build_rotated_periodized_mpo(..., prune_zero_channels=True)
  assert max(full.chi) == 2 * K + 2
  assert max(pruned.chi) == 2 * np.count_nonzero(coefficients) + 2
  np.testing.assert_allclose(
      dense_mpo_hamiltonian(pruned),
      dense_mpo_hamiltonian(full),
      atol=2e-13,
  )
  ```

  Include a coefficient of `1e-300` and prove it is retained.

- [ ] **Step 2: Verify RED**

  Run the focused MPO tests; expected failure for the missing keyword/helper.

- [ ] **Step 3: Implement exact pruning**

  Select only `coefficients != 0.0`; never use an absolute or relative
  threshold. Return original channel indices for provenance. Leave the default
  disabled.

- [ ] **Step 4: Run dense-MPO and observable gates**

  For `L=8,10,12`, require full/pruned agreement for:

  - reconstructed pair coefficients;
  - dense Hamiltonian;
  - E0, E1, and gap;
  - translation-averaged full physical correlations.

  Also retain the exact-pair ED comparison already used by the Phase 5 gate.

- [ ] **Step 5: Enable only in the optimized runner**

  The base builder remains backward-compatible with pruning disabled. The
  optimized Phase 6 command explicitly requests pruning and writes active
  channel indices plus both fit and Hamiltonian hashes.

- [ ] **Step 6: Verify GREEN**

  Run all MPO, validation, and rotated-basis tests.

---

### Task 4: Staged-chi optimization and checkpoint chain

**Files:**
- Create: `src/lrtfim/staged_dmrg.py`
- Modify: `src/lrtfim/__init__.py`
- Create: `tests/test_staged_dmrg.py`

**Interfaces:**
- Produce:
  `StagedStateResult(final: ParityStateResult, stages: list[StageResult])`
- Produce:
  `run_staged_sector(model, sector, chi_schedule, base_options, initial_psi=None, checkpoint_root=None, provenance=None) -> StagedStateResult`
- `StageResult` records requested/reached chi, energy, variance, discarded
  weight, sweeps, wall seconds, and checkpoint path.

- [ ] **Step 1: Write failing schedule tests**

  Reject non-increasing schedules, repeated chi, terminal chi different from
  128 in the benchmark protocol, and a starting checkpoint whose reached chi
  exceeds a lower requested stage without explicit skip behavior.

- [ ] **Step 2: Verify RED**

  Run the focused tests; expected missing-module failure.

- [ ] **Step 3: Implement stage chaining**

  For each chi in `(32, 64, 128)`, clone the shared options, change only
  `trunc_params["chi_max"]`, run the same sector, save a checkpoint, then feed
  the converged MPS to the next stage. Stop immediately if a stage is not
  converged; do not seed later stages from a failed state.

- [ ] **Step 4: Add L<=12 direct/staged/ED comparisons**

  Compare staged `(32,64,128)` with direct 128 for both parity sectors.
  Require:

  - non-increasing variational energy across stages;
  - final energy/gap agreement with direct DMRG and ED;
  - final variance and discarded weight satisfy the locked small-size gates;
  - full physical correlations agree with direct and ED fixtures.

- [ ] **Step 5: Verify GREEN**

  Run staged, checkpoint, continuation, and rotated-basis tests.

---

### Task 5: Fixed-grid continuation command and reverse-path audit

**Files:**
- Create: `src/lrtfim/continuation.py`
- Create: `scripts/run_phase6_continuation.py`
- Create: `tests/test_continuation_cli.py`
- Modify: `scripts/README.md`

**Interfaces:**
- Produce:
  `ContinuationPath(gammas, sector, chi_schedule, checkpoint_paths)`
- Produce:
  `compare_continuation_targets(forward, reverse) -> ContinuationComparison`
- CLI consumes an explicit ordered subset of the locked Gamma grid and never
  generates or refines Gamma values.

- [ ] **Step 1: Write failing fixed-grid tests**

  Require every requested Gamma to be present in `locked_gamma_grid()`.
  Reject `1.5595`, adaptive/refinement fields, sector mixing, or checkpoint
  provenance mismatches.

- [ ] **Step 2: Verify RED**

  Run the focused CLI test; expected missing command/module failure.

- [ ] **Step 3: Implement path execution**

  Each path runs one sector sequentially, atomically saves every state, and
  writes incremental JSON after each Gamma. Resume only success checkpoints
  with exact provenance matches.

- [ ] **Step 4: Implement comparison metrics**

  At the shared target Gamma report:

  - absolute even/odd energy shifts;
  - relative gap shift;
  - both paths' variance and discarded weight;
  - absolute `R_xi` shift;
  - maximum and RMS full-correlation shift.

  Apply the design thresholds without selecting a preferred direction.

- [ ] **Step 5: Add reduced DMRG-only path test**

  Exercise forward/reverse paths at small L and prove the CLI retains every
  checkpoint, raw observable, and convergence diagnostic.

- [ ] **Step 6: Verify GREEN**

  Run the continuation CLI and protocol tests.

---

### Task 6: Bounded local benchmarks

**Files:**
- Create: `scripts/benchmark_phase6_optimizations.py`
- Create: `tests/test_phase6_optimization_benchmark.py`
- Modify: `README.md`
- Modify: `docs/methodology.md`

**Interfaces:**
- CLI modes:
  `--fixture`, `--continuation-l16`, and `--runtime-l32`.
- Produce:
  `results/phase6_sigma1.75/optimization-benchmark/summary.json`,
  stage CSVs, continuation comparison JSON, and runtime comparison table.

- [ ] **Step 1: Write failing fixture test**

  Run `--fixture` at `L=8` and require direct/staged timings, sweeps, energy,
  variance, discarded weight, checkpoint paths, MPO dimensions, active
  channels, and raw observables.

- [ ] **Step 2: Verify RED**

  Run the focused test; expected missing command failure.

- [ ] **Step 3: Implement benchmark command**

  Use `time.perf_counter()` around setup, every DMRG stage, variance, and
  observable reconstruction. Flush one progress record after each stage and
  write summary JSON incrementally.

- [ ] **Step 4: Run L<=12 qualification**

  Run the full exact-reference gate first. Stop if checkpoint identity,
  pruning, continuation, staged chi, spectrum, or correlation validation
  fails.

- [ ] **Step 5: Cost-gate L=16 continuation**

  Time one reduced path step, estimate all four anchor/target sector solves,
  and run:

  ```text
  1.559 -> 1.560
  1.561 -> 1.560
  ```

  only if the estimated remaining local wall time stays within the local
  budget. Otherwise write `status="deferred_resource_limit"` with the timing
  evidence; do not weaken the comparison.

- [ ] **Step 6: Run one optimized L=32 benchmark**

  At Gamma 1.560, compare staged `(32,64,128)` with the existing direct-128
  baseline for runtime, total/per-stage sweeps, energy, gap, variance,
  discarded weight, `R_xi`, and correlations. Reuse saved checkpoints for
  observables; do not run a full L=32 continuation path.

- [ ] **Step 7: Update resource estimate**

  Scale the 72 fixed-chi production base cells by the measured optimized/direct
  L=32 ratio. Report higher-chi refinement separately as projected, not
  measured, unless a corresponding local stage was actually timed.

- [ ] **Step 8: Verify all outputs**

  Require every successful benchmark cell to contain complete raw observables,
  convergence diagnostics, checkpoint provenance, and timing records.

---

### Task 7: Full verification and production gate

**Files:**
- Modify: `results/phase6_sigma1.75/production-preparation.md`
- Modify: `results/phase6_sigma1.75/l32-runtime-profile.md`

**Interfaces:**
- Consume all preceding test and benchmark artifacts.
- Produce a final local qualification status:
  `ready_for_cluster_profile` or `blocked`, never automatic submission.

- [ ] **Step 1: Run the complete test suite**

  ```bash
  PYTHONPATH=src conda run -n mps python -m pytest -q
  ```

  Expected: zero failures.

- [ ] **Step 2: Run diff hygiene**

  ```bash
  git diff --check -- \
    tracks/mps/solutions/agent-of-my-agent-is-not-my-agent
  ```

- [ ] **Step 3: Audit protocol immutability**

  Compare the pre/post `locked_gamma_grid()` byte representation and run-spec
  Gamma list. Require exact equality and confirm no adaptive search field was
  added.

- [ ] **Step 4: Audit production enablement**

  Confirm pruning is enabled only after its dense/observable gate status is
  success; checkpoint mismatch is fail-closed; no approximate MPO compression
  call exists; and no Slurm job/result was created.

- [ ] **Step 5: Report**

  Report direct versus optimized L=32 runtime, sweeps, numerical agreement,
  actual MPO dimension, checkpoint evidence, any deferred L=16 test, and the
  updated production resource estimate.
