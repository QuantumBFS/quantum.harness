# Issue #28 Pure-Neural VMCRG Easy Goal Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Certify and execute the Issue #28 two-dimensional Easy Goal with a pure D4/Z2/translation-symmetric neural Hamiltonian, five paired formal seeds, and at least five consecutive neural-to-neural VMCRG rounds.

**Architecture:** Reuse the verified traditional VMCRG, neural energy, local-cache, validation, and statistical code. Add narrow modules for immutable protocols and hashes, exact small-lattice oracles, BAR objective estimation, explicit Robbins-Monro stopping, neural microscopic Hamiltonians, hash-linked checkpoints, and B0/N0/N1-N5 orchestration. Large 45 x 45 work runs through the existing Slurm harness after a measured pilot; MPS remains an optional comparison only.

**Tech Stack:** Python 3.12, NumPy float64, SciPy, Numba, JAX CPU for N0 automatic-differentiation oracle only, pytest, matplotlib, JSON protocols, Slurm through `scripts/harness_slurm.sh`.

## Global Constraints

- Frozen model: periodic 45 x 45 square-lattice Ising model, `K = 0.436`, 3 x 3 non-overlapping majority blocking, origin `(0, 0)`.
- Primary ansatz: radius-3, hidden-32, multiscale `D4EvenLocalMLP` with exact translation, D4, and Z2 symmetry.
- Pure-neural formal runs keep the 13-operator bias as an exact all-zero float64 vector at every boundary.
- Every RG handoff is `U_next = -V_frozen`; total energies drive Metropolis, reported objectives are normalized per applicable site count.
- Five preregistered formal seed bundles and at least five completed neural-to-neural rounds per successful seed are mandatory.
- Neural, traditional, and unbiased arms use paired initial conditions and matched budgets but independent mutable RNG states.
- Formal held-out objectives use a locked common zero-bias anchor and stratified BAR bridges; failed overlap is `UNIDENTIFIABLE_OVERLAP`.
- Formal training uses `eta_t = eta_0 (t + t_0)^(-p)`, explicit multi-condition stopping, gradient clipping, and Polyak averaging.
- No formal threshold, estimator, bridge ladder, seed, or optimizer setting changes after the first formal output exists.
- Local compute is limited to jobs estimated below 10 minutes and 16 GB. Larger work uses the active Slurm profile.
- Existing paper, neural, MPS, and LTRG evidence is preserved. Only generated caches and duplicated plan text may be removed.
- All user-facing CLI messages, progress summaries, plot labels, and report text use Simplified Chinese; internal APIs and JSON keys remain stable ASCII English.
- Before each compute stage, ratify the Hamiltonian, lattice, boundary, sector/reference, observable, and size in the stage manifest.

---

## File Map

### New focused modules

- `src/vmcrg_ref/artifacts.py`: canonical JSON, SHA-256, atomic JSON/NPZ, verified directory promotion.
- `src/vmcrg_ref/issue28_protocol.py`: protocol dataclasses, paired seed bundles, operator-basis record/hash, gauge-reference creation and validation.
- `src/vmcrg_ref/exact_oracle.py`: 3 x 6 exact blocking oracle and small square identity oracle.
- `src/vmcrg_ref/objective.py`: BAR, overlap diagnostics, chain jackknife, paired objective records.
- `src/vmcrg_ref/training_protocol.py`: literal Robbins-Monro schedule, clipping, monitoring windows, stopping state.
- `src/vmcrg_ref/neural_checkpoint.py`: pure-neural atomic checkpoint and fail-closed resume.
- `src/vmcrg_ref/neural_hamiltonian.py`: neural microscopic Hamiltonian, dual microscopic/coarse caches, reference/compiled samplers.
- `src/vmcrg_ref/issue28_workflow.py`: B0/N0/N1-N5 stage APIs, dependency checks, classification, manifests.

### New scripts and protocols

- `scripts/issue28_easy.py`: thin stage CLI called by `reproduce.py`.
- `scripts/issue28_report.py`: aggregate compact formal outputs and build report inputs.
- `src/vmcrg_ref/issue28_i18n.py`: Simplified-Chinese display labels for stages, classifications, gates, and CLI messages.
- `config/issue28_b0_v1.json`: traditional certification protocol.
- `config/issue28_n0_v1.json`: exact oracle and gradient tolerances.
- `config/issue28_pilot_v1.json`: non-formal optimizer/objective/resource pilot.
- `config/issue28_easy_v1.json`: umbrella dependency graph and immutable physical/statistical gates.
- `config/issue28_formal_v1.json`: generated and locked only after N3 pilot approval; contains literal schedules, bridges, resources, and five seed bundles.
- `jobs/issue28_smoke.slurm`: short environment and entry smoke without hard-coded partition selection.
- `jobs/issue28_round.slurm`: one seed/round job consuming a verified predecessor checkpoint.
- `jobs/issue28_measure.slurm`: paired objective/autocorrelation measurements.

### New tests

- `tests/test_artifacts.py`
- `tests/test_issue28_protocol.py`
- `tests/test_traditional_certification.py`
- `tests/test_exact_oracle.py`
- `tests/test_objective.py`
- `tests/test_training_protocol.py`
- `tests/test_neural_checkpoint.py`
- `tests/test_neural_hamiltonian.py`
- `tests/test_issue28_workflow.py`
- `tests/test_issue28_analysis.py`
- `tests/test_issue28_i18n.py`

### Existing files to modify

- `src/vmcrg_ref/exact.py`: retain current public helpers; re-export compatible oracle helpers only where useful.
- `src/vmcrg_ref/hybrid_neural.py`: consume the explicit schedule/clip/stop interfaces without duplicating them.
- `src/vmcrg_ref/neural_energy.py`: add deterministic parameter payload/hash helpers; preserve energy semantics.
- `src/vmcrg_ref/__init__.py`: export the new stable public interfaces.
- `scripts/neural_challenge.py`: route pure-neural training through the explicit training protocol and shared artifacts.
- `reproduce.py`: add `issue28-easy` orchestration and dry-run/through/backend/resume flags.
- `pyproject.toml`: rename the primary project description and add an oracle optional dependency group.
- `README.md`: make pure-neural Issue #28 the primary workflow and mark MPS optional.
- `PLAN.md`: replace the MPS plan with the canonical B0/N0/N1-N5 execution index.
- `docs/superpowers/plans/2026-07-28-mps-vmcrg-optional-comparison.md`: archived MPS plan with an explicit non-gating banner.

---

### Task 1: Shared Atomic Artifacts and Hashes

**Files:**
- Create: `src/vmcrg_ref/artifacts.py`
- Create: `tests/test_artifacts.py`
- Modify: `src/vmcrg_ref/__init__.py`

**Interfaces:**
- Produces: `canonical_json_bytes(value: object) -> bytes`
- Produces: `sha256_bytes(payload: bytes) -> str`
- Produces: `sha256_file(path: Path) -> str`
- Produces: `atomic_write_json(path: Path, value: object) -> None`
- Produces: `atomic_write_npz(path: Path, arrays: Mapping[str, np.ndarray]) -> None`
- Produces: `verified_promote_directory(staging: Path, final: Path, expected: Mapping[str, str]) -> None`

- [ ] **Step 1: Write failing canonicalization and atomicity tests**

