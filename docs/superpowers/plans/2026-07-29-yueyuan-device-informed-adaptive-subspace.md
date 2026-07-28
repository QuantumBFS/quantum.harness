# YueYuan Device-Informed Adaptive Subspace Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a device-informed adaptive subspace method and a lightweight invariant/rank probe so attempt 004 addresses challenge #113's strongest remaining software-science gaps.

**Architecture:** Add a focused `device_subspace.py` module for black-box paired probing and residual-basis construction. Integrate a new `device_informed_adaptive_hessian_nelder_mead` baseline that shares a single `QueryOnlyDevice` across pilot search, probing, and final search. Add small runners for the focused recovery comparison and invariant probe, then summarize results in existing docs without changing the main full-sweep contract.

**Tech Stack:** Python 3, NumPy, JAX already used by attempt 004, pytest, JSONL/CSV artifacts, matplotlib through existing plotting patterns.

## Global Constraints

- Do not include credentials, usernames, hostnames, SSH commands, private keys, or private access markers.
- Keep `Ion.lock` unstaged and untouched.
- Do not claim real hardware was used.
- Use only finite-shot `QueryOnlyDevice.query()` values for device-informed probe decisions.
- Exact true fidelity may be used only by the audit/scoring path, never to select probe directions or decide whether to probe.
- Count all probing queries and shots inside the same total closed-loop budget.
- Generated artifacts remain under `tracks/qcs/results/YueYuan/attempt-004/` or `/tmp` and stay out of git.
- Preserve the known-good baseline recorded in `docs/superpowers/snapshots/2026-07-29-yueyuan-solution-version-ledger.md`.

---

### Task 1: Device Subspace Probe Module

**Files:**
- Create: `tracks/qcs/solutions/YueYuan/research/attempts/attempt-004/device_subspace.py`
- Test: `tracks/qcs/solutions/YueYuan/research/attempt_tests/test_attempt_004_device_subspace.py`

**Interfaces:**
- Produces: `ProbeConfig(direction_count: int, append_count: int, step: float, repeats: int = 1, min_positive_curvature: float = 0.0)`
- Produces: `ProbeResult(basis: np.ndarray, curvatures: np.ndarray, query_count: int, shot_count: int, selected_count: int, metadata: dict)`
- Produces: `orthonormalize_against(existing_basis: np.ndarray, candidate_basis: np.ndarray, tolerance: float = 1e-10) -> np.ndarray`
- Produces: `random_residual_directions(raw_dim: int, existing_basis: np.ndarray, count: int, seed: int) -> np.ndarray`
- Produces: `estimate_device_subspace(oracle, system_config, center_theta, existing_basis, shots: int, seed: int, cfg: ProbeConfig, on_query=None) -> ProbeResult`

- [ ] **Step 1: Write failing residual-direction test**

Add this test to `test_attempt_004_device_subspace.py`:

```python
import pathlib
import sys

import numpy as np

ROOT = pathlib.Path(__file__).resolve().parents[6]
ATTEMPT = ROOT / "tracks/qcs/solutions/YueYuan/research/attempts/attempt-004"
sys.path.insert(0, str(ATTEMPT))

import device_subspace


def test_attempt_004_residual_directions_are_orthonormal_and_residual():
    existing = np.eye(5, 2)
    directions = device_subspace.random_residual_directions(
        raw_dim=5,
        existing_basis=existing,
        count=3,
        seed=12,
    )

    assert directions.shape == (5, 3)
    assert np.allclose(directions.T @ directions, np.eye(3), atol=1e-10)
    assert np.allclose(existing.T @ directions, np.zeros((2, 3)), atol=1e-10)
```

- [ ] **Step 2: Run test to verify it fails**

Run:

```bash
python3 -m pytest tracks/qcs/solutions/YueYuan/research/attempt_tests/test_attempt_004_device_subspace.py::test_attempt_004_residual_directions_are_orthonormal_and_residual -q
```

