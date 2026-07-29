# VQETape Prototype Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a tested Python prototype that compiles exact 1D TFIM VQE energy-and-gradient kernels into unrolled, scan, rematerialized, and segmented-adjoint variants, benchmarks them in fresh processes, and selects a memory-feasible Pareto candidate.

**Architecture:** A small semantic frontend validates a `TFIMVQESpec`, numerical kernels generate state-vector oracle programs, and an executable factory applies the requested control-flow and adjoint schedule. A fresh-process benchmark layer measures every valid candidate, after which a pure selection layer computes the Pareto frontier and minimizes compile-plus-iteration cost.

**Tech Stack:** Python 3.12, JAX, NumPy, pytest, psutil, standard-library dataclasses/JSON/subprocess.

## Global Constraints

- The first prototype is exact and must not use MPS truncation or stochastic sampling.
- Supported circuits are open-boundary, one-dimensional `RZZ`-then-`RX` VQE layers.
- Supported Hamiltonian is the open-boundary 1D TFIM.
- Parameter layout is `(depth, 2, nqubits)`; `theta[layer, 0, -1]` is unused padding and its gradient must be exactly zero.
- Every timing must synchronize JAX results before stopping the timer.
- Every measured candidate must execute in a fresh subprocess.
- CPU peak RSS and JAX executable memory analysis must be labelled separately; neither may be described as true GPU peak memory.
- Numerical tolerances are `energy_atol=1e-5`, `gradient_rtol=1e-4` for `complex64`, and `energy_atol=1e-10`, `gradient_rtol=1e-9` for `complex128`.
- The code must remain usable without TensorCircuit-NG or cuTensorNet installed.

---

## Planned File Structure

```text
pyproject.toml                         Package metadata and dependencies
.gitignore                            Local environments, caches, and reports
README.md                             Setup, CLI, limitations, and terminology
src/vqetape/__init__.py               Stable public API exports
src/vqetape/spec.py                   Validated immutable request dataclasses
src/vqetape/kernels.py                Exact gates, state evolution, and TFIM energy
src/vqetape/programs.py               Unrolled, scan, remat, and segmented executables
src/vqetape/estimate.py               Static state/tape/gate-work estimates
src/vqetape/candidates.py             Candidate enumeration
src/vqetape/metrics.py                Timing, synchronization, and statistics
src/vqetape/worker.py                 One-candidate subprocess benchmark entry point
src/vqetape/benchmark.py              Parent-process orchestration and JSON protocol
src/vqetape/selection.py              Correctness, Pareto, and K-aware selection
src/vqetape/compiler.py               End-to-end compile request orchestration
src/vqetape/cli.py                    Reproducible command-line experiment
tests/test_spec.py                    Dataclass validation tests
tests/test_kernels.py                 State, energy, and finite-difference tests
tests/test_programs.py                Program and adjoint equivalence tests
tests/test_estimate_candidates.py     Static estimate and enumeration tests
tests/test_metrics_selection.py       Statistics and Pareto tests
tests/test_benchmark.py               Fresh-process benchmark protocol tests
tests/test_compiler_cli.py            End-to-end compile and CLI tests
```

---

### Task 1: Package Skeleton and Validated Specifications

**Files:**
- Create: `pyproject.toml`
- Create: `.gitignore`
- Create: `src/vqetape/__init__.py`
- Create: `src/vqetape/spec.py`
- Create: `tests/test_spec.py`

**Interfaces:**
- Produces: `TFIMVQESpec`, `ProgramConfig`, `CompileRequest`, `CorrectnessTolerance`, and `dtype_bytes`.
- Later tasks consume the exact dataclass fields and validation behavior defined here.

- [x] **Step 1: Write specification tests**