```python
def test_canonical_json_hash_is_key_order_independent():
    left = sha256_bytes(canonical_json_bytes({"b": 2, "a": 1}))
    right = sha256_bytes(canonical_json_bytes({"a": 1, "b": 2}))
    assert left == right

def test_verified_promote_rejects_hash_mismatch(tmp_path):
    staging = tmp_path / "staging"
    staging.mkdir()
    (staging / "x.txt").write_text("actual", encoding="utf-8")
    with pytest.raises(ValueError, match="hash mismatch"):
        verified_promote_directory(staging, tmp_path / "final", {"x.txt": "0" * 64})
```

- [ ] **Step 2: Run tests and confirm missing-module failure**

Run: `../../../.venv/bin/python -m pytest tests/test_artifacts.py -q`

Expected: FAIL because `vmcrg_ref.artifacts` does not exist.

- [ ] **Step 3: Implement canonical serialization and fsync-backed atomic writers**

```python
def canonical_json_bytes(value: object) -> bytes:
    return (json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True) + "\n").encode("ascii")

def atomic_write_json(path: Path, value: object) -> None:
    payload = canonical_json_bytes(value)
    _atomic_bytes(path, payload)
```

Use a temporary file in the destination directory, flush, `os.fsync`, then `os.replace`. Refuse directory promotion when the final directory is nonempty.

- [ ] **Step 4: Run focused and existing artifact/checkpoint tests**

Run: `../../../.venv/bin/python -m pytest tests/test_artifacts.py tests/test_checkpoint_mps.py -q`

Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add tracks/mps/DMRG/src/vmcrg_ref/artifacts.py tracks/mps/DMRG/src/vmcrg_ref/__init__.py tracks/mps/DMRG/tests/test_artifacts.py
git commit -m "feat: add verified atomic artifacts"
```

### Task 2: Issue #28 Protocol, Basis Hash, Gauge Set, and Seed Bundles

**Files:**
- Create: `src/vmcrg_ref/issue28_protocol.py`
- Create: `tests/test_issue28_protocol.py`
- Create: `config/issue28_b0_v1.json`
- Create: `config/issue28_n0_v1.json`
- Create: `config/issue28_pilot_v1.json`
- Create: `config/issue28_easy_v1.json`
- Modify: `src/vmcrg_ref/neural_energy.py`
- Modify: `pyproject.toml`

**Interfaces:**
- Consumes: artifact helpers from Task 1.
- Produces: `SeedStream(entropy: int, spawn_key: tuple[int, ...])`
- Produces: `SeedBundle(bundle_id: str, streams: Mapping[str, SeedStream])`
- Produces: `Issue28Protocol`
- Produces: `load_issue28_protocol(path: Path) -> Issue28Protocol`
- Produces: `canonical_operator_basis_record(length: int = 15) -> dict`
- Produces: `operator_basis_sha256(length: int = 15) -> str`
- Produces: `create_gauge_reference(protocol: Issue28Protocol, output: Path) -> dict`
- Produces: `D4EvenLocalMLP.parameter_payload() -> dict[str, np.ndarray]`

- [ ] **Step 1: Write failing fail-closed protocol tests**

```python
def test_formal_bundle_streams_are_globally_unique():
    protocol = load_issue28_protocol(Path("config/issue28_easy_v1.json"))
    records = [(s.entropy, s.spawn_key) for b in protocol.formal_bundles for s in b.streams.values()]
    assert len(records) == len(set(records))

def test_pure_neural_linear_branch_is_exact_zero():
    protocol = load_issue28_protocol(Path("config/issue28_easy_v1.json"))
    assert np.array_equal(protocol.pure_linear_bias, np.zeros(13, dtype=np.float64))

def test_operator_basis_hash_changes_on_coordinate_change(monkeypatch):
    expected = operator_basis_sha256()
    monkeypatch.setattr(EVEN_SHAPES[0], "vertices", ((0, 0), (2, 0)))
    assert operator_basis_sha256() != expected
```

- [ ] **Step 2: Run tests and verify failure**

Run: `../../../.venv/bin/python -m pytest tests/test_issue28_protocol.py -q`

Expected: FAIL because the protocol module and files do not exist.

- [ ] **Step 3: Implement immutable dataclasses and literal config validation**

Validate exact physical values, five bundles, five rounds, zero bias, BAR gates, non-inferiority margins, terminal classifications, and required stream names. Store SeedSequence entropy and spawn keys explicitly.

```python
REQUIRED_STREAMS = (
    "initial_condition", "microscopic", "neural_training", "linear_training",
    "monitoring", "validation", "projection", "objective_anchor",
    "objective_neural", "objective_linear", "objective_target",
    "autocorrelation", "bootstrap",
)
```

- [ ] **Step 4: Implement canonical basis and gauge reference records**

The basis record includes operator name, ordered vertices, D4 orbit, arity, instance count at L=15, and sign convention. The gauge record contains generator, seed stream, shape, dtype, byte order, NPZ hash, and raw-array hash.

- [ ] **Step 5: Add JAX as an optional oracle dependency**

```toml
[project.optional-dependencies]
oracle = ["jax>=0.4"]
```

Keep the existing `make install jax` target as the supported installation path.

- [ ] **Step 6: Run focused tests and config validation**

Run: `../../../.venv/bin/python -m pytest tests/test_issue28_protocol.py tests/test_neural_replacement.py -q`

Expected: PASS.

- [ ] **Step 7: Commit**

```bash
git add tracks/mps/DMRG/src/vmcrg_ref/issue28_protocol.py tracks/mps/DMRG/src/vmcrg_ref/neural_energy.py tracks/mps/DMRG/src/vmcrg_ref/__init__.py tracks/mps/DMRG/config/issue28_*.json tracks/mps/DMRG/tests/test_issue28_protocol.py tracks/mps/DMRG/pyproject.toml
git commit -m "feat: lock issue 28 protocols and seeds"
```

### Task 3: B0 Traditional VMCRG Baseline Certification

**Files:**
- Create: `src/vmcrg_ref/baseline_certification.py`
- Create: `scripts/issue28_baseline.py`
- Create: `tests/test_traditional_certification.py`
- Modify: `src/vmcrg_ref/multi_optimizer.py`

**Interfaces:**
- Consumes: B0 protocol, operator basis hash, existing traditional optimizer/samplers.
- Produces: `certify_traditional_baseline(protocol: Issue28Protocol, output: Path) -> dict`
- Produces: `traditional_handoff_from_values(bias: np.ndarray, values: np.ndarray) -> np.ndarray`
- Produces: `traditional_handoff_energy(bias: np.ndarray, spins: np.ndarray, basis: OperatorBasis) -> np.ndarray`

- [ ] **Step 1: Write failing basis, handoff, convergence, and classification tests**

```python
def test_traditional_handoff_uses_negative_frozen_bias():
    bias = np.array([0.2, -0.1])
    values = np.array([[3.0, 4.0]])
    np.testing.assert_allclose(traditional_handoff_from_values(bias, values), -(values @ bias))

def test_b0_rejects_wrong_basis_hash(tmp_path):
    protocol = replace(load_issue28_protocol(PROTOCOL), operator_basis_sha256="0" * 64)
    with pytest.raises(ValueError, match="operator basis hash"):
        certify_traditional_baseline(protocol, tmp_path)