Expected: fail with `ModuleNotFoundError` or missing `random_residual_directions`.

- [ ] **Step 3: Implement minimal residual basis utilities**

Create `device_subspace.py` with:

```python
from __future__ import annotations

from dataclasses import dataclass, asdict

import numpy as np


@dataclass(frozen=True)
class ProbeConfig:
    direction_count: int
    append_count: int
    step: float
    repeats: int = 1
    min_positive_curvature: float = 0.0


@dataclass(frozen=True)
class ProbeResult:
    basis: np.ndarray
    curvatures: np.ndarray
    query_count: int
    shot_count: int
    selected_count: int
    metadata: dict


def _as_basis(matrix: np.ndarray, raw_dim: int) -> np.ndarray:
    basis = np.asarray(matrix, dtype=float)
    if basis.size == 0:
        return np.zeros((raw_dim, 0), dtype=float)
    if basis.ndim != 2 or basis.shape[0] != raw_dim:
        raise ValueError(f"basis must have shape ({raw_dim}, k)")
    return basis


def orthonormalize_against(existing_basis, candidate_basis, tolerance: float = 1e-10) -> np.ndarray:
    existing = np.asarray(existing_basis, dtype=float)
    candidates = np.asarray(candidate_basis, dtype=float)
    if candidates.ndim != 2:
        raise ValueError("candidate_basis must be a matrix")
    raw_dim = candidates.shape[0]
    existing = _as_basis(existing, raw_dim)
    vectors = []
    for column in range(candidates.shape[1]):
        vector = candidates[:, column].astype(float)
        if existing.shape[1]:
            vector = vector - existing @ (existing.T @ vector)
        for accepted in vectors:
            vector = vector - accepted * float(accepted @ vector)
        norm = float(np.linalg.norm(vector))
        if norm > tolerance:
            vectors.append(vector / norm)
    if not vectors:
        return np.zeros((raw_dim, 0), dtype=float)
    return np.column_stack(vectors)


def random_residual_directions(raw_dim: int, existing_basis, count: int, seed: int) -> np.ndarray:
    if raw_dim <= 0:
        raise ValueError("raw_dim must be positive")
    if count <= 0:
        return np.zeros((raw_dim, 0), dtype=float)
    existing = _as_basis(existing_basis, raw_dim)
    residual_dim = max(0, raw_dim - existing.shape[1])
    draw_count = min(int(count), residual_dim)
    if draw_count == 0:
        return np.zeros((raw_dim, 0), dtype=float)
    rng = np.random.default_rng(seed)
    candidates = rng.normal(size=(raw_dim, max(draw_count, count)))
    return orthonormalize_against(existing, candidates)[:, :draw_count]
```

- [ ] **Step 4: Run residual test to verify it passes**

Run the same pytest command. Expected: pass.

- [ ] **Step 5: Write failing paired-probe accounting test**

Append:

```python
import config
import device
import pulses
import systems


def _one_qubit_probe_context(seed=21):
    model = systems.build_system(config.ONE_QUBIT_X)
    true_system = device.build_true_system(model, "small", seed=seed)
    oracle = device.QueryOnlyDevice(true_system, seed=seed + 1)
    center = pulses.initial_pulse(config.ONE_QUBIT_X, seed=seed + 2)
    existing = np.eye(config.ONE_QUBIT_X.raw_dim, 2)
    return oracle, center, existing


def test_attempt_004_device_subspace_probe_counts_queries_and_shots():
    oracle, center, existing = _one_qubit_probe_context()
    cfg = device_subspace.ProbeConfig(
        direction_count=3,
        append_count=2,
        step=0.02,
        repeats=2,
        min_positive_curvature=-1e9,
    )

    result = device_subspace.estimate_device_subspace(
        oracle,
        config.ONE_QUBIT_X,
        center,
        existing,
        shots=32,
        seed=33,
        cfg=cfg,
    )

    assert result.query_count == 13
    assert result.shot_count == 13 * 32
    assert oracle.query_count == 13
    assert oracle.shot_count == 13 * 32
    assert result.curvatures.shape == (3,)
    assert result.basis.shape == (config.ONE_QUBIT_X.raw_dim, 2)
    assert result.selected_count == 2
    assert np.allclose(result.basis.T @ result.basis, np.eye(2), atol=1e-10)
```