```python
import pytest

from vqetape.spec import CompileRequest, ProgramConfig, TFIMVQESpec, dtype_bytes


def test_tfim_spec_parameter_shape_and_count():
    spec = TFIMVQESpec(nqubits=5, depth=3)
    assert spec.parameter_shape == (3, 2, 5)
    assert spec.active_parameter_count == 3 * (2 * 5 - 1)


@pytest.mark.parametrize(
    ("kwargs", "message"),
    [
        ({"nqubits": 1}, "nqubits"),
        ({"depth": 0}, "depth"),
        ({"dtype": "float32"}, "dtype"),
        ({"initial_state": "bell"}, "initial_state"),
    ],
)
def test_tfim_spec_rejects_invalid_values(kwargs, message):
    with pytest.raises(ValueError, match=message):
        TFIMVQESpec(**kwargs)


def test_segmented_config_requires_scan_and_segment_length():
    with pytest.raises(ValueError, match="segmented"):
        ProgramConfig(control_flow="unrolled", adjoint="segmented", unroll=1, segment_length=2)
    with pytest.raises(ValueError, match="segment_length"):
        ProgramConfig(control_flow="scan", adjoint="segmented", unroll=1)


def test_compile_request_requires_positive_budget_and_steps():
    spec = TFIMVQESpec(nqubits=4, depth=2)
    with pytest.raises(ValueError, match="memory_budget_bytes"):
        CompileRequest(spec=spec, memory_budget_bytes=0, expected_vqe_steps=10)
    with pytest.raises(ValueError, match="expected_vqe_steps"):
        CompileRequest(spec=spec, memory_budget_bytes=1024, expected_vqe_steps=0)


def test_dtype_bytes():
    assert dtype_bytes("complex64") == 8
    assert dtype_bytes("complex128") == 16
```

- [x] **Step 2: Run the tests and verify the missing-package failure**

Run: `python -m pytest tests/test_spec.py -q`

Expected: collection fails because `vqetape` does not exist.

- [x] **Step 3: Add package metadata and immutable validated dataclasses**

`pyproject.toml` must declare a `src` package, Python `>=3.12`, runtime
dependencies on `jax`, `numpy`, and `psutil`, a `test` extra containing
`pytest`, and a `vqetape` console script targeting `vqetape.cli:main`.

`src/vqetape/spec.py` must define:

```python
from __future__ import annotations

from dataclasses import dataclass
from math import isfinite
from typing import Literal

DTypeName = Literal["complex64", "complex128"]


def dtype_bytes(dtype: DTypeName) -> int:
    return {"complex64": 8, "complex128": 16}[dtype]


@dataclass(frozen=True)
class TFIMVQESpec:
    nqubits: int
    depth: int
    coupling: float = 1.0
    field: float = 1.0
    initial_state: Literal["zero", "plus"] = "plus"
    dtype: DTypeName = "complex64"

    def __post_init__(self) -> None:
        if self.nqubits < 2:
            raise ValueError("nqubits must be at least 2")
        if self.depth < 1:
            raise ValueError("depth must be positive")
        if not isfinite(self.coupling) or not isfinite(self.field):
            raise ValueError("coupling and field must be finite")
        if self.initial_state not in ("zero", "plus"):
            raise ValueError("unsupported initial_state")
        if self.dtype not in ("complex64", "complex128"):
            raise ValueError("unsupported dtype")

    @property
    def parameter_shape(self) -> tuple[int, int, int]:
        return (self.depth, 2, self.nqubits)

    @property
    def active_parameter_count(self) -> int:
        return self.depth * (2 * self.nqubits - 1)
```

Add the other dataclasses with the exact fields described in
`docs/plans/2026-07-28-vqetape-design.md`.

- [x] **Step 4: Run the tests**

Run: `python -m pytest tests/test_spec.py -q`

Expected: all tests pass.

- [x] **Step 5: Commit**

```bash
git add pyproject.toml .gitignore src/vqetape tests/test_spec.py
git commit -m "feat: add VQETape package and validated specs"
```

---

### Task 2: Exact VQE Numerical Kernels

**Files:**
- Create: `src/vqetape/kernels.py`
- Create: `tests/test_kernels.py`

**Interfaces:**
- Consumes: `TFIMVQESpec`.
- Produces: `initial_state(spec)`, `apply_rx(state, angle, wire, nqubits)`,
  `apply_rzz(state, angle, wire0, wire1, nqubits)`, `apply_layer(state, theta_layer, spec)`,
  `tfim_energy(state, spec)`, and `unrolled_energy(theta, spec)`.

