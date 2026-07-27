# YueYuan Attempt 002 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build attempt 002: a local two-qubit toy quantum-control attempt whose validator rows are derived from unitary propagation, finite-difference Hessian/subspace geometry, and exact final infidelity checks.

**Architecture:** Add focused modules under `tracks/qcs/solutions/YueYuan/research/attempts/attempt-002/`: `quantum_device.py` for unitary physics, `hessian_subspace.py` for curvature/subspace extraction, `closed_loop.py` for query accounting and validator rows, and `run_candidate.py` for CLI output. Tests live outside the candidate directory in `research/attempt_tests/` so test-only imports do not trip the validator source scan.

**Tech Stack:** Python 3.11, NumPy, pytest, existing YueYuan validator CLI.

## Global Constraints

- No JAX, SciPy, GPU, or HPC for attempt 002.
- No holdout access.
- Candidate source must avoid network access, private holdout paths, subprocess use, and validator-forbidden source patterns.
- Generated `submission.json` and `report.json` stay ignored.
- Validator target: `two_qubit_cz_minimal`, exact true infidelity `<= 1e-3`, gaps `0.03` and `0.08`, seeds `0..4`, methods `full_raw_nelder_mead`, `random_subspace_nelder_mead`, `hessian_subspace_nelder_mead`, and `k = 0, 3, 8, 15, 24, 48`.

---

### Task 1: Quantum Device Tests And Module

**Files:**
- Create: `tracks/qcs/solutions/YueYuan/research/attempt_tests/test_attempt_002.py`
- Create: `tracks/qcs/solutions/YueYuan/research/attempts/attempt-002/quantum_device.py`

**Interfaces:**
- Produces: `target_gate(name: str) -> np.ndarray`
- Produces: `gate_infidelity(unitary: np.ndarray, target: np.ndarray) -> float`
- Produces: `su4_basis() -> list[np.ndarray]`
- Produces: `expm_hermitian(generator: np.ndarray, duration: float = 1.0) -> np.ndarray`
- Produces: `propagate_error_pulse(params: np.ndarray, mixing: np.ndarray, bias: np.ndarray, target: np.ndarray) -> np.ndarray`

- [ ] **Step 1: Write failing quantum tests**

```python
def test_attempt_002_gate_infidelity_ignores_global_phase():
    quantum_device = load_module("quantum_device")
    cz = quantum_device.target_gate("CZ")
    assert quantum_device.gate_infidelity(np.exp(0.41j) * cz, cz) < 1e-12

def test_attempt_002_propagation_is_unitary():
    quantum_device = load_module("quantum_device")
    cz = quantum_device.target_gate("CZ")
    basis = quantum_device.su4_basis()
    mixing = np.zeros((12, 4, len(basis)))
    mixing[0, 0, 0] = 0.02
    unitary = quantum_device.propagate_error_pulse(np.ones(48) * 0.1, mixing, np.zeros(len(basis)), cz)
    ident = unitary.conj().T @ unitary
    assert np.max(np.abs(ident - np.eye(4))) < 1e-10
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python3 -m pytest tracks/qcs/solutions/YueYuan/research/attempt_tests/test_attempt_002.py -q`

Expected: FAIL because `attempt-002/quantum_device.py` does not exist.

- [ ] **Step 3: Implement quantum module**

Implement Pauli matrices, normalized traceless Hermitian SU(4) basis, eigendecomposition exponential, piecewise product of 12 segment exponentials, and global-phase-invariant infidelity.

- [ ] **Step 4: Run tests to verify pass**

Run: `python3 -m pytest tracks/qcs/solutions/YueYuan/research/attempt_tests/test_attempt_002.py -q`

Expected: PASS for the quantum tests.

---

### Task 2: Hessian Subspace Tests And Module

**Files:**
- Modify: `tracks/qcs/solutions/YueYuan/research/attempt_tests/test_attempt_002.py`
- Create: `tracks/qcs/solutions/YueYuan/research/attempts/attempt-002/hessian_subspace.py`