```

- [ ] **Step 2: Run focused tests to verify failure**

Run: `../../../.venv/bin/python -m pytest tests/test_traditional_certification.py -q`

- [ ] **Step 3: Add a callback-safe traditional trajectory export**

Extend `MultiOptimizationRecord` serialization without changing the optimizer equations. Record gradient norm, mean operators, covariance condition, instantaneous/running bias, acceptance, and wall time at flushed progress intervals.

- [ ] **Step 4: Implement B0 by composing existing verified scripts/APIs**

Reuse `MultiOperatorOptimizer`, frozen moment validation, paper anchor comparison, local-delta checks, and autocorrelation functions. Write `basis.json`, `trajectory.npz`, `convergence.json`, `frozen_validation.json`, `handoff.json`, `autocorrelation.json`, `resources.json`, and `manifest.json` atomically.

- [ ] **Step 5: Run a small smoke certification**

Run: `../../../.venv/bin/python scripts/issue28_baseline.py --protocol config/issue28_b0_v1.json --preset smoke --output /tmp/issue28-b0-smoke`

Expected: manifest classification is not a protocol/correctness failure; smoke is labelled statistically insufficient.

- [ ] **Step 6: Run focused plus legacy traditional tests**

Run: `../../../.venv/bin/python -m pytest tests/test_traditional_certification.py tests/test_core.py tests/test_local_operators_pytest.py tests/test_reproduce.py -q`

- [ ] **Step 7: Commit**

```bash
git add tracks/mps/DMRG/src/vmcrg_ref/baseline_certification.py tracks/mps/DMRG/src/vmcrg_ref/multi_optimizer.py tracks/mps/DMRG/scripts/issue28_baseline.py tracks/mps/DMRG/tests/test_traditional_certification.py
git commit -m "feat: certify the traditional VMCRG baseline"
```

### Task 4: N0 Exact Blocking and VMCRG Oracle

**Files:**
- Create: `src/vmcrg_ref/exact_oracle.py`
- Create: `scripts/issue28_exact_oracle.py`
- Create: `tests/test_exact_oracle.py`
- Modify: `src/vmcrg_ref/exact.py`

**Interfaces:**
- Produces: `ExactBlockingResult`
- Produces: `enumerate_rectangular_blocking(rows: int, cols: int, block_size: int, coupling: float) -> ExactBlockingResult`
- Produces: `exact_objective(result: ExactBlockingResult, bias_energy: np.ndarray, target_probability: np.ndarray) -> float`
- Produces: `exact_parameter_gradient(result: ExactBlockingResult, features: np.ndarray, parameters: np.ndarray, target_probability: np.ndarray) -> np.ndarray`

- [ ] **Step 1: Write failing 3 x 6 enumeration tests**

```python
def test_3x6_oracle_enumerates_every_microstate():
    result = enumerate_rectangular_blocking(3, 6, 3, 0.436)
    assert result.microstate_count == 2**18
    assert result.coarse_shape == (1, 2)
    np.testing.assert_allclose(result.coarse_probability.sum(), 1.0, atol=1e-15)

def test_exact_objective_gradient_matches_finite_difference():
    result = enumerate_rectangular_blocking(3, 6, 3, 0.436)
    features = result.coarse_nn[:, None]
    target = np.full(result.coarse_state_count, 1.0 / result.coarse_state_count)
    theta = np.array([0.1])
    grad = exact_parameter_gradient(result, features, theta, target)
    epsilon = 1e-6
    plus = exact_objective(result, features @ (theta + epsilon), target)
    minus = exact_objective(result, features @ (theta - epsilon), target)
    assert grad[0] == pytest.approx((plus - minus) / (2.0 * epsilon), abs=1e-8)
```

- [ ] **Step 2: Run and confirm missing implementation**

Run: `../../../.venv/bin/python -m pytest tests/test_exact_oracle.py -q`

- [ ] **Step 3: Implement chunked exact enumeration**

Enumerate all 18-bit states in bounded chunks, compute periodic rectangular Ising energy with each undirected bond counted once, apply explicit 3 x 3 majority blocks, aggregate exact coarse weights by log-sum-exp, and retain state-level arrays only when requested by N0.

- [ ] **Step 4: Implement exact objective, target distances, and gradients**

Use normalized exact probabilities; return total and per-coarse-site objective, TV, JS, operator moments, and gradient. Include a synthetic nonuniform target diagnostic solely to make bias-sign reversal observable.

- [ ] **Step 5: Run exact tests and current exact helpers**

Run: `../../../.venv/bin/python -m pytest tests/test_exact_oracle.py tests/test_core.py::ExactVariationalTests -q`

- [ ] **Step 6: Commit**

```bash
git add tracks/mps/DMRG/src/vmcrg_ref/exact_oracle.py tracks/mps/DMRG/src/vmcrg_ref/exact.py tracks/mps/DMRG/scripts/issue28_exact_oracle.py tracks/mps/DMRG/tests/test_exact_oracle.py
git commit -m "feat: add exact VMCRG blocking oracle"
```

### Task 5: N0 JAX Automatic-Differentiation Gradient Oracle

**Files:**
- Modify: `src/vmcrg_ref/exact_oracle.py`
- Modify: `scripts/issue28_exact_oracle.py`
- Modify: `tests/test_exact_oracle.py`

**Interfaces:**
- Produces: `jax_exact_neural_gradient(states: np.ndarray, probabilities: np.ndarray, target_states: np.ndarray, model: D4EvenLocalMLP) -> np.ndarray`
- Produces: `flatten_mlp_gradient(gradient: MLPGradient) -> np.ndarray`
- Produces: `compare_small_neural_gradients(length: int, radius: int, hidden: int, seed: int) -> dict`

- [ ] **Step 1: Install the supported CPU JAX oracle stack**

Run: `make install jax EXTRA=cpu` from the repository root.

Expected: `.venv/bin/python -c 'import jax; print(jax.devices())'` shows a CPU device.

- [ ] **Step 2: Write failing five-way gradient comparison**

```python
def test_small_identity_oracle_gradients_agree():
    report = compare_small_neural_gradients(length=3, radius=1, hidden=3, seed=2026072801)
    assert report["jax_vs_analytic_linf"] <= 1e-9
    assert report["jax_vs_finite_difference_linf"] <= 1e-6
    assert report["exact_vs_mc_all_z_below"]
```

- [ ] **Step 3: Implement a pure JAX reduced MLP objective**

Mirror `D4EvenLocalMLP` density exactly for radius 1, including D4/Z2 averaging and total-energy summation. Use `jax.grad` only in the oracle module; do not change production inference to JAX.

- [ ] **Step 4: Add Monte Carlo statistical comparison**

Use preregistered independent chains, chain-level standard errors, and a Bonferroni maximum-z gate. Compare sign and normalization explicitly.

- [ ] **Step 5: Run N0 and full neural gradient tests**

Run: `../../../.venv/bin/python -m pytest tests/test_exact_oracle.py tests/test_neural.py tests/test_neural_identity_gradient_diagnostic.py -q`

- [ ] **Step 6: Commit**

```bash
git add tracks/mps/DMRG/src/vmcrg_ref/exact_oracle.py tracks/mps/DMRG/scripts/issue28_exact_oracle.py tracks/mps/DMRG/tests/test_exact_oracle.py
git commit -m "test: certify neural gradients with exact JAX oracle"
```

### Task 6: Frozen BAR Held-Out Objective Estimator

**Files:**
- Create: `src/vmcrg_ref/objective.py`
- Create: `tests/test_objective.py`
- Modify: `config/issue28_pilot_v1.json`

**Interfaces:**
- Produces: `ObjectiveProtocol`
- Produces: `ChainSet`
- Produces: `BarIntervalResult`
- Produces: `ObjectiveResult`
- Produces: `PairedObjectiveResult`
- Produces: `bar_free_energy_difference(work_forward: np.ndarray, work_reverse: np.ndarray, *, root_tolerance: float) -> BarIntervalResult`
- Produces: `bridge_objective(anchor: ChainSet, bridges: Sequence[ChainSet], target_energies: ChainSet, protocol: ObjectiveProtocol) -> ObjectiveResult`
- Produces: `paired_objective_difference(neural: ObjectiveResult, linear: ObjectiveResult) -> PairedObjectiveResult`
- Produces: `chain_jackknife(values: np.ndarray, chain_axis: int = 0) -> dict`

- [ ] **Step 1: Write failing analytic BAR and overlap tests**

```python
def test_bar_recovers_two_state_free_energy():
    exact = np.log((1.0 + np.exp(-1.0)) / 2.0)
    result = bar_from_exact_two_state_ensembles(delta_energy=np.array([0.0, 1.0]))
    assert result.delta_log_z == pytest.approx(exact, abs=1e-10)