- [x] **Step 1: Write kernel correctness tests**

```python
import jax
import jax.numpy as jnp
import numpy as np

from vqetape.kernels import initial_state, tfim_energy, unrolled_energy
from vqetape.spec import TFIMVQESpec


def test_initial_states_are_normalized():
    for name in ("zero", "plus"):
        spec = TFIMVQESpec(nqubits=4, depth=1, initial_state=name)
        state = initial_state(spec)
        np.testing.assert_allclose(np.asarray(jnp.vdot(state, state)), 1.0, atol=1e-6)


def test_plus_state_tfim_energy_at_zero_parameters():
    spec = TFIMVQESpec(nqubits=4, depth=1, initial_state="plus")
    theta = jnp.zeros(spec.parameter_shape)
    energy = unrolled_energy(theta, spec)
    np.testing.assert_allclose(np.asarray(energy), -4.0, atol=1e-6)


def test_padding_rzz_parameter_has_zero_gradient():
    spec = TFIMVQESpec(nqubits=4, depth=2)
    theta = jnp.arange(np.prod(spec.parameter_shape), dtype=jnp.float32).reshape(spec.parameter_shape) / 20
    gradient = jax.grad(unrolled_energy)(theta, spec)
    np.testing.assert_array_equal(np.asarray(gradient[:, 0, -1]), np.zeros(spec.depth))


def test_gradient_matches_central_difference():
    spec = TFIMVQESpec(nqubits=3, depth=2, dtype="complex128")
    theta = jnp.linspace(-0.2, 0.3, np.prod(spec.parameter_shape), dtype=jnp.float64).reshape(spec.parameter_shape)
    gradient = jax.grad(unrolled_energy)(theta, spec)
    index = (1, 1, 2)
    step = 1e-5
    delta = jnp.zeros_like(theta).at[index].set(step)
    finite_difference = (unrolled_energy(theta + delta, spec) - unrolled_energy(theta - delta, spec)) / (2 * step)
    np.testing.assert_allclose(np.asarray(gradient[index]), np.asarray(finite_difference), rtol=1e-6, atol=1e-7)
```

- [x] **Step 2: Verify failure**

Run: `JAX_ENABLE_X64=1 python -m pytest tests/test_kernels.py -q`

Expected: import fails because `vqetape.kernels` does not exist.

- [x] **Step 3: Implement exact gates and TFIM energy**

Use explicit small gate matrices and axis permutations. `tfim_energy` must apply
Pauli actions to the state and sum local expectations without constructing a
dense Hamiltonian. Return a real JAX scalar.

- [x] **Step 4: Run tests**

Run: `JAX_ENABLE_X64=1 python -m pytest tests/test_kernels.py -q`

Expected: all tests pass.

- [x] **Step 5: Commit**

```bash
git add src/vqetape/kernels.py tests/test_kernels.py
git commit -m "feat: add exact TFIM VQE kernels"
```

---

### Task 3: Unrolled, Scan, and Rematerialized Programs

**Files:**
- Create: `src/vqetape/programs.py`
- Create: `tests/test_programs.py`

**Interfaces:**
- Consumes: `TFIMVQESpec`, `ProgramConfig`, and kernel functions.
- Produces: `build_energy_function(spec, config)` and
  `build_value_and_grad(spec, config)`.

- [x] **Step 1: Write equivalence tests**

```python
import jax
import jax.numpy as jnp
import numpy as np
import pytest

from vqetape.programs import build_value_and_grad
from vqetape.spec import ProgramConfig, TFIMVQESpec


@pytest.mark.parametrize("unroll", [1, 2, 4])
@pytest.mark.parametrize("adjoint", ["default", "remat"])
def test_scan_program_matches_unrolled(unroll, adjoint):
    spec = TFIMVQESpec(nqubits=4, depth=4)
    theta = jnp.linspace(-0.4, 0.5, np.prod(spec.parameter_shape), dtype=jnp.float32).reshape(spec.parameter_shape)
    reference = build_value_and_grad(
        spec, ProgramConfig(control_flow="unrolled", adjoint="default", unroll=1)
    )
    candidate = build_value_and_grad(
        spec, ProgramConfig(control_flow="scan", adjoint=adjoint, unroll=unroll)
    )
    ref_energy, ref_gradient = reference(theta)
    energy, gradient = candidate(theta)
    np.testing.assert_allclose(np.asarray(energy), np.asarray(ref_energy), atol=1e-5)
    np.testing.assert_allclose(np.asarray(gradient), np.asarray(ref_gradient), rtol=1e-4, atol=1e-5)
```