- [ ] **Step 6: Run probe test to verify it fails**

Run:

```bash
python3 -m pytest tracks/qcs/solutions/YueYuan/research/attempt_tests/test_attempt_004_device_subspace.py::test_attempt_004_device_subspace_probe_counts_queries_and_shots -q
```

Expected: fail because `estimate_device_subspace` is missing.

- [ ] **Step 7: Implement paired probing**

Add `estimate_device_subspace`. It must:

```python
from pulses import clip_pulse


def _validate_probe_config(cfg: ProbeConfig) -> None:
    if cfg.direction_count < 0:
        raise ValueError("direction_count must be non-negative")
    if cfg.append_count < 0:
        raise ValueError("append_count must be non-negative")
    if cfg.step <= 0.0:
        raise ValueError("step must be positive")
    if cfg.repeats <= 0:
        raise ValueError("repeats must be positive")


def estimate_device_subspace(
    oracle,
    system_config,
    center_theta,
    existing_basis,
    shots: int,
    seed: int,
    cfg: ProbeConfig,
    on_query=None,
) -> ProbeResult:
    _validate_probe_config(cfg)
    if shots <= 0:
        raise ValueError("shots must be positive")
    raw_dim = system_config.raw_dim
    center = clip_pulse(np.asarray(center_theta, dtype=float), system_config)
    existing = _as_basis(existing_basis, raw_dim)
    query_start = int(getattr(oracle, "query_count", 0))
    shot_start = int(getattr(oracle, "shot_count", 0))
    directions = random_residual_directions(raw_dim, existing, cfg.direction_count, seed)
    center_value = float(oracle.query(center, shots=shots))
    if on_query is not None:
        on_query(center)
    curvatures = []
    for column in range(directions.shape[1]):
        direction = directions[:, column]
        plus_values = []
        minus_values = []
        for repeat in range(cfg.repeats):
            plus = clip_pulse(center + cfg.step * direction, system_config)
            minus = clip_pulse(center - cfg.step * direction, system_config)
            plus_values.append(float(oracle.query(plus, shots=shots)))
            if on_query is not None:
                on_query(plus)
            minus_values.append(float(oracle.query(minus, shots=shots)))
            if on_query is not None:
                on_query(minus)
        curvature = (float(np.mean(plus_values)) + float(np.mean(minus_values)) - 2.0 * center_value) / (cfg.step**2)
        curvatures.append(curvature)
    curvatures_array = np.asarray(curvatures, dtype=float)
    order = np.argsort(curvatures_array)[::-1]
    selected_columns = [
        index for index in order
        if curvatures_array[index] >= cfg.min_positive_curvature
    ][: cfg.append_count]
    selected = directions[:, selected_columns] if selected_columns else np.zeros((raw_dim, 0))
    selected = orthonormalize_against(existing, selected)
    query_count = int(getattr(oracle, "query_count", 0)) - query_start
    shot_count = int(getattr(oracle, "shot_count", 0)) - shot_start
    return ProbeResult(
        basis=selected,
        curvatures=curvatures_array,
        query_count=query_count,
        shot_count=shot_count,
        selected_count=selected.shape[1],
        metadata={
            "direction_count": directions.shape[1],
            "append_count": cfg.append_count,
            "selected_indices": [int(index) for index in selected_columns[: selected.shape[1]]],
            "step": cfg.step,
            "repeats": cfg.repeats,
        },
    )
```

- [ ] **Step 8: Run device-subspace tests**

Run:

```bash
python3 -m pytest tracks/qcs/solutions/YueYuan/research/attempt_tests/test_attempt_004_device_subspace.py -q
```

Expected: pass.

- [ ] **Step 9: Commit Task 1**

```bash
git add tracks/qcs/solutions/YueYuan/research/attempts/attempt-004/device_subspace.py tracks/qcs/solutions/YueYuan/research/attempt_tests/test_attempt_004_device_subspace.py
git commit -m "Add device-informed subspace probing"
```

### Task 2: Device-Informed Adaptive Baseline

**Files:**
- Modify: `tracks/qcs/solutions/YueYuan/research/attempts/attempt-004/baselines.py`
- Test: `tracks/qcs/solutions/YueYuan/research/attempt_tests/test_attempt_004_device_subspace.py`

**Interfaces:**
- Consumes: `device_subspace.ProbeConfig`, `device_subspace.estimate_device_subspace`
- Produces: `run_device_informed_adaptive_hessian_method(system, true_system, start_theta, hessian_matrix, initial_k, max_k, shots, seed, cfg, probe_cfg=None) -> RunRecord`
- Modifies: `RunRecord` with optional fields `device_probe_attempted`, `device_probe_directions_tested`, `device_probe_directions_selected`, `device_probe_query_count`, `device_probe_shot_count`.

- [ ] **Step 1: Write failing budget/boundary baseline test**

Append:

```python
import baselines
import hessian


def test_attempt_004_device_informed_method_respects_budget_and_records_probe():
    model = systems.build_system(config.ONE_QUBIT_X)
    start = pulses.initial_pulse(config.ONE_QUBIT_X, seed=41)
    hess = np.eye(config.ONE_QUBIT_X.raw_dim)
    true_system = device.build_true_system(model, "medium", seed=42)
    closed_cfg = config.ClosedLoopConfig(
        query_budget=36,
        target_infidelity=1e-3,
        initial_step=0.05,
    )
    probe_cfg = device_subspace.ProbeConfig(
        direction_count=4,
        append_count=2,
        step=0.03,
        repeats=1,
        min_positive_curvature=-1e9,
    )

    record = baselines.run_device_informed_adaptive_hessian_method(
        model,
        true_system,
        start,
        hess,
        initial_k=2,
        max_k=5,
        shots=64,
        seed=43,
        cfg=closed_cfg,
        probe_cfg=probe_cfg,
    )

    assert record.method == "device_informed_adaptive_hessian_nelder_mead"
    assert record.query_count <= closed_cfg.query_budget
    assert record.total_shots == record.query_count * 64
    assert record.device_probe_attempted is True
    assert record.device_probe_directions_tested == 4
    assert record.device_probe_directions_selected <= 2
    assert record.device_probe_query_count == 1 + 2 * 4
    assert record.device_probe_shot_count == record.device_probe_query_count * 64
    assert record.adaptive_initial_k == 2
    assert record.adaptive_final_k >= 2
```

- [ ] **Step 2: Run test to verify it fails**

Run:

```bash
python3 -m pytest tracks/qcs/solutions/YueYuan/research/attempt_tests/test_attempt_004_device_subspace.py::test_attempt_004_device_informed_method_respects_budget_and_records_probe -q
```

Expected: fail because the baseline method or RunRecord fields are missing.

- [ ] **Step 3: Extend `RunRecord`**

In `baselines.py`, add optional fields after the existing adaptive fields:

```python
    device_probe_attempted: bool | None = None
    device_probe_directions_tested: int | None = None
    device_probe_directions_selected: int | None = None
    device_probe_query_count: int | None = None
    device_probe_shot_count: int | None = None
```

- [ ] **Step 4: Implement device-informed adaptive method**

Add `import device_subspace` and implement:

```python
def _affordable_probe_config(system, initial_k: int, max_k: int, remaining_queries: int, cfg, probe_cfg):
    default = probe_cfg or device_subspace.ProbeConfig(
        direction_count=min(8, max(0, system.config.raw_dim - initial_k)),
        append_count=min(4, max(0, max_k - initial_k)),
        step=max(0.02, 0.5 * cfg.initial_step),
        repeats=1,
        min_positive_curvature=0.0,
    )
    if default.append_count <= 0 or remaining_queries <= 4:
        return None
    max_directions = max(0, (remaining_queries - 3) // (2 * default.repeats))
    direction_count = min(default.direction_count, max_directions)
    if direction_count <= 0:
        return None
    return device_subspace.ProbeConfig(
        direction_count=direction_count,
        append_count=min(default.append_count, max_k - initial_k, direction_count),
        step=default.step,
        repeats=default.repeats,
        min_positive_curvature=default.min_positive_curvature,
    )
```

Then add `run_device_informed_adaptive_hessian_method` by copying the shape of
`run_adaptive_hessian_method` but changing the second phase:

- initial basis is `leading_eigenspace(hessian_matrix, initial_k).vectors`;
- pilot budget is `min(cfg.query_budget, max(initial_k + 2, cfg.query_budget // 3))`;
- `make_objective` records exact audit only after each `oracle.query`;
- if the pilot's noisy best value is greater than zero and budget remains, call
  `device_subspace.estimate_device_subspace` with the same `oracle`;
- pass an `on_query(theta)` callback that updates `queries_to_target` using
  `AuditEvaluator` without feeding that result back into probe selection;
- merged basis is `np.column_stack([initial_basis, probe_result.basis])` when
  selected directions exist;
- final Nelder-Mead starts from pilot coefficients padded with zeros;
- all records use `oracle.query_count` and `oracle.shot_count`.

- [ ] **Step 5: Run baseline test to verify it passes**

Run the exact pytest command from Step 2. Expected: pass.

- [ ] **Step 6: Run all device-subspace tests**

Run:

```bash
python3 -m pytest tracks/qcs/solutions/YueYuan/research/attempt_tests/test_attempt_004_device_subspace.py -q
```

Expected: pass.

- [ ] **Step 7: Commit Task 2**

```bash
git add tracks/qcs/solutions/YueYuan/research/attempts/attempt-004/baselines.py tracks/qcs/solutions/YueYuan/research/attempt_tests/test_attempt_004_device_subspace.py
git commit -m "Add device-informed adaptive baseline"
```

### Task 3: Focused Device-Informed Runner And Summaries

**Files:**
- Create: `tracks/qcs/solutions/YueYuan/research/attempts/attempt-004/run_device_informed_focus.py`
- Modify: `tracks/qcs/solutions/YueYuan/research/attempts/attempt-004/analysis.py`
- Modify: `tracks/qcs/solutions/YueYuan/research/attempts/attempt-004/plotting.py`
- Test: `tracks/qcs/solutions/YueYuan/research/attempt_tests/test_attempt_004_device_subspace.py`

**Interfaces:**
- Produces CLI: `python3 .../run_device_informed_focus.py --out <dir> --fast`
- Produces generated files: `runs.jsonl`, `device_informed_summary.csv`, `device_informed_recovery.csv`, `figures/device_informed_recovery.png`
- Produces analysis helpers: `device_informed_summary_rows(groups: list[dict]) -> list[dict]`, `write_device_informed_tables(results_dir: Path, summary: dict | None = None) -> list[Path]`

- [ ] **Step 1: Write failing focused-runner smoke test**

Append:

```python
def test_attempt_004_device_informed_focus_runner_emits_new_method(tmp_path):
    out_dir = tmp_path / "device_focus"
    result = subprocess.run(
        [
            sys.executable,
            str(ATTEMPT / "run_device_informed_focus.py"),
            "--out",
            str(out_dir),
            "--fast",
        ],
        capture_output=True,
        text=True,
    )

    assert result.returncode == 0, result.stderr
    rows = [json.loads(line) for line in (out_dir / "runs.jsonl").read_text().splitlines()]
    assert "device_informed_adaptive_hessian_nelder_mead" in {row["method"] for row in rows}
    assert (out_dir / "summary_tables" / "device_informed_summary.csv").exists()
    assert (out_dir / "summary_tables" / "device_informed_recovery.csv").exists()
    assert (out_dir / "figures" / "device_informed_recovery.png").exists()
```