def test_failed_overlap_is_unidentifiable():
    result = bar_free_energy_difference(np.full(100, 1000.0), np.full(100, -1000.0), root_tolerance=1e-12)
    assert result.classification == "UNIDENTIFIABLE_OVERLAP"
```

- [ ] **Step 2: Run tests and confirm missing module**

Run: `../../../.venv/bin/python -m pytest tests/test_objective.py -q`

- [ ] **Step 3: Implement stable BAR and diagnostics**

Use `scipy.optimize.brentq`, `np.logaddexp`, BAR overlap `>=0.03`, forward/reverse Kish ESS fractions `>=0.10`, and closure disagreement `<=3` combined SE. Return the failed interval and reason instead of a favourable numeric fallback.

- [ ] **Step 4: Implement common-anchor pairing and chain jackknife**

The neural and linear records must reference the same anchor hash but different nonzero bridge-stream hashes. Reject mismatched anchors and any measurement-level jackknife request.

- [ ] **Step 5: Add hierarchical bootstrap unit tests**

Use a synthetic five-seed, four-chain fixture with a known paired shift. Assert seed-level pairing occurs before bootstrap aggregation.

- [ ] **Step 6: Run focused and existing ablation/statistics tests**

Run: `../../../.venv/bin/python -m pytest tests/test_objective.py tests/test_neural_confirmation.py tests/test_neural_three_arm.py -q`

- [ ] **Step 7: Commit**

```bash
git add tracks/mps/DMRG/src/vmcrg_ref/objective.py tracks/mps/DMRG/tests/test_objective.py tracks/mps/DMRG/config/issue28_pilot_v1.json
git commit -m "feat: freeze BAR objective estimation"
```

### Task 7: Literal Robbins-Monro Schedule, Clipping, and Multi-Gate Stopping

**Files:**
- Create: `src/vmcrg_ref/training_protocol.py`
- Create: `tests/test_training_protocol.py`
- Modify: `src/vmcrg_ref/hybrid_neural.py`
- Modify: `scripts/neural_challenge.py`

**Interfaces:**
- Produces: `RobbinsMonroSchedule(eta_0: float, t_0: float, p: float)` with `rate(update: int) -> float`
- Produces: `TrainingStopConfig`
- Produces: `TrainingWindow`
- Produces: `TrainingStopState.observe(window: TrainingWindow) -> str | None`
- Produces: `clip_mlp_gradient(gradient: MLPGradient, max_norm: float) -> tuple[MLPGradient, float, float]`

- [ ] **Step 1: Write failing literal-rate and stop-conjunction tests**

```python
def test_robbins_monro_uses_literal_formula():
    schedule = RobbinsMonroSchedule(eta_0=2.0, t_0=4.0, p=0.75)
    assert schedule.rate(0) == pytest.approx(2.0 * 4.0**-0.75)
    assert schedule.rate(10) == pytest.approx(2.0 * 14.0**-0.75)

def test_stop_requires_every_monitor_gate():
    state = TrainingStopState(config_with_patience(3))
    for _ in range(3):
        assert state.observe(passing_window(parameter_drift=1.0)) is None
```

- [ ] **Step 2: Run tests to verify failure**

Run: `../../../.venv/bin/python -m pytest tests/test_training_protocol.py -q`

- [ ] **Step 3: Implement schedule, finite checks, clipping, and stopping state**

Formal configuration rejects omitted values. A max-update exit without the conjunction returns `NOT_CONVERGED`. Nonfinite parameters or gradients return `CORRECTNESS_FAILURE` immediately.

- [ ] **Step 4: Integrate without changing legacy Adam behavior**

Add a new explicit training-protocol path to `HybridNeuralVMCRGOptimizer.run`; preserve old call signatures for historical reproduction commands. Log monitoring objective, gradient bounds, operator-equivalence, patch-TV, function drift, clipped/unclipped norm, and stop reason.

- [ ] **Step 5: Run focused optimizer and legacy neural tests**

Run: `../../../.venv/bin/python -m pytest tests/test_training_protocol.py tests/test_neural.py tests/test_neural_replacement.py tests/test_neural_confirmation.py -q`

- [ ] **Step 6: Commit**

```bash
git add tracks/mps/DMRG/src/vmcrg_ref/training_protocol.py tracks/mps/DMRG/src/vmcrg_ref/hybrid_neural.py tracks/mps/DMRG/scripts/neural_challenge.py tracks/mps/DMRG/tests/test_training_protocol.py
git commit -m "feat: lock neural stochastic training"
```

### Task 8: Pure-Neural Checkpoint and Fail-Closed Resume

**Files:**
- Create: `src/vmcrg_ref/neural_checkpoint.py`
- Create: `tests/test_neural_checkpoint.py`

**Interfaces:**
- Produces: `NeuralCheckpoint`
- Produces: `CheckpointExpectations`
- Produces: `save_neural_checkpoint(directory: Path, checkpoint: NeuralCheckpoint) -> dict`
- Produces: `load_neural_checkpoint(directory: Path, expected: CheckpointExpectations) -> NeuralCheckpoint`

- [ ] **Step 1: Write failing round-trip, mismatch, and interrupted-write tests**

```python
def test_checkpoint_rejects_protocol_hash_mismatch(tmp_path):
    save_neural_checkpoint(tmp_path / "ckpt", example_checkpoint(protocol_hash="a" * 64))
    with pytest.raises(ValueError, match="protocol hash"):
        load_neural_checkpoint(tmp_path / "ckpt", expectations(protocol_hash="b" * 64))

def test_partial_staging_directory_is_not_resumable(tmp_path):
    (tmp_path / "ckpt.staging").mkdir()
    with pytest.raises(FileNotFoundError):
        load_neural_checkpoint(tmp_path / "ckpt", expectations())