- [x] **Step 2: Verify failure**

Run: `python -m pytest tests/test_programs.py -q`

Expected: import fails because `vqetape.programs` does not exist.

- [x] **Step 3: Implement program builders**

`build_energy_function` must close over the immutable spec so it is not passed
as a traced JAX value. The unrolled variant calls `unrolled_energy`. The scan
variant initializes the state, calls `jax.lax.scan` over parameter layers, and
then calls `tfim_energy`. For `adjoint="remat"`, wrap the scan layer body with
`jax.checkpoint`. `build_value_and_grad` returns
`jax.jit(jax.value_and_grad(energy_function))`.

- [x] **Step 4: Run tests**

Run: `python -m pytest tests/test_programs.py -q`

Expected: all tests pass.

- [x] **Step 5: Commit**

```bash
git add src/vqetape/programs.py tests/test_programs.py
git commit -m "feat: add unrolled and scan VQE programs"
```

---

### Task 4: Segmented Custom Adjoint

**Files:**
- Modify: `src/vqetape/programs.py`
- Modify: `tests/test_programs.py`

**Interfaces:**
- Extends: `build_value_and_grad` for `ProgramConfig(adjoint="segmented")`.
- Produces: an exact segmented custom VJP whose padded `RZZ` gradients remain zero.

- [x] **Step 1: Add segmented equivalence tests**

```python
@pytest.mark.parametrize("depth", [3, 4, 7])
@pytest.mark.parametrize("segment_length", [1, 2, 3])
def test_segmented_adjoint_matches_unrolled(depth, segment_length):
    spec = TFIMVQESpec(nqubits=3, depth=depth)
    theta = jnp.linspace(-0.2, 0.4, np.prod(spec.parameter_shape), dtype=jnp.float32).reshape(spec.parameter_shape)
    reference = build_value_and_grad(
        spec, ProgramConfig(control_flow="unrolled", adjoint="default", unroll=1)
    )
    candidate = build_value_and_grad(
        spec,
        ProgramConfig(
            control_flow="scan",
            adjoint="segmented",
            unroll=1,
            segment_length=segment_length,
        ),
    )
    ref_energy, ref_gradient = reference(theta)
    energy, gradient = candidate(theta)
    np.testing.assert_allclose(np.asarray(energy), np.asarray(ref_energy), atol=1e-5)
    np.testing.assert_allclose(np.asarray(gradient), np.asarray(ref_gradient), rtol=1e-4, atol=1e-5)
    np.testing.assert_array_equal(np.asarray(gradient[:, 0, -1]), np.zeros(depth))
```

- [x] **Step 2: Verify failure**

Run: `python -m pytest tests/test_programs.py -q`

Expected: segmented configurations fail as unsupported.

- [x] **Step 3: Implement a shape-static segmented custom VJP**

Pad the depth to `ceil(depth / segment_length) * segment_length`, create a
segment function that applies masked layers, and define a custom VJP around the
full segmented evolution. The forward residual contains the parameters and
only segment-boundary states. The backward rule uses a reverse `lax.scan`; for
each segment it calls `jax.vjp` on the rematerialized segment function,
propagates the state cotangent, and writes the segment parameter cotangent into
the padded gradient buffer before truncating it to the original depth.

- [x] **Step 4: Run segmented and full tests**

Run: `python -m pytest tests/test_programs.py -q`

Expected: all program variants pass.

- [x] **Step 5: Commit**

```bash
git add src/vqetape/programs.py tests/test_programs.py
git commit -m "feat: add segmented VQE adjoint schedule"
```

---

### Task 5: Static Estimates and Candidate Enumeration

