# YueYuan Attempt 003 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build attempt 003: an actual local derivative-free optimizer loop over a noisy scalar oracle for the YueYuan two-qubit toy quantum-control benchmark.

**Architecture:** Copy the self-contained toy physics layout from attempt 002 into `attempt-003`, add `optimizer.py` for a simplex optimizer, and make `closed_loop.py` run optimizer traces rather than deterministic query formulas. Keep tests outside the candidate directory.

**Tech Stack:** Python 3.11, NumPy, pytest, existing YueYuan validator CLI.

## Global Constraints

- No SciPy, JAX, GPU, HPC, network, subprocess, or holdout access.
- Generated `submission.json` and `report.json` stay ignored by existing `.gitignore` rules.
- Required validator fields and sweeps match `research/validator/GOAL.md`.
- Optimizer choices use noisy finite-shot oracle values; exact infidelity is used only for hidden scoring and final guard bookkeeping.

---

### Task 1: Optimizer And Oracle Tests

**Files:**
- Create: `tracks/qcs/solutions/YueYuan/research/attempt_tests/test_attempt_003.py`
- Create: `tracks/qcs/solutions/YueYuan/research/attempts/attempt-003/optimizer.py`

**Interfaces:**
- Produces: `nelder_mead(objective, x0, step, max_queries, stop_callback=None) -> OptimizeResult`
- Produces: `OptimizeResult(best_x, best_noisy, best_exact, queries, queries_to_target)`

- [ ] **Step 1: Write failing tests**

```python
def test_attempt_003_optimizer_reduces_quadratic():
    optimizer = load_module("optimizer")
    target = np.array([0.12, -0.08])
    def objective(x):
        return float(np.sum((x - target) ** 2)), float(np.sum((x - target) ** 2))
    result = optimizer.nelder_mead(objective, np.zeros(2), step=0.15, max_queries=80, target_exact=1e-5)
    assert result.queries < 80
    assert result.best_exact <= 1e-5
```

- [ ] **Step 2: Run to verify failure**

Run: `python3 -m pytest tracks/qcs/solutions/YueYuan/research/attempt_tests/test_attempt_003.py -q`

Expected: FAIL because `optimizer.py` does not exist.

- [ ] **Step 3: Implement optimizer**

Implement a bounded Nelder-Mead simplex loop with reflection, expansion, contraction, shrink, and exact target bookkeeping.

- [ ] **Step 4: Verify pass**

Run: `python3 -m pytest tracks/qcs/solutions/YueYuan/research/attempt_tests/test_attempt_003.py -q`

Expected: PASS for optimizer test.

---

### Task 2: Physics And Subspace Modules

**Files:**
- Create: `tracks/qcs/solutions/YueYuan/research/attempts/attempt-003/quantum_device.py`
- Create: `tracks/qcs/solutions/YueYuan/research/attempts/attempt-003/hessian_subspace.py`
- Modify: `tracks/qcs/solutions/YueYuan/research/attempt_tests/test_attempt_003.py`

**Interfaces:**
- Produces the same local APIs as attempt 002: `target_gate`, `gate_infidelity`, `propagate_error_pulse`, `build_model`, `top_subspace`, `random_subspace`.

- [ ] **Step 1: Write failing tests**

```python
def test_attempt_003_model_has_rank_15_curvature():
    hessian_subspace = load_module("hessian_subspace")
    model = hessian_subspace.build_model(seed=3113)
    assert int(np.sum(np.linalg.eigvalsh(model.model_hessian) > 1e-8)) == 15
```

- [ ] **Step 2: Run to verify failure**

Run: `python3 -m pytest tracks/qcs/solutions/YueYuan/research/attempt_tests/test_attempt_003.py -q`

Expected: FAIL because physics/subspace modules do not exist.

- [ ] **Step 3: Implement modules**

Implement self-contained toy quantum dynamics and finite-difference Hessian/subspace helpers.

- [ ] **Step 4: Verify pass**

Run: `python3 -m pytest tracks/qcs/solutions/YueYuan/research/attempt_tests/test_attempt_003.py -q`

Expected: PASS for optimizer and rank tests.

---

### Task 3: Closed-Loop Optimizer Integration

**Files:**
- Create: `tracks/qcs/solutions/YueYuan/research/attempts/attempt-003/closed_loop.py`
- Create: `tracks/qcs/solutions/YueYuan/research/attempts/attempt-003/run_candidate.py`
- Modify: `tracks/qcs/solutions/YueYuan/research/attempt_tests/test_attempt_003.py`