- [ ] **Step 2: Run test to verify it fails**

Run:

```bash
python3 -m pytest tracks/qcs/solutions/YueYuan/research/attempt_tests/test_attempt_004_device_subspace.py::test_attempt_004_device_informed_focus_runner_emits_new_method -q
```

Expected: fail because `run_device_informed_focus.py` does not exist.

- [ ] **Step 3: Add focused runner**

Implement `run_device_informed_focus.py`:

- parse `--out` and `--fast`;
- for fast mode run two work items:
  - `(ONE_QUBIT_X, "large", 256, seed=0)`;
  - `(TWO_QUBIT_CZ, "medium", 256, seed=1)`;
- for non-fast mode run:
  - one-qubit `medium`, `large`, 2048 shots, seeds `0..7`;
  - two-qubit `medium`, `large`, 2048 shots, seeds `0..7`;
- for each work item build model, optimize open-loop, compute Hessian, build true system;
- run methods:
  - `full_space_nelder_mead`;
  - `random_subspace_nelder_mead`;
  - `hessian_subspace_nelder_mead` at benchmark `k`;
  - `adaptive_hessian_subspace_nelder_mead`;
  - `device_informed_adaptive_hessian_nelder_mead`;
- write `runs.jsonl`;
- call `analysis.write_summary`, `analysis.write_device_informed_tables`, and `plotting.make_device_informed_recovery`;
- print JSON containing `records`, `device_informed_records`, and `out`.

- [ ] **Step 4: Add summary helpers and plot**

In `analysis.py`, add:

```python
DEVICE_INFORMED_FIELDS = GROUP_FIELDS + (
    "median_probe_query_count",
    "median_probe_shot_count",
    "median_probe_directions_selected",
)


def device_informed_summary_rows(groups: list[dict]) -> list[dict]:
    return [
        row for row in groups
        if row["method"] in {
            "full_space_nelder_mead",
            "random_subspace_nelder_mead",
            "hessian_subspace_nelder_mead",
            "adaptive_hessian_subspace_nelder_mead",
            "device_informed_adaptive_hessian_nelder_mead",
        }
    ]
```

Also compute medians for device-probe fields in `aggregate` when rows contain
`device_probe_query_count`, `device_probe_shot_count`, and
`device_probe_directions_selected`.

In `plotting.py`, add `make_device_informed_recovery(results_dir: Path) -> Path`
that reads `summary.json`, compares success rate for the three adaptive/fixed
methods, and writes `figures/device_informed_recovery.png`.

- [ ] **Step 5: Run focused-runner smoke test**

Run the pytest command from Step 2. Expected: pass.

- [ ] **Step 6: Run all device-subspace tests**

Run:

```bash
python3 -m pytest tracks/qcs/solutions/YueYuan/research/attempt_tests/test_attempt_004_device_subspace.py -q
```

Expected: pass.

- [ ] **Step 7: Commit Task 3**

```bash
git add tracks/qcs/solutions/YueYuan/research/attempts/attempt-004/run_device_informed_focus.py tracks/qcs/solutions/YueYuan/research/attempts/attempt-004/analysis.py tracks/qcs/solutions/YueYuan/research/attempts/attempt-004/plotting.py tracks/qcs/solutions/YueYuan/research/attempt_tests/test_attempt_004_device_subspace.py
git commit -m "Add device-informed focus runner"
```

### Task 4: Lightweight Invariant Rank Probe