**Files:**
- Create: `src/vqetape/estimate.py`
- Create: `src/vqetape/candidates.py`
- Create: `tests/test_estimate_candidates.py`

**Interfaces:**
- Consumes: `TFIMVQESpec`, `CompileRequest`, and `ProgramConfig`.
- Produces: `StaticEstimate`, `estimate_program(spec, config)`,
  `segment_lengths(depth)`, and `enumerate_candidates(request)`.

- [x] **Step 1: Write deterministic enumeration tests**

```python
from vqetape.candidates import enumerate_candidates, segment_lengths
from vqetape.estimate import estimate_program
from vqetape.spec import CompileRequest, ProgramConfig, TFIMVQESpec


def test_segment_lengths_include_endpoints_and_sqrt_neighbors():
    assert segment_lengths(10) == (1, 2, 3, 4, 5, 10)


def test_segmented_estimate_is_smaller_than_save_all_for_deep_chain():
    spec = TFIMVQESpec(nqubits=8, depth=100)
    default = estimate_program(
        spec, ProgramConfig(control_flow="scan", adjoint="default", unroll=1)
    )
    segmented = estimate_program(
        spec,
        ProgramConfig(
            control_flow="scan", adjoint="segmented", unroll=1, segment_length=10
        ),
    )
    assert segmented.saved_boundary_upper_bound_bytes < default.saved_boundary_upper_bound_bytes
    assert segmented.estimated_recompute_gate_applications > default.estimated_recompute_gate_applications


def test_candidate_enumeration_is_unique_and_memory_filtered():
    request = CompileRequest(
        spec=TFIMVQESpec(nqubits=6, depth=8),
        memory_budget_bytes=2 * 1024**3,
        expected_vqe_steps=100,
    )
    candidates = enumerate_candidates(request)
    assert len(candidates) == len(set(candidates))
    assert all(estimate_program(request.spec, item).saved_boundary_upper_bound_bytes <= request.memory_budget_bytes for item in candidates)
```

- [x] **Step 2: Verify failure**

Run: `python -m pytest tests/test_estimate_candidates.py -q`

Expected: imports fail.

- [x] **Step 3: Implement estimates and enumeration**

Use explicit gate counts:

\[
G_{\mathrm{layer}}=(n-1)+n=2n-1.
\]

Default scan uses a conservative `depth + 1` saved-state upper bound.
Rematerialized scan uses two boundary states plus one body workspace.
Segmented uses `ceil(depth / segment_length) + segment_length + 2`.
Enumeration must always include the unrolled reference and remove duplicate
configs caused by clipping unroll factors.

- [x] **Step 4: Run tests**

Run: `python -m pytest tests/test_estimate_candidates.py -q`

Expected: all tests pass.

- [x] **Step 5: Commit**

```bash
git add src/vqetape/estimate.py src/vqetape/candidates.py tests/test_estimate_candidates.py
git commit -m "feat: estimate and enumerate VQETape programs"
```

---

### Task 6: Statistics, Correctness, and Pareto Selection

**Files:**
- Create: `src/vqetape/metrics.py`
- Create: `src/vqetape/selection.py`
- Create: `tests/test_metrics_selection.py`

**Interfaces:**
- Produces: `median_and_mad`, `CandidateResult`, `correctness_error`,
  `pareto_frontier`, and `select_for_horizon`.

- [x] **Step 1: Write pure-function tests**

```python
import math

from vqetape.metrics import median_and_mad
from vqetape.selection import CandidateResult, pareto_frontier, select_for_horizon
from vqetape.spec import ProgramConfig


def result(name, compile_s, warm_s, memory):
    return CandidateResult(
        config=ProgramConfig(control_flow=name, adjoint="default", unroll=1),
        compile_seconds=compile_s,
        first_execute_seconds=0.1,
        warm_seconds_median=warm_s,
        warm_seconds_mad=0.0,
        peak_rss_bytes=memory,
        energy_abs_error=0.0,
        gradient_relative_l2_error=0.0,
        valid=True,
    )


def test_median_and_mad():
    assert median_and_mad([1.0, 2.0, 100.0]) == (2.0, 1.0)


def test_pareto_frontier_removes_dominated_result():
    fast = result("unrolled", 2.0, 1.0, 100)
    dominated = result("scan", 3.0, 2.0, 120)
    assert pareto_frontier([fast, dominated]) == [fast]


def test_horizon_selection_accounts_for_compile_amortization():
    low_cold = result("unrolled", 1.0, 2.0, 100)
    high_throughput = result("scan", 20.0, 1.0, 100)
    assert select_for_horizon([low_cold, high_throughput], 2).config == low_cold.config
    assert select_for_horizon([low_cold, high_throughput], 100).config == high_throughput.config
```