```

- [ ] **Step 2: Run and confirm missing module**

Run: `../../../.venv/bin/python -m pytest tests/test_neural_checkpoint.py -q`

- [ ] **Step 3: Implement checkpoint schema v1**

Store model arrays, schedule/update state, Polyak accumulators, RNG bit-generator states, round/bundle IDs, predecessor manifest hash, protocol/code/basis/gauge hashes, stop state, and metadata. Write into a staging directory and promote only after every file hash verifies.

- [ ] **Step 4: Verify deterministic save/load energy behavior**

Use the gauge set to assert the loaded model energy vector differs from the saved vector by at most one constant with residual `<=1e-10`.

- [ ] **Step 5: Run checkpoint and artifact suites**

Run: `../../../.venv/bin/python -m pytest tests/test_neural_checkpoint.py tests/test_artifacts.py tests/test_checkpoint_mps.py -q`

- [ ] **Step 6: Commit**

```bash
git add tracks/mps/DMRG/src/vmcrg_ref/neural_checkpoint.py tracks/mps/DMRG/tests/test_neural_checkpoint.py
git commit -m "feat: add fail-closed neural checkpoints"
```

### Task 9: Neural Microscopic Hamiltonian and Dual-Cache Sampler

**Files:**
- Create: `src/vmcrg_ref/neural_hamiltonian.py`
- Create: `tests/test_neural_hamiltonian.py`
- Modify: `src/vmcrg_ref/neural_energy.py`

**Interfaces:**
- Produces: `NeuralHamiltonian(model: D4EvenLocalMLP)` with `energy`, `proposal`, `commit`, `assert_consistent`
- Produces: `NeuralToNeuralBiasedMetropolis`
- Produces: `NeuralToNeuralProposal`

- [ ] **Step 1: Write failing local-delta and long-drift tests**

```python
def test_neural_micro_delta_matches_full_energy():
    sampler = make_reference_neural_to_neural_sampler(seed=10)
    proposal = sampler.proposal_delta(7, 9)
    trial = sampler.spins.copy(); trial[7, 9] *= -1
    assert sampler.full_effective_energy(trial) - sampler.effective_energy == pytest.approx(proposal.delta_total, abs=1e-10)

def test_dual_caches_do_not_drift_after_10000_proposals():
    sampler = make_reference_neural_to_neural_sampler(seed=11)
    sampler.run_proposals(10_000)
    sampler.assert_cache_consistent(atol=1e-10)
```

- [ ] **Step 2: Run and confirm missing implementation**

Run: `../../../.venv/bin/python -m pytest tests/test_neural_hamiltonian.py -q`

- [ ] **Step 3: Implement reference dual-cache proposal/commit**

For a microscopic flip, update the microscopic neural receptive fields, propagate the possible majority-block change, then update the coarse neural-bias receptive fields. Proposal is side-effect free; commit applies both caches atomically.

- [ ] **Step 4: Implement compiled trajectory-equivalent path**

Use the existing Numba density kernel and precomputed incidence arrays. Feed pre-generated uniform random values to reference and compiled paths so identical trajectories are testable.

- [ ] **Step 5: Add gauge and serialization handoff test**

Save round-r bias, load as round-(r+1) microscopic Hamiltonian, evaluate a fixed configuration set, fit one constant, and require maximum residual `<=1e-10`.

- [ ] **Step 6: Run neural sampler suites**

Run: `../../../.venv/bin/python -m pytest tests/test_neural_hamiltonian.py tests/test_neural.py -q`

- [ ] **Step 7: Commit**

```bash
git add tracks/mps/DMRG/src/vmcrg_ref/neural_hamiltonian.py tracks/mps/DMRG/src/vmcrg_ref/neural_energy.py tracks/mps/DMRG/tests/test_neural_hamiltonian.py
git commit -m "feat: add neural-to-neural VMCRG sampler"
```

### Task 10: Issue #28 Workflow, Manifests, and Classifications

**Files:**
- Create: `src/vmcrg_ref/issue28_workflow.py`
- Create: `tests/test_issue28_workflow.py`
- Modify: `src/vmcrg_ref/__init__.py`

**Interfaces:**
- Produces: `StageName = Literal["B0", "N0", "N1", "N2", "N3", "N4", "N5"]`
- Produces: `RunClassification = Literal["CORRECTNESS_FAILURE", "PROTOCOL_FAILURE", "SCIENTIFIC_NEGATIVE", "EASY_GOAL_SUCCESS"]`
- Produces: `run_stage(stage: StageName, protocol: Issue28Protocol, output: Path, backend: str, resume: bool) -> dict`
- Produces: `verify_stage_dependencies(stage: StageName, root: Path, protocol: Issue28Protocol) -> list[dict]`

- [ ] **Step 1: Write failing dependency and classification tests**

```python
def test_n1_refuses_to_run_without_passing_b0_and_n0(tmp_path):
    with pytest.raises(ValueError, match="B0"):
        verify_stage_dependencies("N1", tmp_path, protocol())

def test_scientific_failure_continues_to_n5_report(tmp_path):
    write_verified_manifest(tmp_path, "N4", classification="SCIENTIFIC_NEGATIVE")
    assert verify_stage_dependencies("N5", tmp_path, protocol())
```

- [ ] **Step 2: Run and confirm missing module**

Run: `../../../.venv/bin/python -m pytest tests/test_issue28_workflow.py -q`

- [ ] **Step 3: Implement hash-linked manifests and dependency gates**

Every manifest records stage, bundle, round, predecessor hashes, protocol/code/basis/gauge hashes, physical setup, resources, outputs, correctness gates, scientific gates, and classification.

- [ ] **Step 4: Implement stage dispatch with safe scientific-negative continuation**

Correctness/protocol failures block dependent compute. Scientific negatives block success claims but permit N5 aggregation/reporting.

- [ ] **Step 5: Run focused workflow tests**

Run: `../../../.venv/bin/python -m pytest tests/test_issue28_workflow.py tests/test_issue28_protocol.py -q`

- [ ] **Step 6: Commit**

```bash
git add tracks/mps/DMRG/src/vmcrg_ref/issue28_workflow.py tracks/mps/DMRG/src/vmcrg_ref/__init__.py tracks/mps/DMRG/tests/test_issue28_workflow.py
git commit -m "feat: orchestrate issue 28 stage dependencies"
```

### Task 11: N1 Random-Initialization Identity Certification

**Files:**
- Create: `scripts/issue28_identity.py`
- Create: `tests/test_issue28_identity.py`
- Modify: `docs/superpowers/plans/2026-07-27-neural-identity-random-convergence.md`

**Interfaces:**
- Consumes: explicit training protocol, exact identity oracle, checkpoints, workflow manifests.
- Produces: `run_identity_certification(protocol: Issue28Protocol, preset: str, output: Path) -> dict`

- [ ] **Step 1: Write failing random-start and no-supervised-checkpoint tests**

```python
def test_identity_formal_starts_from_protocol_random_model(monkeypatch, tmp_path):
    report = run_identity_certification(smoke_protocol(), "smoke", tmp_path)
    assert report["initialization"] == "random"
    assert report["supervised_checkpoint"] is None