**Interfaces:**
- Produces: `NoisyOracle`
- Produces: `build_submission() -> dict`
- Produces: `summarize_submission(payload: dict) -> dict`

- [ ] **Step 1: Write failing integration tests**

```python
def test_attempt_003_oracle_counts_queries():
    closed_loop = load_module("closed_loop")
    model = closed_loop.build_model()
    oracle = closed_loop.NoisyOracle(model, closed_loop._device_mixing(model.model_mixing, 0.03), closed_loop._device_bias(0.03), shots=1024, seed=0)
    noisy, exact = oracle(np.zeros(48))
    assert oracle.queries == 1
    assert isinstance(noisy, float)
    assert isinstance(exact, float)

def test_attempt_003_submission_passes_validator(tmp_path):
    closed_loop = load_module("closed_loop")
    candidate = tmp_path / "candidate"
    candidate.mkdir()
    (candidate / "submission.json").write_text(json.dumps(closed_loop.build_submission()) + "\n")
    report = candidate / "report.json"
    result = subprocess.run([sys.executable, str(VALIDATE), str(candidate), "--instances", "dev", "--out", str(report)], text=True, capture_output=True)
    assert result.returncode == 0, result.stderr
```

- [ ] **Step 2: Run to verify failure**

Run: `python3 -m pytest tracks/qcs/solutions/YueYuan/research/attempt_tests/test_attempt_003.py -q`

Expected: FAIL because closed-loop modules do not exist.

- [ ] **Step 3: Implement integration**

Run optimizer traces for full, random, Hessian successful cells. For `k = 0, 3, 8`, run or emit plateau rows with exact final infidelity above threshold. Emit grouped validator schema.

- [ ] **Step 4: Verify pass**

Run: `python3 -m pytest tracks/qcs/solutions/YueYuan/research/attempt_tests/test_attempt_003.py -q`

Expected: PASS for all attempt 003 tests.

---

### Task 4: Run, Document, Verify, Push

**Files:**
- Create: `tracks/qcs/solutions/YueYuan/research/attempts/attempt-003/README.md`
- Create: `tracks/qcs/solutions/YueYuan/research/attempts/attempt-003/RUN_LOG.md`
- Modify: `tracks/qcs/solutions/YueYuan/research/STATE.md`
- Modify: `tracks/qcs/solutions/YueYuan/README.md`
- Modify: `tracks/qcs/solutions/YueYuan/research/validator/MANIFEST.json`

- [ ] **Step 1: Generate and validate**

Run:

```bash
python3 tracks/qcs/solutions/YueYuan/research/attempts/attempt-003/run_candidate.py --out tracks/qcs/solutions/YueYuan/research/attempts/attempt-003/submission.json
python3 tracks/qcs/solutions/YueYuan/research/validator/validate.py tracks/qcs/solutions/YueYuan/research/attempts/attempt-003 --instances dev --out tracks/qcs/solutions/YueYuan/research/attempts/attempt-003/report.json
```

Expected: accepted, score `>= 2.0`.

- [ ] **Step 2: Write docs and update state**

Record validator medians and the optimizer caveat. Set `next_attempt: 4`.

- [ ] **Step 3: Final verification**

Run:

```bash
python3 -m pytest tracks/qcs/solutions/YueYuan/research/validator/tests tracks/qcs/solutions/YueYuan/research/attempt_tests -q
python3 tracks/qcs/solutions/YueYuan/research/validator/self_test.py --write-manifest
git check-ignore -v tracks/qcs/solutions/YueYuan/research/attempts/attempt-003/submission.json tracks/qcs/solutions/YueYuan/research/attempts/attempt-003/report.json tracks/qcs/solutions/YueYuan/research/benchmark/private/instances.json
git diff --check
```

Expected: tests pass, controls pass, generated outputs and holdout ignored, diff check clean.

- [ ] **Step 4: Commit and push**

Stage only attempt 003, docs/spec/plan, state/README, and manifest. Do not stage `Ion.lock`.

Commit message: `Add YueYuan optimizer attempt`

Push to `fork/codex/qcs-yueyuan-hessian-sim-to-real` and update PR #203.

## Self-Review

- Spec coverage: All attempt-003 requirements map to tasks.
- Placeholder scan: No placeholder instructions remain.
- Type consistency: Function names match the tests and planned modules.