- [x] **Step 2: Verify failure**

Run: `python -m pytest tests/test_metrics_selection.py -q`

Expected: imports fail.

- [x] **Step 3: Implement statistics and selection**

`CandidateResult` must support `to_dict()` and `from_dict()` without losing
configuration fields. Invalid candidates and candidates over the measured
memory budget must not appear in the selectable frontier. Relative gradient
error must use `max(1, ||g_ref||_2)` as the denominator.

- [x] **Step 4: Run tests**

Run: `python -m pytest tests/test_metrics_selection.py -q`

Expected: all tests pass.

- [x] **Step 5: Commit**

```bash
git add src/vqetape/metrics.py src/vqetape/selection.py tests/test_metrics_selection.py
git commit -m "feat: add correctness and Pareto selection"
```

---

### Task 7: Fresh-Process Candidate Benchmarking

**Files:**
- Create: `src/vqetape/worker.py`
- Create: `src/vqetape/benchmark.py`
- Create: `tests/test_benchmark.py`

**Interfaces:**
- Consumes: a serializable spec, config, deterministic seed, and warm repeat count.
- Produces: `benchmark_candidate(...) -> CandidateResult`.

- [x] **Step 1: Write subprocess protocol tests**

```python
from vqetape.benchmark import benchmark_candidate
from vqetape.spec import ProgramConfig, TFIMVQESpec


def test_candidate_runs_in_fresh_process_and_returns_finite_metrics():
    spec = TFIMVQESpec(nqubits=3, depth=2)
    result = benchmark_candidate(
        spec=spec,
        config=ProgramConfig(control_flow="scan", adjoint="default", unroll=1),
        seed=7,
        warm_repeats=2,
        timeout_seconds=120,
    )
    assert result.valid
    assert result.compile_seconds >= 0
    assert result.first_execute_seconds >= 0
    assert result.warm_seconds_median > 0
    assert result.peak_rss_bytes > 0
    assert result.worker_pid != result.parent_pid
```

- [x] **Step 2: Verify failure**

Run: `python -m pytest tests/test_benchmark.py -q`

Expected: imports fail.

- [x] **Step 3: Implement worker and parent protocol**

The parent invokes:

```text
python -m vqetape.worker --request-json <path> --result-json <path>
```

using a temporary directory. The worker:

1. reconstructs spec and config;
2. creates deterministic parameters with NumPy;
3. builds and lowers the executable;
4. times compilation;
5. times and synchronizes first execution;
6. runs synchronized warm repetitions;
7. queries executable memory analysis when present;
8. records `resource.getrusage(...).ru_maxrss` with platform-correct units;
9. writes one JSON result atomically.

The parent must convert timeout, non-zero exit, missing JSON, and malformed
JSON into invalid `CandidateResult` values with a useful `failure` string.

- [x] **Step 4: Run tests**

Run: `python -m pytest tests/test_benchmark.py -q`

Expected: the worker PID differs from the test process and all tests pass.

- [x] **Step 5: Commit**

```bash
git add src/vqetape/worker.py src/vqetape/benchmark.py tests/test_benchmark.py
git commit -m "feat: benchmark VQE candidates in fresh processes"
```

---

### Task 8: End-to-End Compiler and CLI

**Files:**
- Create: `src/vqetape/compiler.py`
- Create: `src/vqetape/cli.py`
- Modify: `src/vqetape/__init__.py`
- Create: `tests/test_compiler_cli.py`
- Create: `README.md`