```

- [ ] **Step 2: Run and verify failure**

Run: `../../../.venv/bin/python -m pytest tests/test_issue28_identity.py -q`

- [ ] **Step 3: Implement smoke/pilot/formal identity runner**

Use block size 1, the pure multiscale network, exact zero linear branch, separate monitoring/final streams, checkpoint/resume, and the N0 exact relation. Pilot seeds are disjoint; formal identity uses three locked seeds.

- [ ] **Step 4: Add gradient-oracle failure classification**

If frozen projection misses the gate, run the existing Metropolis/importance gradient diagnostic with a new diagnostic stream and classify convergence versus estimator noise without changing training settings.

- [ ] **Step 5: Run smoke and tests**

Run: `../../../.venv/bin/python scripts/issue28_identity.py --protocol config/issue28_pilot_v1.json --preset smoke --output /tmp/issue28-n1-smoke`

Run: `../../../.venv/bin/python -m pytest tests/test_issue28_identity.py tests/test_neural_identity_gradient_diagnostic.py tests/test_neural_supervised_identity.py -q`

- [ ] **Step 6: Commit**

```bash
git add tracks/mps/DMRG/scripts/issue28_identity.py tracks/mps/DMRG/tests/test_issue28_identity.py tracks/mps/DMRG/docs/superpowers/plans/2026-07-27-neural-identity-random-convergence.md
git commit -m "feat: certify random-start neural identity RG"
```

### Task 12: N2 One-Round 45 x 45 Pure-Neural RG

**Files:**
- Create: `scripts/issue28_one_round.py`
- Create: `tests/test_issue28_one_round.py`
- Modify: `scripts/neural_challenge.py`

**Interfaces:**
- Produces: `run_one_round(protocol: Issue28Protocol, bundle: SeedBundle, preset: str, output: Path) -> dict`

- [ ] **Step 1: Write failing zero-branch, paired-budget, and manifest tests**

```python
def test_one_round_checkpoint_has_exact_zero_linear_branch(tmp_path):
    report = run_one_round(smoke_protocol(), smoke_bundle(), "smoke", tmp_path)
    assert report["fixed_linear_bias_linf"] == 0.0
    assert report["manifest"]["round"] == 1
```

- [ ] **Step 2: Run and verify failure**

Run: `../../../.venv/bin/python -m pytest tests/test_issue28_one_round.py -q`

- [ ] **Step 3: Implement N2 by composing current train/validate/project APIs**

Replace the old fixed-step-only path with Task 7 monitoring. Add candidate-26 diagnostics, BAR objective, gauge-centered handoff, resources, and classification. Final objective/validation streams are never used for stopping.

- [ ] **Step 4: Run short L=21 connectivity smoke**

Run: `../../../.venv/bin/python scripts/issue28_one_round.py --protocol config/issue28_pilot_v1.json --preset smoke --output /tmp/issue28-n2-smoke`

Expected: complete manifest, no correctness/protocol failure, explicitly not formal.

- [ ] **Step 5: Run focused and legacy pure-neural tests**

Run: `../../../.venv/bin/python -m pytest tests/test_issue28_one_round.py tests/test_neural_replacement.py tests/test_neural_confirmation.py -q`

- [ ] **Step 6: Commit**

```bash
git add tracks/mps/DMRG/scripts/issue28_one_round.py tracks/mps/DMRG/scripts/neural_challenge.py tracks/mps/DMRG/tests/test_issue28_one_round.py
git commit -m "feat: run one-round pure-neural VMCRG"
```

### Task 13: N3 Five-Round Pilot, Resource Record, and Power Estimate

**Files:**
- Create: `scripts/issue28_five_round.py`
- Create: `src/vmcrg_ref/power.py`
- Create: `tests/test_issue28_five_round.py`
- Create: `tests/test_issue28_analysis.py`

**Interfaces:**
- Produces: `run_five_round_chain(protocol: Issue28Protocol, bundle: SeedBundle, output: Path, backend: str, resume: bool) -> dict`
- Produces: `estimate_five_seed_power(pilot_effects: np.ndarray, pilot_chain_variances: np.ndarray, bootstrap_seed: int) -> dict`

- [ ] **Step 1: Write failing five-round dependency and power tests**

```python
def test_round_two_consumes_round_one_manifest_hash(tmp_path):
    report = run_five_round_chain(smoke_protocol(rounds=2), smoke_bundle(), tmp_path, "local", False)
    assert report["rounds"][1]["predecessor_manifest_sha256"] == report["rounds"][0]["manifest_sha256"]

def test_power_report_never_recommends_postformal_seed_addition():
    report = estimate_five_seed_power(np.array([-1.0, -0.5]), np.array([1.0, 1.2]), 7)
    assert report["formal_seed_count"] == 5
    assert report["postformal_seed_extension_allowed"] is False
```

- [ ] **Step 2: Run and verify failure**

Run: `../../../.venv/bin/python -m pytest tests/test_issue28_five_round.py tests/test_issue28_analysis.py -q`

- [ ] **Step 3: Implement resumable five-round chain**

Round zero uses Ising; later rounds load the predecessor neural checkpoint as `U_r`. Each round writes training, validation, objective, projection, gauge, resource, checkpoint, and manifest artifacts before release.

- [ ] **Step 4: Implement resource and output accounting**

Record elapsed wall, CPU, thread count, peak RSS, checkpoint bytes, logs bytes, compact output bytes, proposals/s, sweeps/s, and estimated formal total. Flush progress 10-50 times per round.

- [ ] **Step 5: Implement fixed-five-seed power description**

Bootstrap pilot seed/chain effects to report expected CI width and estimated probability of crossing each gate. Always include the valid-negative caveat and never mutate the formal seed count.

- [ ] **Step 6: Run a two-round local smoke and tests**

Run: `../../../.venv/bin/python scripts/issue28_five_round.py --protocol config/issue28_pilot_v1.json --preset smoke --rounds 2 --output /tmp/issue28-n3-smoke`

Run: `../../../.venv/bin/python -m pytest tests/test_issue28_five_round.py tests/test_issue28_analysis.py tests/test_neural_hamiltonian.py -q`

- [ ] **Step 7: Commit**

```bash
git add tracks/mps/DMRG/scripts/issue28_five_round.py tracks/mps/DMRG/src/vmcrg_ref/power.py tracks/mps/DMRG/tests/test_issue28_five_round.py tracks/mps/DMRG/tests/test_issue28_analysis.py
git commit -m "feat: add five-round neural VMCRG pilot"
```

### Task 14: Freeze the Formal Protocol After N3

**Files:**
- Create: `scripts/freeze_issue28_formal_protocol.py`
- Create: `tests/test_issue28_formal_protocol.py`
- Create after pilot: `config/issue28_formal_v1.json`

**Interfaces:**
- Produces: `freeze_formal_protocol(umbrella: Path, pilot_manifest: Path, output: Path) -> dict`

- [ ] **Step 1: Write failing protocol-freeze tests**

```python
def test_formal_protocol_cannot_be_frozen_without_passing_pilot(tmp_path):
    with pytest.raises(ValueError, match="N3 pilot"):
        freeze_formal_protocol(UMBRELLA, failing_pilot_manifest(tmp_path), tmp_path / "formal.json")

def test_formal_protocol_contains_literal_bridges_training_and_resources(tmp_path):
    value = freeze_formal_protocol(UMBRELLA, passing_pilot_manifest(tmp_path), tmp_path / "formal.json")
    assert value["training"]["eta_0"] > 0
    assert value["objective"]["neural_lambda_ladder"][0] == 0.0
    assert value["objective"]["neural_lambda_ladder"][-1] == 1.0
    assert len(value["formal_seed_bundles"]) == 5