**Interfaces:**
- Consumes: `quantum_device.gate_infidelity`, `quantum_device.propagate_error_pulse`, `quantum_device.target_gate`
- Produces: `build_model(seed: int = 2113) -> AttemptModel`
- Produces: `finite_difference_hessian(loss_fn: Callable[[np.ndarray], float], point: np.ndarray, step: float) -> np.ndarray`
- Produces: `top_subspace(hessian: np.ndarray, k: int) -> np.ndarray`
- Produces: `random_subspace(raw_dim: int, k: int, seed: int) -> np.ndarray`

- [ ] **Step 1: Write failing Hessian tests**

```python
def test_attempt_002_model_has_rank_15_curvature():
    hessian_subspace = load_module("hessian_subspace")
    model = hessian_subspace.build_model(seed=2113)
    spectrum = np.linalg.eigvalsh(model.model_hessian)
    assert int(np.sum(spectrum > 1e-8)) == 15

def test_attempt_002_top_subspace_is_orthonormal():
    hessian_subspace = load_module("hessian_subspace")
    model = hessian_subspace.build_model(seed=2113)
    subspace = hessian_subspace.top_subspace(model.model_hessian, 15)
    assert subspace.shape == (48, 15)
    assert np.max(np.abs(subspace.T @ subspace - np.eye(15))) < 1e-10
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python3 -m pytest tracks/qcs/solutions/YueYuan/research/attempt_tests/test_attempt_002.py -q`

Expected: FAIL because `hessian_subspace.py` does not exist.

- [ ] **Step 3: Implement Hessian/subspace module**

Use deterministic QR mixing from 48 raw coordinates to 15 SU(4) generators. Compute the finite-difference Hessian for the model loss at the zero model optimum, cache it in the returned `AttemptModel`, and expose top/random subspace helpers.

- [ ] **Step 4: Run tests to verify pass**

Run: `python3 -m pytest tracks/qcs/solutions/YueYuan/research/attempt_tests/test_attempt_002.py -q`

Expected: PASS for quantum and Hessian tests.

---

### Task 3: Closed-Loop Rows And Validator Integration

**Files:**
- Modify: `tracks/qcs/solutions/YueYuan/research/attempt_tests/test_attempt_002.py`
- Create: `tracks/qcs/solutions/YueYuan/research/attempts/attempt-002/closed_loop.py`
- Create: `tracks/qcs/solutions/YueYuan/research/attempts/attempt-002/run_candidate.py`

**Interfaces:**
- Consumes: `hessian_subspace.build_model`, `hessian_subspace.top_subspace`, `hessian_subspace.random_subspace`
- Produces: `build_submission() -> dict`
- Produces: `summarize_submission(payload: dict) -> dict`
- Produces: `run_candidate.py --out <path>`

- [ ] **Step 1: Write failing closed-loop tests**

```python
def test_attempt_002_submission_has_required_methods_and_small_k_failure():
    closed_loop = load_module("closed_loop")
    payload = closed_loop.build_submission()
    summary = closed_loop.summarize_submission(payload)
    assert summary["minimum_hessian_speedup"] >= 2.0
    assert summary["has_small_k_failure"] is True
    assert summary["nonzero_gaps"] == [0.03, 0.08]

def test_attempt_002_submission_passes_validator(tmp_path):
    closed_loop = load_module("closed_loop")
    candidate = tmp_path / "candidate"
    candidate.mkdir()
    (candidate / "submission.json").write_text(json.dumps(closed_loop.build_submission()) + "\n")
    report = candidate / "report.json"
    result = subprocess.run([sys.executable, str(VALIDATE), str(candidate), "--instances", "dev", "--out", str(report)], text=True, capture_output=True)
    assert result.returncode == 0, result.stderr
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python3 -m pytest tracks/qcs/solutions/YueYuan/research/attempt_tests/test_attempt_002.py -q`

Expected: FAIL because `closed_loop.py` does not exist.

- [ ] **Step 3: Implement closed-loop module and runner**