**Interfaces:**
- Consumes: `CompileRequest`.
- Produces: `CompileResult`, `compile_vqe`, CLI JSON report, and selected executable.

- [x] **Step 1: Write end-to-end tests**

```python
import json
import subprocess
import sys

import jax.numpy as jnp

from vqetape.compiler import compile_vqe
from vqetape.spec import CompileRequest, TFIMVQESpec


def test_compile_vqe_selects_valid_executable():
    request = CompileRequest(
        spec=TFIMVQESpec(nqubits=3, depth=2),
        memory_budget_bytes=1024**3,
        expected_vqe_steps=5,
        warm_repeats=2,
    )
    compiled = compile_vqe(request)
    theta = jnp.zeros(request.spec.parameter_shape)
    energy, gradient = compiled.executable(theta)
    assert energy.shape == ()
    assert gradient.shape == request.spec.parameter_shape
    assert compiled.selected.valid
    assert compiled.selected in compiled.pareto


def test_cli_writes_machine_readable_report(tmp_path):
    report = tmp_path / "report.json"
    completed = subprocess.run(
        [
            sys.executable,
            "-m",
            "vqetape.cli",
            "--nqubits",
            "3",
            "--depth",
            "2",
            "--memory-budget-gib",
            "1",
            "--expected-steps",
            "5",
            "--warm-repeats",
            "2",
            "--output",
            str(report),
        ],
        check=False,
        capture_output=True,
        text=True,
        timeout=180,
    )
    assert completed.returncode == 0, completed.stderr
    payload = json.loads(report.read_text())
    assert payload["selected"]["valid"] is True
    assert payload["measurement_notes"]["peak_rss"] == "process peak RSS, not GPU peak memory"
```

- [x] **Step 2: Verify failure**

Run: `python -m pytest tests/test_compiler_cli.py -q`

Expected: imports fail.

- [x] **Step 3: Implement compiler orchestration**

`compile_vqe` must:

1. enumerate statically feasible candidates;
2. benchmark the unrolled reference first;
3. benchmark all other candidates;
4. calculate errors against the reference outputs using the same deterministic
   parameter vector;
5. mark candidates outside tolerance invalid;
6. calculate the Pareto frontier;
7. select the minimum compile-plus-horizon candidate;
8. rebuild the selected executable in the parent process;
9. return all results and a JSON-serializable report.

- [x] **Step 4: Implement CLI and documentation**

The README must include:

- installation with a Python 3.12 virtual environment;
- a minimal API example;
- a CLI example;
- parameter and Hamiltonian conventions;
- explicit explanation of cold, first-execute, warm, RSS, and JAX memory fields;
- first-prototype limitations;
- the two research decision gates.

- [x] **Step 5: Run all tests**

Run: `JAX_ENABLE_X64=1 python -m pytest -q`

Expected: all tests pass.

- [x] **Step 6: Run a reproducible experiment**

Run:

```bash
python -m vqetape.cli \
  --nqubits 4 \
  --depth 4 \
  --memory-budget-gib 2 \
  --expected-steps 100 \
  --warm-repeats 5 \
  --output outputs/vqetape-smoke-report.json
```

Expected: the command exits zero, every valid candidate is numerically
equivalent to the reference within tolerance, and the output contains a
non-empty Pareto frontier.

- [x] **Step 7: Commit**

```bash
git add README.md src/vqetape tests/test_compiler_cli.py outputs/vqetape-smoke-report.json
git commit -m "feat: compile and report VQETape candidates"
```

---

## Self-Review Record

- **Spec coverage:** The plan covers all initial-repository success criteria in
  the approved design. Direct bra-H-ket contraction and cuTensorNet are
  explicitly later phases, not silently omitted prototype requirements.
- **Placeholder scan:** The plan contains no `TBD`, implementation `TODO`, or
  unspecified error-handling step.
- **Type consistency:** `TFIMVQESpec`, `ProgramConfig`, `CompileRequest`,
  `CandidateResult`, `build_value_and_grad`, `benchmark_candidate`, and
  `compile_vqe` retain the same names and responsibilities across tasks.
- **Execution mode:** Implement inline in the current session because the
  current collaboration policy does not authorize subagent dispatch.