```

- [ ] **Step 2: Run and verify failure**

Run: `../../../.venv/bin/python -m pytest tests/test_issue28_formal_protocol.py -q`

- [ ] **Step 3: Implement deterministic freeze logic**

Consume only approved pilot fields: chosen bridge ladders, sample counts, literal `eta_0/t_0/p`, stopping thresholds, gradient clip, Polyak window, wall/memory request, five predeclared bundles, operator/gauge/code hashes, and power caveat. Refuse to overwrite an existing formal protocol.

- [ ] **Step 4: Validate protocol hash stability**

Run freeze twice into two empty temporary paths and assert byte-identical JSON and identical SHA-256.

- [ ] **Step 5: Run tests and commit the freezer**

Run: `../../../.venv/bin/python -m pytest tests/test_issue28_formal_protocol.py tests/test_issue28_protocol.py -q`

```bash
git add tracks/mps/DMRG/scripts/freeze_issue28_formal_protocol.py tracks/mps/DMRG/tests/test_issue28_formal_protocol.py
git commit -m "feat: freeze issue 28 formal protocol"
```

- [ ] **Step 6: After the measured pilot, generate and commit the immutable formal protocol**

Run: `../../../.venv/bin/python scripts/freeze_issue28_formal_protocol.py --umbrella config/issue28_easy_v1.json --pilot results/issue28/pilot/manifest.json --output config/issue28_formal_v1.json`

Verify: `git diff --check -- config/issue28_formal_v1.json` and protocol validator PASS.

Commit only the generated protocol and its compact pilot/power evidence.

### Task 15: N4 Formal Paired Five-Seed/Five-Round Orchestration

**Files:**
- Create: `scripts/issue28_formal.py`
- Create: `tests/test_issue28_formal.py`
- Modify: `src/vmcrg_ref/issue28_workflow.py`

**Interfaces:**
- Produces: `run_formal_bundle(protocol: Issue28Protocol, bundle_id: str, output: Path, backend: str, resume: bool) -> dict`
- Produces: `classify_formal_root(root: Path, protocol: Issue28Protocol) -> dict`

- [ ] **Step 1: Write failing paired-arm and no-replacement tests**

```python
def test_formal_arms_share_initial_hash_but_not_rng_stream(tmp_path):
    manifest = build_formal_smoke_manifest(tmp_path)
    assert manifest["neural"]["initial_state_sha256"] == manifest["linear"]["initial_state_sha256"]
    assert manifest["neural"]["rng_stream"] != manifest["linear"]["rng_stream"]

def test_missing_formal_seed_is_not_replaced():
    result = classify_formal_fixture(missing_bundle="formal-3")
    assert result["replacement_seed_allowed"] is False
```

- [ ] **Step 2: Run and verify failure**

Run: `../../../.venv/bin/python -m pytest tests/test_issue28_formal.py -q`

- [ ] **Step 3: Implement one-bundle orchestration**

Train paired traditional and neural arms from copied initial states under matched budgets/hardware. Run five dependent rounds, bridge objectives, final validation, projections, and autocorrelation. Preserve all outcomes.

- [ ] **Step 4: Implement root classification**

Require exactly the five protocol bundles. Distinguish correctness, protocol, scientific negative, and success. `UNIDENTIFIABLE_OVERLAP` is scientific negative when protocols/correctness otherwise hold.

- [ ] **Step 5: Run formal dry-run and tests**

Run: `../../../.venv/bin/python scripts/issue28_formal.py --protocol config/issue28_formal_v1.json --dry-run --output results/issue28/formal`

Run: `../../../.venv/bin/python -m pytest tests/test_issue28_formal.py tests/test_issue28_workflow.py -q`

- [ ] **Step 6: Commit**

```bash
git add tracks/mps/DMRG/scripts/issue28_formal.py tracks/mps/DMRG/src/vmcrg_ref/issue28_workflow.py tracks/mps/DMRG/tests/test_issue28_formal.py
git commit -m "feat: orchestrate paired formal issue 28 runs"
```

### Task 16: Unified Fresh-Checkout Entry

**Files:**
- Create: `scripts/issue28_easy.py`
- Create: `src/vmcrg_ref/issue28_i18n.py`
- Create: `tests/test_issue28_entry.py`
- Create: `tests/test_issue28_i18n.py`
- Modify: `reproduce.py`

**Interfaces:**
- Produces CLI: `python reproduce.py issue28-easy --protocol PATH [--stage STAGE|--through STAGE] [--backend local|slurm] [--resume] [--dry-run]`
- Produces: `run_issue28(protocol: Path, *, stage: str | None, through: str | None, backend: str, resume: bool, dry_run: bool, output: Path) -> dict`
- Produces: `display_label(code: str) -> str`

- [ ] **Step 1: Write failing parser and order tests**

```python
def test_issue28_entry_defaults_to_full_dependency_order():
    args = reproduce.build_parser().parse_args(["issue28-easy", "--dry-run"])
    assert args.stage_order == ["B0", "N0", "N1", "N2", "N3", "N4", "N5"]

def test_formal_local_backend_refuses_large_estimate(tmp_path):
    with pytest.raises(ValueError, match="Slurm"):
        run_issue28(large_formal_protocol(), through="N4", backend="local", output=tmp_path)

def test_every_terminal_classification_has_simplified_chinese_label():
    assert display_label("EASY_GOAL_SUCCESS") == "二维简易目标成功"
    assert display_label("SCIENTIFIC_NEGATIVE") == "科学结论未通过"
```

- [ ] **Step 2: Run and verify parser failure**

Run: `../../../.venv/bin/python -m pytest tests/test_issue28_entry.py -q`

- [ ] **Step 3: Implement thin orchestration**

The script validates setup, prints/records the exact physical card, dispatches `run_stage`, respects dependencies, and reports planned commands in dry-run. It does not duplicate stage algorithms.

All visible parser help, progress, stage names, gate summaries, and terminal
classification labels use `issue28_i18n.py`. Machine-readable codes and JSON
keys remain English.

- [ ] **Step 4: Add fresh-checkout setup diagnostics**

Check root `.venv`, JAX for N0, protocol/gauge/operator hashes, active cluster profile for Slurm, and output emptiness. Error messages name `make skills` and `make install jax EXTRA=cpu` where applicable.

- [ ] **Step 5: Run entry and regression tests**

Run: `../../../.venv/bin/python reproduce.py issue28-easy --protocol config/issue28_easy_v1.json --through N0 --dry-run`

Run: `../../../.venv/bin/python -m pytest tests/test_issue28_entry.py tests/test_issue28_i18n.py tests/test_reproduce.py -q`

- [ ] **Step 6: Commit**

```bash
git add tracks/mps/DMRG/scripts/issue28_easy.py tracks/mps/DMRG/src/vmcrg_ref/issue28_i18n.py tracks/mps/DMRG/reproduce.py tracks/mps/DMRG/tests/test_issue28_entry.py tracks/mps/DMRG/tests/test_issue28_i18n.py
git commit -m "feat: add unified issue 28 runner"
```

### Task 17: Slurm Smoke, Round Jobs, Monitoring, and Fetch

**Files:**
- Create: `jobs/issue28_smoke.slurm`
- Create: `jobs/issue28_round.slurm`
- Create: `jobs/issue28_measure.slurm`
- Create: `tests/test_issue28_slurm.py`
- Modify: `scripts/issue28_easy.py`

**Interfaces:**
- Consumes: active cluster profile and `scripts/harness_slurm.sh`.
- Produces: profile-neutral job templates with `HARNESS_*` environment inputs.

- [ ] **Step 1: Write failing template safety tests**

```python
def test_issue28_jobs_do_not_hardcode_partition():
    for path in JOBS:
        assert "#SBATCH --partition=" not in path.read_text()