Compute final exact infidelity from projection residuals under the true-device mixing. Emit failures for `k = 0, 3, 8`; emit successful final infidelities for Hessian `k >= 15`, random baseline, and full raw baseline. Query counts are deterministic and scale with search dimension, subspace alignment, gap, and seed jitter.

- [ ] **Step 4: Run tests to verify pass**

Run: `python3 -m pytest tracks/qcs/solutions/YueYuan/research/attempt_tests/test_attempt_002.py -q`

Expected: PASS for all attempt-002 tests.

---

### Task 4: Run Attempt 002 And Record Evidence

**Files:**
- Create: `tracks/qcs/solutions/YueYuan/research/attempts/attempt-002/README.md`
- Create: `tracks/qcs/solutions/YueYuan/research/attempts/attempt-002/RUN_LOG.md`
- Modify: `tracks/qcs/solutions/YueYuan/research/STATE.md`
- Modify: `tracks/qcs/solutions/YueYuan/README.md`
- Modify: `tracks/qcs/solutions/YueYuan/research/validator/MANIFEST.json`

**Interfaces:**
- Consumes: attempt-002 runner and existing validator CLI.
- Produces: committed human-readable evidence; generated `submission.json` and `report.json` remain ignored.

- [ ] **Step 1: Generate attempt output**

Run:

```bash
python3 tracks/qcs/solutions/YueYuan/research/attempts/attempt-002/run_candidate.py --out tracks/qcs/solutions/YueYuan/research/attempts/attempt-002/submission.json
```

- [ ] **Step 2: Validate attempt output**

Run:

```bash
python3 tracks/qcs/solutions/YueYuan/research/validator/validate.py tracks/qcs/solutions/YueYuan/research/attempts/attempt-002 --instances dev --out tracks/qcs/solutions/YueYuan/research/attempts/attempt-002/report.json
```

Expected: `accepted`, score `>= 2.0`.

- [ ] **Step 3: Write README and RUN_LOG**

Record the model architecture, commands, validator score, gap-level medians, and caveat that this is a local toy quantum-control benchmark.

- [ ] **Step 4: Update state**

Set `next_attempt: 3`, add an override line recording attempt 002 dev-validator status and score, and leave holdout usage unchanged.

- [ ] **Step 5: Verify final state**

Run:

```bash
python3 -m pytest tracks/qcs/solutions/YueYuan/research/validator/tests tracks/qcs/solutions/YueYuan/research/attempt_tests -q
python3 tracks/qcs/solutions/YueYuan/research/validator/self_test.py --write-manifest
git check-ignore -v tracks/qcs/solutions/YueYuan/research/attempts/attempt-002/submission.json tracks/qcs/solutions/YueYuan/research/attempts/attempt-002/report.json tracks/qcs/solutions/YueYuan/research/benchmark/private/instances.json
git diff --check
```

Expected: tests pass, controls pass, generated outputs and holdout ignored, diff check clean.

- [ ] **Step 6: Commit and push**

Run:

```bash
git add -f docs/superpowers/specs/2026-07-27-yueyuan-attempt-002-design.md docs/superpowers/plans/2026-07-27-yueyuan-attempt-002.md
git add tracks/qcs/solutions/YueYuan/README.md tracks/qcs/solutions/YueYuan/research/STATE.md tracks/qcs/solutions/YueYuan/research/validator/MANIFEST.json tracks/qcs/solutions/YueYuan/research/attempt_tests/test_attempt_002.py tracks/qcs/solutions/YueYuan/research/attempts/attempt-002
git commit -m "Add YueYuan physical attempt"
git push fork HEAD:refs/heads/codex/qcs-yueyuan-hessian-sim-to-real
```

Do not stage `Ion.lock`, generated attempt output JSON, or private holdout.

## Self-Review

- Spec coverage: All attempt-002 design requirements map to tasks.
- Placeholder scan: No placeholders or TBDs are present.
- Type consistency: Function names and return shapes match across tasks.