**Files:**
- Create: `tracks/qcs/solutions/YueYuan/research/attempts/attempt-004/invariant_probe.py`
- Create: `tracks/qcs/solutions/YueYuan/research/attempts/attempt-004/run_invariant_probe.py`
- Test: `tracks/qcs/solutions/YueYuan/research/attempt_tests/test_attempt_004_invariant_probe.py`

**Interfaces:**
- Produces: `su_dimension(d: int) -> int`
- Produces: `local_chart_hessian(d: int, flat_extra: int = 0) -> np.ndarray`
- Produces: `rank_probe_rows() -> list[dict]`
- Produces CLI: `python3 .../run_invariant_probe.py --out <dir>`
- Produces generated files: `invariant_rank_probe.csv`, `figures/invariant_rank_probe.png`

- [ ] **Step 1: Write failing invariant probe tests**

Create `test_attempt_004_invariant_probe.py`:

```python
import csv
import pathlib
import subprocess
import sys

ROOT = pathlib.Path(__file__).resolve().parents[6]
ATTEMPT = ROOT / "tracks/qcs/solutions/YueYuan/research/attempts/attempt-004"
sys.path.insert(0, str(ATTEMPT))

import invariant_probe


def test_attempt_004_invariant_probe_reports_su_dimensions():
    assert invariant_probe.su_dimension(2) == 3
    assert invariant_probe.su_dimension(4) == 15
    assert invariant_probe.su_dimension(8) == 63
    rows = invariant_probe.rank_probe_rows()
    by_d = {row["hilbert_dim"]: row for row in rows}
    assert by_d[2]["benchmark_rank"] == 3
    assert by_d[4]["benchmark_rank"] == 15
    assert by_d[8]["benchmark_rank"] == 63
    assert by_d[8]["evidence_type"] == "local_unitary_chart"


def test_attempt_004_invariant_probe_runner_writes_csv_and_figure(tmp_path):
    out_dir = tmp_path / "invariant"
    result = subprocess.run(
        [sys.executable, str(ATTEMPT / "run_invariant_probe.py"), "--out", str(out_dir)],
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0, result.stderr
    csv_path = out_dir / "invariant_rank_probe.csv"
    assert csv_path.exists()
    assert (out_dir / "figures" / "invariant_rank_probe.png").exists()
    rows = list(csv.DictReader(csv_path.open()))
    assert {"2", "4", "8"} <= {row["hilbert_dim"] for row in rows}
```

- [ ] **Step 2: Run invariant tests to verify failure**

Run:

```bash
python3 -m pytest tracks/qcs/solutions/YueYuan/research/attempt_tests/test_attempt_004_invariant_probe.py -q
```

Expected: fail because modules do not exist.

- [ ] **Step 3: Implement invariant probe module**

`invariant_probe.py` should:

- return `d * d - 1` from `su_dimension`;
- build a diagonal Hessian with `d^2 - 1` curved entries and `flat_extra` zeros;
- report rows for:
  - one-qubit attempt-004 model-Hessian smoke evidence;
  - two-qubit attempt-004 model-Hessian smoke evidence;
  - three-qubit local chart sanity probe;
- include fields:
  - `system`;
  - `hilbert_dim`;
  - `benchmark_rank`;
  - `observed_curved_rank`;
  - `pulse_dim_or_chart_dim`;
  - `evidence_type`;
  - `rank_metric`;
  - `curvature_at_benchmark_rank`;
  - `formal_effective_rank`;
  - `caveat`.

- [ ] **Step 4: Implement invariant probe runner**

`run_invariant_probe.py` should write CSV and a simple bar figure comparing
benchmark rank and observed curved rank.

- [ ] **Step 5: Run invariant tests**

Run the pytest command from Step 2. Expected: pass.

- [ ] **Step 6: Commit Task 4**

```bash
git add tracks/qcs/solutions/YueYuan/research/attempts/attempt-004/invariant_probe.py tracks/qcs/solutions/YueYuan/research/attempts/attempt-004/run_invariant_probe.py tracks/qcs/solutions/YueYuan/research/attempt_tests/test_attempt_004_invariant_probe.py
git commit -m "Add invariant rank probe"
```