def test_round_job_requires_bundle_round_and_protocol():
    text = Path("jobs/issue28_round.slurm").read_text()
    assert 'HARNESS_BUNDLE_ID:?' in text
    assert 'HARNESS_ROUND:?' in text
    assert 'HARNESS_PROTOCOL:?' in text
```

- [ ] **Step 2: Run and verify missing templates**

Run: `../../../.venv/bin/python -m pytest tests/test_issue28_slurm.py -q`

- [ ] **Step 3: Implement profile-neutral templates**

Templates set `set -euo pipefail`, flushed Python, thread limits, writable Numba/Matplotlib caches, per-round output/log paths, and atomic manifests. Partition, GRES, CPU, memory, and wall flags come from the active profile/harness submission command.

- [ ] **Step 4: Add dry-run Slurm command generation**

Generate `harness_slurm.sh precheck`, `probe-partitions`, `submit --test-only`, real submit, status, fetch, classify, and pending-cells commands. Do not submit until the test-only request and queue estimate are ratified under `using-slurm`.

- [ ] **Step 5: Run template and dry-run tests**

Run: `../../../.venv/bin/python -m pytest tests/test_issue28_slurm.py tests/test_issue28_entry.py -q`

- [ ] **Step 6: Commit**

```bash
git add tracks/mps/DMRG/jobs/issue28_*.slurm tracks/mps/DMRG/scripts/issue28_easy.py tracks/mps/DMRG/tests/test_issue28_slurm.py
git commit -m "feat: add profile-driven issue 28 Slurm jobs"
```

### Task 18: N5 Paired Analysis, Figures, and Challenge Report

**Files:**
- Create: `scripts/issue28_report.py`
- Create: `tests/test_issue28_report.py`
- Modify: `README.md`

**Interfaces:**
- Produces: `build_issue28_report(root: Path, protocol: Issue28Protocol) -> dict`

- [ ] **Step 1: Write failing classification and figure-source tests**

```python
def test_report_preserves_scientific_negative(tmp_path):
    report = build_issue28_report(scientific_negative_fixture(tmp_path), protocol())
    assert report["classification"] == "SCIENTIFIC_NEGATIVE"

def test_every_figure_has_exact_source_table(tmp_path):
    report = build_issue28_report(success_fixture(tmp_path), protocol())
    for figure in report["figures"]:
        assert Path(figure["source_csv"]).is_file()
```

- [ ] **Step 2: Run and verify failure**

Run: `../../../.venv/bin/python -m pytest tests/test_issue28_report.py -q`

- [ ] **Step 3: Implement paired aggregation**

Aggregate within-bundle differences first, then hierarchical bootstrap. Report B0/N0 gates, each seed/round status, objective overlap, `R_rep`, tau ratios, ESS/s ratios, convergence/resource data, and power caveat.

- [ ] **Step 4: Generate publication-quality compact figures**

Create objective-by-round, patch/candidate residuals, tau and ESS/s three-arm comparisons, function drift, training convergence, and resource scaling. Use colorblind-safe colors, error bars, seed count, lattice, K, round, and exact source CSV/JSON.

- [ ] **Step 5: Build challenge report inputs and HTML**

Write `report.json`, then invoke the existing report renderer. Include the 3D Hard Goal exclusion and optional MPS comparison in a non-gating appendix.

- [ ] **Step 6: Run report tests and a fixture render**

Run: `../../../.venv/bin/python -m pytest tests/test_issue28_report.py tests/test_issue28_analysis.py -q`

Run: `../../../.venv/bin/python scripts/issue28_report.py --root /tmp/issue28-report-fixture --protocol config/issue28_easy_v1.json`

- [ ] **Step 7: Commit**

```bash
git add tracks/mps/DMRG/scripts/issue28_report.py tracks/mps/DMRG/tests/test_issue28_report.py tracks/mps/DMRG/README.md
git commit -m "feat: report issue 28 easy goal results"
```

### Task 19: Canonical Plan, Documentation, Cleanup, and Verification

**Files:**
- Modify: `PLAN.md`
- Modify: `README.md`
- Modify: `PROJECT_STATUS_AND_ROADMAP.md`
- Modify: `docs/superpowers/plans/2026-07-28-mps-vmcrg-optional-comparison.md`
- Modify: `.gitignore`

**Interfaces:**
- Consumes: all completed tasks and verification outputs.
- Produces: one canonical plan/status entry and an explicit MPS optional archive.

- [ ] **Step 1: Add the optional-plan banner**

Insert at the top of the archived MPS plan:

```markdown
> Archived optional comparison. This MPS route is preserved for evidence and
> does not contribute to any Issue #28 success gate.
```

- [ ] **Step 2: Update project-facing metadata**

Root `PLAN.md` tracks B0/N0/N1-N5 and links this detailed plan/spec. README leads with the pure-neural fresh-checkout command. Project status lists exact completed/blocked stages and never labels smoke/pilot as success.

- [ ] **Step 3: Remove generated caches only**

Delete `__pycache__/`, `.pytest_cache/`, Numba cache files, and duplicated generated HTML inside the DMRG workspace. Preserve all historical source, protocols, raw compact evidence, MPS outputs, paper outputs, and LTRG work.

- [ ] **Step 4: Run focused tests after every completed task, then the full suite**

Run from `tracks/mps/DMRG`:

`../../../.venv/bin/python -m pytest -q`

Expected: all tests pass; baseline before implementation was 142 tests.

- [ ] **Step 5: Run root harness tests when the DMRG suite passes**

Run from repository root: `make test`

Record any unrelated pre-existing failure separately; do not modify unrelated files to force a green result.

- [ ] **Step 6: Verify fresh-checkout dry-run and smoke chain**

Run:

```bash
../../../.venv/bin/python reproduce.py issue28-easy --protocol config/issue28_easy_v1.json --through N0 --dry-run
../../../.venv/bin/python reproduce.py issue28-easy --protocol config/issue28_easy_v1.json --through N1 --backend local
```

Expected: B0/N0/N1 manifests exist and classification is not correctness/protocol failure.

- [ ] **Step 7: Use verification-before-completion before any success claim**

Verify tests, manifests, hashes, formal seed count, five-round depth, BAR overlap, paired statistics, and report HTML. If formal compute has not completed, report implementation completion separately from scientific Easy Goal completion.

- [ ] **Step 8: Commit documentation and cleanup**

```bash
git add tracks/mps/DMRG/PLAN.md tracks/mps/DMRG/README.md tracks/mps/DMRG/PROJECT_STATUS_AND_ROADMAP.md tracks/mps/DMRG/docs/superpowers/plans/2026-07-28-mps-vmcrg-optional-comparison.md tracks/mps/DMRG/.gitignore
git commit -m "docs: make pure-neural issue 28 canonical"
```

---

## Formal Compute Handoff

After Tasks 1-19 pass locally:

1. invoke `using-slurm` and read the active profile;
2. run `scripts/harness_slurm.sh precheck` and `probe-partitions`;
3. submit the short smoke with `--test-only`, then monitor its first manifest;
4. execute the N3 measured pilot and freeze `config/issue28_formal_v1.json`;
5. submit five independent seed chains, each with rounds 1-5 dependent;
6. monitor through first-round logs and periodic status checks;
7. fetch and classify every cell, resume only hash-matching interrupted rounds;
8. run N5 analysis and render the final report;
9. claim `EASY_GOAL_SUCCESS` only if the complete formal evidence passes every frozen gate.