### Task 5: Docs, Ledger, Verification, PR Update

**Files:**
- Modify: `tracks/qcs/solutions/YueYuan/research/attempts/attempt-004/README.md`
- Modify: `tracks/qcs/solutions/YueYuan/research/attempts/attempt-004/REPORT.md`
- Modify: `docs/superpowers/snapshots/2026-07-29-yueyuan-solution-version-ledger.md`

**Interfaces:**
- Consumes: all new runners and test outputs.
- Produces: updated report sections for device-informed adaptive recovery and invariant rank probe.

- [ ] **Step 1: Run fast device-informed focus and invariant probe**

Run:

```bash
python3 tracks/qcs/solutions/YueYuan/research/attempts/attempt-004/run_device_informed_focus.py --out /tmp/yueyuan-attempt004-device-informed --fast
python3 tracks/qcs/solutions/YueYuan/research/attempts/attempt-004/run_invariant_probe.py --out /tmp/yueyuan-attempt004-invariant
```

Record the printed counts and generated file names.

- [ ] **Step 2: Update README and REPORT**

Add concise sections:

- `Device-Informed Adaptive Subspace`: explain paired finite-shot probing,
  counted overhead, and result interpretation.
- `Invariant Rank Probe`: explain one/two-qubit physical evidence plus
  three-qubit local-chart caveat.
- Update verification counts after final test runs.

- [ ] **Step 3: Update version ledger**

Append a new entry with the final commit SHA after implementation, changed-file
summary, verification outputs, and whether the score improved relative to
Baseline A.

- [ ] **Step 4: Run full verification**

Run:

```bash
python3 -m pytest tracks/qcs/solutions/YueYuan/research/attempt_tests/test_attempt_004_device_subspace.py -q
python3 -m pytest tracks/qcs/solutions/YueYuan/research/attempt_tests/test_attempt_004_invariant_probe.py -q
python3 -m pytest tracks/qcs/solutions/YueYuan/research/attempt_tests/test_attempt_004_*.py -q
python3 -m pytest tracks/qcs/solutions/YueYuan/research/attempt_tests -q
python3 tracks/qcs/solutions/YueYuan/research/validator/self_test.py
python3 tracks/qcs/solutions/YueYuan/research/attempts/attempt-004/run_candidate.py --fast --out /tmp/yueyuan-attempt004-candidate.json
python3 tracks/qcs/solutions/YueYuan/research/attempts/attempt-004/run_hardware_dry_run.py --out /tmp/yueyuan-attempt004-hardware --shots 256
python3 tracks/qcs/solutions/YueYuan/research/attempts/attempt-004/run_device_informed_focus.py --out /tmp/yueyuan-attempt004-device-informed --fast
python3 tracks/qcs/solutions/YueYuan/research/attempts/attempt-004/run_invariant_probe.py --out /tmp/yueyuan-attempt004-invariant
git diff --check
# Run the local private-marker scan with exact private markers kept out of
# committed docs. Expected output: no hits.
```

Expected: tests and commands pass; private-marker scan returns no hits.

- [ ] **Step 5: Commit docs and ledger**

```bash
git add tracks/qcs/solutions/YueYuan/research/attempts/attempt-004/README.md tracks/qcs/solutions/YueYuan/research/attempts/attempt-004/REPORT.md
git add -f docs/superpowers/snapshots/2026-07-29-yueyuan-solution-version-ledger.md
git commit -m "Document device-informed recovery and invariant probe"
```

- [ ] **Step 6: Publish PR update**

Update PR #203 with the current tree using normal push if possible, or the
existing GitHub API tree-commit fallback if HTTPS push times out. Update the PR
body with:

- device-informed adaptive method summary;
- invariant rank probe summary;
- fresh verification counts;
- unchanged no-real-hardware limitation;
- sensitive-marker scan result.
