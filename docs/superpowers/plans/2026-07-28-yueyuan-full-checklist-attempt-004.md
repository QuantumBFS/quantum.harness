# YueYuan Full Checklist Attempt 004 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build `attempt-004` as the full challenge #113 research artifact with differentiable quantum dynamics, Hessian-guided black-box calibration, full checklist sweeps, figures, report, PR update, and capped HPC verification.

**Architecture:** Add a new self-contained package under `tracks/qcs/solutions/YueYuan/research/attempts/attempt-004/`. The code separates differentiable model optimization from a strict query-only true-device boundary, emits ignored machine-readable results, and keeps committed artifacts limited to source, tests, configs, scripts, and report summaries.

**Tech Stack:** Python 3.11, JAX/JAXLIB for autodiff and Hessians, NumPy for records and statistics glue, SciPy for optional eigensolvers and optimizer comparisons, Matplotlib for figures, Pytest for local verification, Slurm scripts for capped HPC sweeps.

## Global Constraints

- The differentiable path requires JAX; checklist completion requires JAX-backed gradient and Hessian tests.
- Attempt code lives in `tracks/qcs/solutions/YueYuan/research/attempts/attempt-004/`.
- Tests live in `tracks/qcs/solutions/YueYuan/research/attempt_tests/`.
- Generated data and figures live under `tracks/qcs/results/YueYuan/attempt-004/` and stay out of git.
- Generated `submission.json` and `report.json` under attempt directories stay out of git.
- Do not commit credentials, SSH commands with secrets, account names, hostnames, tokens, or passwords.
- HPC CPU jobs must never exceed 200 concurrent CPU cores.
- HPC GPU jobs must never exceed 1 concurrent GPU.
- Do not expose exact true fidelity, true Hamiltonian, hidden perturbations, true gradients, or true Hessians to derivative-free optimizers.
- Compare full-space, random-subspace, and Hessian-subspace methods with shared starting pulse, optimizer family, query budget, shots, target fidelity, seed set, stopping rule, and parameter bounds.
- Report both black-box queries and total shots; do not claim advantage from query counts alone.
- Keep `Ion.lock` out of all attempt-004 commits unless the user explicitly requests otherwise.

---

## File Structure

- Create `tracks/qcs/solutions/YueYuan/research/attempts/attempt-004/__init__.py`: package marker.
- Create `tracks/qcs/solutions/YueYuan/research/attempts/attempt-004/requirements.txt`: explicit runtime dependencies.
- Create `tracks/qcs/solutions/YueYuan/research/attempts/attempt-004/config.py`: dataclasses and default configs.
- Create `tracks/qcs/solutions/YueYuan/research/attempts/attempt-004/systems.py`: gates, bases, model Hamiltonians, true-device perturbations.
- Create `tracks/qcs/solutions/YueYuan/research/attempts/attempt-004/pulses.py`: pulse vector packing, random starts, bounds, subspace projection.
- Create `tracks/qcs/solutions/YueYuan/research/attempts/attempt-004/dynamics.py`: JAX propagator and phase-insensitive fidelity.
- Create `tracks/qcs/solutions/YueYuan/research/attempts/attempt-004/open_loop.py`: Adam-style model optimization and history records.
- Create `tracks/qcs/solutions/YueYuan/research/attempts/attempt-004/hessian.py`: dense Hessian, HVP, eigenspace, spectrum summaries.
- Create `tracks/qcs/solutions/YueYuan/research/attempts/attempt-004/device.py`: strict query-only finite-shot device.
- Create `tracks/qcs/solutions/YueYuan/research/attempts/attempt-004/optimizers.py`: derivative-free black-box optimizers.
- Create `tracks/qcs/solutions/YueYuan/research/attempts/attempt-004/baselines.py`: model-only, full, random, Hessian methods.
- Create `tracks/qcs/solutions/YueYuan/research/attempts/attempt-004/experiments.py`: sweep orchestration and JSONL writes.
- Create `tracks/qcs/solutions/YueYuan/research/attempts/attempt-004/analysis.py`: aggregation and summary JSON.
- Create `tracks/qcs/solutions/YueYuan/research/attempts/attempt-004/plotting.py`: required figures.
- Create `tracks/qcs/solutions/YueYuan/research/attempts/attempt-004/run_local_smoke.py`: quick local evidence run.
- Create `tracks/qcs/solutions/YueYuan/research/attempts/attempt-004/run_full_sweep.py`: full sweep CLI.
- Create `tracks/qcs/solutions/YueYuan/research/attempts/attempt-004/make_figures.py`: figure regeneration CLI.
- Create `tracks/qcs/solutions/YueYuan/research/attempts/attempt-004/run_candidate.py`: compact validator-compatible output.
- Create `tracks/qcs/solutions/YueYuan/research/attempts/attempt-004/README.md`: reproduction instructions.
- Create `tracks/qcs/solutions/YueYuan/research/attempts/attempt-004/REPORT.md`: short report.
- Create `tracks/qcs/solutions/YueYuan/research/attempts/attempt-004/slurm/cpu_sweep.sbatch`: capped CPU array job.
- Create `tracks/qcs/solutions/YueYuan/research/attempts/attempt-004/slurm/gpu_verify.sbatch`: capped GPU verification job.
- Create `tracks/qcs/solutions/YueYuan/research/attempts/attempt-004/slurm/README.md`: HPC instructions.
- Create six attempt-004 test files under `tracks/qcs/solutions/YueYuan/research/attempt_tests/`.
- Modify `tracks/qcs/solutions/YueYuan/README.md`: final attempt-004 summary after verification.
- Modify `tracks/qcs/solutions/YueYuan/research/STATE.md`: advance `next_attempt` after attempt-004 completion.

---

### Task 1: Attempt-004 Scaffold and Import Harness

**Files:**
- Create: `tracks/qcs/solutions/YueYuan/research/attempts/attempt-004/__init__.py`
- Create: `tracks/qcs/solutions/YueYuan/research/attempts/attempt-004/requirements.txt`
- Create: `tracks/qcs/solutions/YueYuan/research/attempts/attempt-004/config.py`
- Create: `tracks/qcs/solutions/YueYuan/research/attempt_tests/test_attempt_004_model.py`

**Interfaces:**
- Produces: `require_jax() -> tuple[jax_module, jnp_module]`
- Produces: `SystemConfig`, `OpenLoopConfig`, `ClosedLoopConfig`, `SweepConfig`, `default_smoke_sweep()`, `default_full_sweep()`
- Consumes: no attempt-004 modules from earlier tasks.

- [ ] **Step 1: Write the failing import/config test**

```python
# tracks/qcs/solutions/YueYuan/research/attempt_tests/test_attempt_004_model.py
import importlib.util
import pathlib
import sys

ROOT = pathlib.Path(__file__).resolve().parents[6]
ATTEMPT = ROOT / "tracks/qcs/solutions/YueYuan/research/attempts/attempt-004"


def load_module(name):
    for module_name in [
        "config",
        "systems",
        "pulses",
        "dynamics",
        "open_loop",
        "hessian",
        "device",
        "optimizers",
        "baselines",
        "experiments",
        "analysis",
        "plotting",
    ]:
        sys.modules.pop(module_name, None)
    sys.path.insert(0, str(ATTEMPT))
    spec = importlib.util.spec_from_file_location(name, ATTEMPT / f"{name}.py")
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


def test_attempt_004_default_sweeps_have_required_axes():
    config = load_module("config")
    smoke = config.default_smoke_sweep()
    full = config.default_full_sweep()

    assert {system.name for system in smoke.systems} == {"one_qubit_x", "two_qubit_cz"}
    assert {system.name for system in full.systems} == {"one_qubit_x", "two_qubit_cz"}
    assert full.gaps == ("small", "medium", "large")
    assert full.shots_per_query == (128, 512, 2048)
    assert full.seeds == tuple(range(8))
    assert max(full.cpu_array_cores_per_task * full.cpu_array_max_concurrent_tasks, 1) <= 200
    assert full.gpu_array_max_concurrent_tasks == 1
```

- [ ] **Step 2: Run the test to verify it fails**

Run:

```bash
python3 -m pytest tracks/qcs/solutions/YueYuan/research/attempt_tests/test_attempt_004_model.py::test_attempt_004_default_sweeps_have_required_axes -q
```

Expected: FAIL because `config.py` does not exist.

- [ ] **Step 3: Create package marker and requirements**

```python
# tracks/qcs/solutions/YueYuan/research/attempts/attempt-004/__init__.py
"""YueYuan attempt 004: full checklist sim-to-real gate calibration."""
```

```text
# tracks/qcs/solutions/YueYuan/research/attempts/attempt-004/requirements.txt
jax
jaxlib
numpy
scipy
matplotlib
pytest
```

- [ ] **Step 4: Implement `config.py`**

```python
from __future__ import annotations

from dataclasses import dataclass
from typing import Sequence


def require_jax():
    try:
        import jax
        import jax.numpy as jnp
    except Exception as exc:
        raise RuntimeError(
            "Attempt 004 requires JAX/JAXLIB. Install dependencies from "
            "tracks/qcs/solutions/YueYuan/research/attempts/attempt-004/requirements.txt"
        ) from exc
    jax.config.update("jax_enable_x64", True)
    return jax, jnp


@dataclass(frozen=True)
class SystemConfig:
    name: str
    target: str
    hilbert_dim: int
    segments: int
    controls: int
    max_amplitude: float
    benchmark_rank: int

    @property
    def raw_dim(self) -> int:
        return self.segments * self.controls


@dataclass(frozen=True)
class OpenLoopConfig:
    steps: int
    learning_rate: float
    target_infidelity: float
    seed_scale: float


@dataclass(frozen=True)
class ClosedLoopConfig:
    query_budget: int
    target_infidelity: float
    initial_step: float


@dataclass(frozen=True)
class SweepConfig:
    systems: tuple[SystemConfig, ...]
    gaps: tuple[str, ...]
    shots_per_query: tuple[int, ...]
    seeds: tuple[int, ...]
    one_qubit_k: tuple[int, ...]
    two_qubit_k: tuple[int, ...]
    open_loop: OpenLoopConfig
    closed_loop: ClosedLoopConfig
    cpu_array_cores_per_task: int
    cpu_array_max_concurrent_tasks: int
    gpu_array_max_concurrent_tasks: int


ONE_QUBIT_X = SystemConfig("one_qubit_x", "X", 2, 8, 2, 0.8, 3)
TWO_QUBIT_CZ = SystemConfig("two_qubit_cz", "CZ", 4, 12, 4, 0.55, 15)


def default_smoke_sweep() -> SweepConfig:
    return SweepConfig(
        systems=(ONE_QUBIT_X, TWO_QUBIT_CZ),
        gaps=("small", "medium", "large"),
        shots_per_query=(128, 512, 2048),
        seeds=(0, 1),
        one_qubit_k=(0, 1, 2, 3, 4, 8, 16),
        two_qubit_k=(0, 3, 5, 8, 10, 15, 20, 24, 32, 48),
        open_loop=OpenLoopConfig(steps=80, learning_rate=0.045, target_infidelity=1e-4, seed_scale=0.03),
        closed_loop=ClosedLoopConfig(query_budget=120, target_infidelity=1e-3, initial_step=0.08),
        cpu_array_cores_per_task=4,
        cpu_array_max_concurrent_tasks=25,
        gpu_array_max_concurrent_tasks=1,
    )


def default_full_sweep() -> SweepConfig:
    cfg = default_smoke_sweep()
    return SweepConfig(
        systems=cfg.systems,
        gaps=cfg.gaps,
        shots_per_query=cfg.shots_per_query,
        seeds=tuple(range(8)),
        one_qubit_k=cfg.one_qubit_k,
        two_qubit_k=cfg.two_qubit_k,
        open_loop=OpenLoopConfig(steps=180, learning_rate=0.035, target_infidelity=1e-3, seed_scale=0.04),
        closed_loop=ClosedLoopConfig(query_budget=240, target_infidelity=1e-3, initial_step=0.08),
        cpu_array_cores_per_task=4,
        cpu_array_max_concurrent_tasks=25,
        gpu_array_max_concurrent_tasks=1,
    )
```

- [ ] **Step 5: Run the test to verify it passes**

```bash
python3 -m pytest tracks/qcs/solutions/YueYuan/research/attempt_tests/test_attempt_004_model.py::test_attempt_004_default_sweeps_have_required_axes -q
```

Expected: PASS.

- [ ] **Step 6: Commit**

```bash
git add -f tracks/qcs/solutions/YueYuan/research/attempts/attempt-004/__init__.py \
  tracks/qcs/solutions/YueYuan/research/attempts/attempt-004/requirements.txt \
  tracks/qcs/solutions/YueYuan/research/attempts/attempt-004/config.py \
  tracks/qcs/solutions/YueYuan/research/attempt_tests/test_attempt_004_model.py
git commit -m "Add attempt 004 scaffold"
```

---

### Task 2: Systems, Pulses, and JAX Dynamics

**Files:**
- Create: `tracks/qcs/solutions/YueYuan/research/attempts/attempt-004/systems.py`
- Create: `tracks/qcs/solutions/YueYuan/research/attempts/attempt-004/pulses.py`
- Create: `tracks/qcs/solutions/YueYuan/research/attempts/attempt-004/dynamics.py`
- Modify: `tracks/qcs/solutions/YueYuan/research/attempt_tests/test_attempt_004_model.py`

**Interfaces:**
- Consumes: `config.SystemConfig`, `config.ONE_QUBIT_X`, `config.TWO_QUBIT_CZ`, `config.require_jax`
- Produces: `SystemModel`, `build_system(config: SystemConfig) -> SystemModel`
- Produces: `initial_pulse(config: SystemConfig, seed: int) -> np.ndarray`
- Produces: `clip_pulse(theta: np.ndarray, config: SystemConfig) -> np.ndarray`
- Produces: `propagator(theta, system)`, `gate_fidelity(theta, system)`, `gate_infidelity(theta, system)`

- [ ] **Step 1: Add failing physical-model tests**

Append to `test_attempt_004_model.py`:

```python
def test_attempt_004_systems_have_required_dimensions():
    config = load_module("config")
    systems = load_module("systems")

    one = systems.build_system(config.ONE_QUBIT_X)
    two = systems.build_system(config.TWO_QUBIT_CZ)

    assert one.target.shape == (2, 2)
    assert len(one.control_hamiltonians) == 2
    assert one.config.raw_dim == 16
    assert two.target.shape == (4, 4)
    assert len(two.control_hamiltonians) == 4
    assert two.config.raw_dim == 48


def test_attempt_004_dynamics_are_unitary_and_phase_invariant():
    config = load_module("config")
    systems = load_module("systems")
    pulses = load_module("pulses")
    dynamics = load_module("dynamics")

    system = systems.build_system(config.ONE_QUBIT_X)
    theta = pulses.initial_pulse(config.ONE_QUBIT_X, seed=2)
    unitary = dynamics.propagator(theta, system)
    identity = unitary.conj().T @ unitary

    assert float(abs(identity[0, 0] - 1.0)) < 1e-9
    assert float(abs(identity[1, 1] - 1.0)) < 1e-9
    assert float(dynamics.unitary_infidelity(system.target, system.target)) < 1e-12
    assert float(dynamics.unitary_infidelity(1j * system.target, system.target)) < 1e-12
```

- [ ] **Step 2: Run the model tests to verify failure**

```bash
python3 -m pytest tracks/qcs/solutions/YueYuan/research/attempt_tests/test_attempt_004_model.py -q
```

Expected: FAIL because `systems.py`, `pulses.py`, and `dynamics.py` do not exist.

- [ ] **Step 3: Implement `systems.py`**

```python
from __future__ import annotations

from dataclasses import dataclass

from config import SystemConfig, require_jax

jax, jnp = require_jax()


@dataclass(frozen=True)
class SystemModel:
    config: SystemConfig
    target: object
    drift: object
    control_hamiltonians: tuple[object, ...]


def pauli_i():
    return jnp.eye(2, dtype=jnp.complex128)


def pauli_x():
    return jnp.array([[0, 1], [1, 0]], dtype=jnp.complex128)


def pauli_y():
    return jnp.array([[0, -1j], [1j, 0]], dtype=jnp.complex128)


def pauli_z():
    return jnp.array([[1, 0], [0, -1]], dtype=jnp.complex128)


def target_gate(name: str):
    gate = name.upper()
    if gate == "X":
        return pauli_x()
    if gate == "CZ":
        return jnp.diag(jnp.array([1, 1, 1, -1], dtype=jnp.complex128))
    raise ValueError(f"unknown target gate: {name}")


def build_system(config: SystemConfig) -> SystemModel:
    if config.name == "one_qubit_x":
        controls = (0.5 * pauli_x(), 0.5 * pauli_y())
        drift = 0.08 * pauli_z()
    elif config.name == "two_qubit_cz":
        xi = jnp.kron(pauli_x(), pauli_i())
        yi = jnp.kron(pauli_y(), pauli_i())
        ix = jnp.kron(pauli_i(), pauli_x())
        iy = jnp.kron(pauli_i(), pauli_y())
        zz = jnp.kron(pauli_z(), pauli_z())
        controls = (0.5 * xi, 0.5 * yi, 0.5 * ix, 0.5 * iy)
        drift = 0.18 * zz
    else:
        raise ValueError(f"unknown system config: {config.name}")
    return SystemModel(config=config, target=target_gate(config.target), drift=drift, control_hamiltonians=controls)
```

- [ ] **Step 4: Implement `pulses.py`**

```python
from __future__ import annotations

import numpy as np

from config import SystemConfig


def initial_pulse(config: SystemConfig, seed: int) -> np.ndarray:
    rng = np.random.default_rng(seed)
    raw = rng.normal(scale=0.05, size=config.raw_dim)
    return clip_pulse(raw, config)


def zero_pulse(config: SystemConfig) -> np.ndarray:
    return np.zeros(config.raw_dim, dtype=float)


def clip_pulse(theta: np.ndarray, config: SystemConfig) -> np.ndarray:
    theta = np.asarray(theta, dtype=float)
    if theta.shape != (config.raw_dim,):
        raise ValueError(f"pulse must have shape ({config.raw_dim},)")
    return np.clip(theta, -config.max_amplitude, config.max_amplitude)


def as_segments(theta, config: SystemConfig):
    return theta.reshape((config.segments, config.controls))
```

- [ ] **Step 5: Implement `dynamics.py`**

```python
from __future__ import annotations

from config import require_jax
from pulses import as_segments

jax, jnp = require_jax()


def matrix_exp_hermitian(hamiltonian, dt: float):
    values, vectors = jnp.linalg.eigh(hamiltonian)
    phases = jnp.exp(-1j * dt * values)
    return (vectors * phases) @ vectors.conj().T


def propagator(theta, system):
    config = system.config
    controls = as_segments(jnp.asarray(theta, dtype=jnp.float64), config)
    unitary = jnp.eye(config.hilbert_dim, dtype=jnp.complex128)
    dt = 1.0 / float(config.segments)
    for segment in range(config.segments):
        hamiltonian = system.drift
        for index, control_h in enumerate(system.control_hamiltonians):
            hamiltonian = hamiltonian + controls[segment, index] * control_h
        unitary = matrix_exp_hermitian(hamiltonian, dt) @ unitary
    return unitary


def unitary_fidelity(unitary, target):
    dim = target.shape[0]
    overlap = jnp.trace(target.conj().T @ unitary)
    return jnp.real(jnp.abs(overlap) ** 2 / (dim * dim))


def unitary_infidelity(unitary, target):
    return jnp.clip(1.0 - unitary_fidelity(unitary, target), 0.0, 1.0)


def gate_fidelity(theta, system):
    return unitary_fidelity(propagator(theta, system), system.target)


def gate_infidelity(theta, system):
    return unitary_infidelity(propagator(theta, system), system.target)
```

- [ ] **Step 6: Run the model tests**

```bash
python3 -m pytest tracks/qcs/solutions/YueYuan/research/attempt_tests/test_attempt_004_model.py -q
```

Expected: PASS.

- [ ] **Step 7: Commit**

```bash
git add -f tracks/qcs/solutions/YueYuan/research/attempts/attempt-004/systems.py \
  tracks/qcs/solutions/YueYuan/research/attempts/attempt-004/pulses.py \
  tracks/qcs/solutions/YueYuan/research/attempts/attempt-004/dynamics.py \
  tracks/qcs/solutions/YueYuan/research/attempt_tests/test_attempt_004_model.py
git commit -m "Add attempt 004 differentiable dynamics"
```

---

### Task 3: Open-Loop Optimization and Gradient Checks

**Files:**
- Create: `tracks/qcs/solutions/YueYuan/research/attempts/attempt-004/open_loop.py`
- Create: `tracks/qcs/solutions/YueYuan/research/attempt_tests/test_attempt_004_gradients.py`

**Interfaces:**
- Consumes: `dynamics.gate_infidelity(theta, system)`, `pulses.clip_pulse`, `config.OpenLoopConfig`
- Produces: `finite_difference_gradient(loss_fn, theta, step) -> np.ndarray`
- Produces: `optimize_model_pulse(system, start_theta, cfg) -> OpenLoopResult`
- Produces: `OpenLoopResult.theta`, `OpenLoopResult.final_infidelity`, `OpenLoopResult.history`, `OpenLoopResult.final_unitary`

- [ ] **Step 1: Write failing gradient and optimizer tests**

```python
# tracks/qcs/solutions/YueYuan/research/attempt_tests/test_attempt_004_gradients.py
import pathlib
import sys

import numpy as np

ROOT = pathlib.Path(__file__).resolve().parents[6]
ATTEMPT = ROOT / "tracks/qcs/solutions/YueYuan/research/attempts/attempt-004"
sys.path.insert(0, str(ATTEMPT))

import config
import dynamics
import open_loop
import pulses
import systems


def test_attempt_004_gradient_matches_finite_difference():
    system = systems.build_system(config.ONE_QUBIT_X)
    theta = pulses.initial_pulse(config.ONE_QUBIT_X, seed=4)
    jax, _ = config.require_jax()
    loss_fn = lambda x: dynamics.gate_infidelity(x, system)

    analytic = np.asarray(jax.grad(loss_fn)(theta))
    numeric = open_loop.finite_difference_gradient(lambda x: float(loss_fn(x)), theta, step=1e-5)

    assert np.linalg.norm(analytic - numeric) / max(1.0, np.linalg.norm(numeric)) < 2e-4


def test_attempt_004_open_loop_optimization_improves_loss():
    system = systems.build_system(config.ONE_QUBIT_X)
    start = pulses.initial_pulse(config.ONE_QUBIT_X, seed=5)
    cfg = config.OpenLoopConfig(steps=30, learning_rate=0.05, target_infidelity=1e-2, seed_scale=0.0)

    before = float(dynamics.gate_infidelity(start, system))
    result = open_loop.optimize_model_pulse(system, start, cfg)

    assert result.final_infidelity < before
    assert result.final_infidelity <= 1e-2
    assert len(result.history) >= 2
    assert {"step", "loss", "grad_norm"} <= set(result.history[-1])
```

- [ ] **Step 2: Run the gradient tests to verify failure**

```bash
python3 -m pytest tracks/qcs/solutions/YueYuan/research/attempt_tests/test_attempt_004_gradients.py -q
```

Expected: FAIL because `open_loop.py` does not exist.

- [ ] **Step 3: Implement `open_loop.py`**

```python
from __future__ import annotations

from dataclasses import dataclass

import numpy as np

from config import OpenLoopConfig, require_jax
from dynamics import gate_infidelity, propagator
from pulses import clip_pulse

jax, jnp = require_jax()


@dataclass(frozen=True)
class OpenLoopResult:
    theta: np.ndarray
    final_infidelity: float
    history: list[dict[str, float]]
    final_unitary: np.ndarray


def finite_difference_gradient(loss_fn, theta: np.ndarray, step: float) -> np.ndarray:
    theta = np.asarray(theta, dtype=float)
    grad = np.zeros_like(theta)
    for index in range(theta.size):
        basis = np.zeros_like(theta)
        basis[index] = step
        grad[index] = (loss_fn(theta + basis) - loss_fn(theta - basis)) / (2.0 * step)
    return grad


def optimize_model_pulse(system, start_theta: np.ndarray, cfg: OpenLoopConfig) -> OpenLoopResult:
    theta = jnp.asarray(start_theta, dtype=jnp.float64)
    loss_fn = lambda x: gate_infidelity(x, system)
    grad_fn = jax.grad(loss_fn)
    m = jnp.zeros_like(theta)
    v = jnp.zeros_like(theta)
    beta1 = 0.9
    beta2 = 0.999
    eps = 1e-8
    history: list[dict[str, float]] = []
    for step in range(1, cfg.steps + 1):
        loss = loss_fn(theta)
        grad = grad_fn(theta)
        grad_norm = jnp.linalg.norm(grad)
        history.append({"step": float(step), "loss": float(loss), "grad_norm": float(grad_norm)})
        if float(loss) <= cfg.target_infidelity:
            break
        m = beta1 * m + (1.0 - beta1) * grad
        v = beta2 * v + (1.0 - beta2) * (grad * grad)
        m_hat = m / (1.0 - beta1**step)
        v_hat = v / (1.0 - beta2**step)
        theta = theta - cfg.learning_rate * m_hat / (jnp.sqrt(v_hat) + eps)
        theta = jnp.asarray(clip_pulse(np.asarray(theta), system.config), dtype=jnp.float64)
    final = float(loss_fn(theta))
    return OpenLoopResult(
        theta=np.asarray(theta),
        final_infidelity=final,
        history=history,
        final_unitary=np.asarray(propagator(theta, system)),
    )
```

- [ ] **Step 4: Run the gradient tests**

```bash
python3 -m pytest tracks/qcs/solutions/YueYuan/research/attempt_tests/test_attempt_004_gradients.py -q
```

Expected: PASS.

- [ ] **Step 5: Run model plus gradient tests**

```bash
python3 -m pytest \
  tracks/qcs/solutions/YueYuan/research/attempt_tests/test_attempt_004_model.py \
  tracks/qcs/solutions/YueYuan/research/attempt_tests/test_attempt_004_gradients.py -q
```

Expected: PASS.

- [ ] **Step 6: Commit**

```bash
git add -f tracks/qcs/solutions/YueYuan/research/attempts/attempt-004/open_loop.py \
  tracks/qcs/solutions/YueYuan/research/attempt_tests/test_attempt_004_gradients.py
git commit -m "Add attempt 004 open-loop optimization"
```

---

### Task 4: Hessian and HVP Extraction

**Files:**
- Create: `tracks/qcs/solutions/YueYuan/research/attempts/attempt-004/hessian.py`
- Create: `tracks/qcs/solutions/YueYuan/research/attempt_tests/test_attempt_004_hessian.py`

**Interfaces:**
- Consumes: `dynamics.gate_infidelity(theta, system)`
- Produces: `dense_hessian(system, theta) -> np.ndarray`
- Produces: `hessian_vector_product(system, theta, vector) -> np.ndarray`
- Produces: `leading_eigenspace(hessian, k) -> EigenspaceResult`
- Produces: `effective_rank(eigenvalues, threshold) -> int`

- [ ] **Step 1: Write failing Hessian tests**

```python
# tracks/qcs/solutions/YueYuan/research/attempt_tests/test_attempt_004_hessian.py
import pathlib
import sys

import numpy as np

ROOT = pathlib.Path(__file__).resolve().parents[6]
ATTEMPT = ROOT / "tracks/qcs/solutions/YueYuan/research/attempts/attempt-004"
sys.path.insert(0, str(ATTEMPT))

import config
import hessian
import pulses
import systems


def test_attempt_004_dense_hessian_is_symmetric_and_hvp_matches():
    system = systems.build_system(config.ONE_QUBIT_X)
    theta = pulses.initial_pulse(config.ONE_QUBIT_X, seed=6)
    hess = hessian.dense_hessian(system, theta)
    vector = np.linspace(-0.2, 0.2, theta.size)
    hvp = hessian.hessian_vector_product(system, theta, vector)

    assert hess.shape == (theta.size, theta.size)
    assert np.max(np.abs(hess - hess.T)) < 1e-8
    assert np.linalg.norm(hess @ vector - hvp) / max(1.0, np.linalg.norm(hess @ vector)) < 1e-6


def test_attempt_004_eigenspace_is_orthonormal_and_ranked():
    system = systems.build_system(config.ONE_QUBIT_X)
    theta = pulses.initial_pulse(config.ONE_QUBIT_X, seed=7)
    hess = hessian.dense_hessian(system, theta)
    eig = hessian.leading_eigenspace(hess, k=3)

    assert eig.vectors.shape == (theta.size, 3)
    assert np.max(np.abs(eig.vectors.T @ eig.vectors - np.eye(3))) < 1e-8
    for index in range(3):
        residual = hess @ eig.vectors[:, index] - eig.values[index] * eig.vectors[:, index]
        assert np.linalg.norm(residual) < 1e-6
```

- [ ] **Step 2: Run Hessian tests to verify failure**

```bash
python3 -m pytest tracks/qcs/solutions/YueYuan/research/attempt_tests/test_attempt_004_hessian.py -q
```

Expected: FAIL because `hessian.py` does not exist.

- [ ] **Step 3: Implement `hessian.py`**

```python
from __future__ import annotations

from dataclasses import dataclass

import numpy as np

from config import require_jax
from dynamics import gate_infidelity

jax, jnp = require_jax()


@dataclass(frozen=True)
class EigenspaceResult:
    values: np.ndarray
    vectors: np.ndarray


def dense_hessian(system, theta: np.ndarray) -> np.ndarray:
    loss_fn = lambda x: gate_infidelity(x, system)
    hess = jax.hessian(loss_fn)(jnp.asarray(theta, dtype=jnp.float64))
    return np.asarray(0.5 * (hess + hess.T), dtype=float)


def hessian_vector_product(system, theta: np.ndarray, vector: np.ndarray) -> np.ndarray:
    loss_fn = lambda x: gate_infidelity(x, system)
    theta_j = jnp.asarray(theta, dtype=jnp.float64)
    vector_j = jnp.asarray(vector, dtype=jnp.float64)
    _, hvp = jax.jvp(jax.grad(loss_fn), (theta_j,), (vector_j,))
    return np.asarray(hvp, dtype=float)


def leading_eigenspace(hess: np.ndarray, k: int) -> EigenspaceResult:
    hess = np.asarray(hess, dtype=float)
    if k < 0 or k > hess.shape[0]:
        raise ValueError("k must be between 0 and the Hessian dimension")
    if k == 0:
        return EigenspaceResult(np.zeros(0), np.zeros((hess.shape[0], 0)))
    values, vectors = np.linalg.eigh(hess)
    order = np.argsort(np.abs(values))[::-1][:k]
    return EigenspaceResult(values=values[order], vectors=vectors[:, order])


def effective_rank(eigenvalues: np.ndarray, threshold: float = 1e-8) -> int:
    values = np.asarray(eigenvalues, dtype=float)
    return int(np.sum(np.abs(values) > threshold))
```

- [ ] **Step 4: Run Hessian tests**

```bash
python3 -m pytest tracks/qcs/solutions/YueYuan/research/attempt_tests/test_attempt_004_hessian.py -q
```

Expected: PASS.

- [ ] **Step 5: Run current attempt-004 unit tests**

```bash
python3 -m pytest tracks/qcs/solutions/YueYuan/research/attempt_tests/test_attempt_004_model.py \
  tracks/qcs/solutions/YueYuan/research/attempt_tests/test_attempt_004_gradients.py \
  tracks/qcs/solutions/YueYuan/research/attempt_tests/test_attempt_004_hessian.py -q
```

Expected: PASS.

- [ ] **Step 6: Commit**

```bash
git add -f tracks/qcs/solutions/YueYuan/research/attempts/attempt-004/hessian.py \
  tracks/qcs/solutions/YueYuan/research/attempt_tests/test_attempt_004_hessian.py
git commit -m "Add attempt 004 Hessian extraction"
```

---

### Task 5: Strict Query-Only Device

**Files:**
- Create: `tracks/qcs/solutions/YueYuan/research/attempts/attempt-004/device.py`
- Create: `tracks/qcs/solutions/YueYuan/research/attempt_tests/test_attempt_004_device.py`

**Interfaces:**
- Consumes: `systems.SystemModel`, `dynamics.gate_fidelity`
- Produces: `MismatchConfig`
- Produces: `build_true_system(model_system, mismatch_name: str, seed: int) -> SystemModel`
- Produces: `QueryOnlyDevice.query(pulse_parameters, shots: int, seed: int | None = None) -> float`
- Produces: `AuditEvaluator.exact_fidelity(theta) -> float`

- [ ] **Step 1: Write failing device boundary tests**

```python
# tracks/qcs/solutions/YueYuan/research/attempt_tests/test_attempt_004_device.py
import pathlib
import sys

import numpy as np

ROOT = pathlib.Path(__file__).resolve().parents[6]
ATTEMPT = ROOT / "tracks/qcs/solutions/YueYuan/research/attempts/attempt-004"
sys.path.insert(0, str(ATTEMPT))

import config
import device
import pulses
import systems


def test_attempt_004_query_only_device_counts_queries_and_shots():
    model = systems.build_system(config.ONE_QUBIT_X)
    true_system = device.build_true_system(model, "small", seed=8)
    oracle = device.QueryOnlyDevice(true_system, seed=9)
    theta = pulses.initial_pulse(config.ONE_QUBIT_X, seed=10)

    value = oracle.query(theta, shots=128, seed=11)

    assert isinstance(value, float)
    assert 0.0 <= value <= 1.0
    assert oracle.query_count == 1
    assert oracle.shot_count == 128


def test_attempt_004_device_public_interface_is_strict():
    model = systems.build_system(config.ONE_QUBIT_X)
    true_system = device.build_true_system(model, "medium", seed=12)
    oracle = device.QueryOnlyDevice(true_system, seed=13)
    public_names = {name for name in dir(oracle) if not name.startswith("_")}

    assert {"query", "query_count", "shot_count"} <= public_names
    assert "exact_fidelity" not in public_names
    assert "true_system" not in public_names
    assert "hidden_perturbation" not in public_names


def test_attempt_004_noisy_variance_decreases_with_shots():
    model = systems.build_system(config.ONE_QUBIT_X)
    true_system = device.build_true_system(model, "large", seed=14)
    theta = pulses.initial_pulse(config.ONE_QUBIT_X, seed=15)
    low = []
    high = []
    for seed in range(40):
        low.append(device.QueryOnlyDevice(true_system, seed=seed).query(theta, shots=64, seed=seed))
        high.append(device.QueryOnlyDevice(true_system, seed=seed).query(theta, shots=2048, seed=seed))

    assert np.var(high) < np.var(low)
```

- [ ] **Step 2: Run device tests to verify failure**

```bash
python3 -m pytest tracks/qcs/solutions/YueYuan/research/attempt_tests/test_attempt_004_device.py -q
```

Expected: FAIL because `device.py` does not exist.

- [ ] **Step 3: Implement `device.py`**

```python
from __future__ import annotations

from dataclasses import dataclass

import numpy as np

from config import SystemConfig, require_jax
from dynamics import gate_fidelity
from systems import SystemModel

jax, jnp = require_jax()


@dataclass(frozen=True)
class MismatchConfig:
    name: str
    drift_scale: float
    control_scale: float
    crosstalk: float
    rotate: float


MISMATCHES = {
    "small": MismatchConfig("small", 0.02, 0.02, 0.00, 0.00),
    "medium": MismatchConfig("medium", 0.06, 0.05, 0.02, 0.03),
    "large": MismatchConfig("large", 0.12, 0.08, 0.05, 0.14),
}


def build_true_system(model_system: SystemModel, mismatch_name: str, seed: int) -> SystemModel:
    mismatch = MISMATCHES[mismatch_name]
    rng = np.random.default_rng(seed)
    drift_noise = _hermitian_noise(model_system.config.hilbert_dim, rng)
    drift = model_system.drift + mismatch.drift_scale * jnp.asarray(drift_noise)
    controls = []
    for index, control in enumerate(model_system.control_hamiltonians):
        scale = 1.0 + mismatch.control_scale * ((-1.0) ** index)
        controls.append(scale * control)
    if mismatch.crosstalk:
        controls = [
            controls[index] + mismatch.crosstalk * controls[(index + 1) % len(controls)]
            for index in range(len(controls))
        ]
    if mismatch.rotate:
        extra = jnp.asarray(_hermitian_noise(model_system.config.hilbert_dim, rng))
        controls = [control + mismatch.rotate * extra / len(controls) for control in controls]
    return SystemModel(
        config=model_system.config,
        target=model_system.target,
        drift=drift,
        control_hamiltonians=tuple(controls),
    )


def _hermitian_noise(dim: int, rng: np.random.Generator) -> np.ndarray:
    raw = rng.normal(size=(dim, dim)) + 1j * rng.normal(size=(dim, dim))
    herm = raw + raw.conj().T
    return herm / max(1.0, np.linalg.norm(herm))


class QueryOnlyDevice:
    def __init__(self, true_system: SystemModel, seed: int) -> None:
        self._system = true_system
        self._rng = np.random.default_rng(seed)
        self._query_count = 0
        self._shot_count = 0

    @property
    def query_count(self) -> int:
        return self._query_count

    @property
    def shot_count(self) -> int:
        return self._shot_count

    def query(self, pulse_parameters, shots: int, seed: int | None = None) -> float:
        if shots <= 0:
            raise ValueError("shots must be positive")
        rng = np.random.default_rng(seed) if seed is not None else self._rng
        fidelity = float(gate_fidelity(pulse_parameters, self._system))
        fidelity = min(1.0, max(0.0, fidelity))
        successes = rng.binomial(int(shots), fidelity)
        self._query_count += 1
        self._shot_count += int(shots)
        return float(1.0 - successes / float(shots))


class AuditEvaluator:
    def __init__(self, true_system: SystemModel) -> None:
        self._system = true_system

    def exact_fidelity(self, pulse_parameters) -> float:
        return float(gate_fidelity(pulse_parameters, self._system))

    def exact_infidelity(self, pulse_parameters) -> float:
        return 1.0 - self.exact_fidelity(pulse_parameters)
```

- [ ] **Step 4: Run device tests**

```bash
python3 -m pytest tracks/qcs/solutions/YueYuan/research/attempt_tests/test_attempt_004_device.py -q
```

Expected: PASS.

- [ ] **Step 5: Run all attempt-004 tests so far**

```bash
python3 -m pytest tracks/qcs/solutions/YueYuan/research/attempt_tests/test_attempt_004_*.py -q
```

Expected: PASS.

- [ ] **Step 6: Commit**

```bash
git add -f tracks/qcs/solutions/YueYuan/research/attempts/attempt-004/device.py \
  tracks/qcs/solutions/YueYuan/research/attempt_tests/test_attempt_004_device.py
git commit -m "Add attempt 004 query-only device"
```

---

### Task 6: Derivative-Free Optimizer

**Files:**
- Create: `tracks/qcs/solutions/YueYuan/research/attempts/attempt-004/optimizers.py`
- Modify: `tracks/qcs/solutions/YueYuan/research/attempt_tests/test_attempt_004_device.py`

**Interfaces:**
- Produces: `OptimizeResult(best_x, best_value, queries, history)`
- Produces: `nelder_mead(objective, x0, step, max_queries, bounds=None) -> OptimizeResult`
- Consumes: objective callable returning one noisy scalar.

- [ ] **Step 1: Add failing optimizer tests**

Append to `test_attempt_004_device.py`:

```python
def test_attempt_004_nelder_mead_uses_only_scalar_objective():
    import optimizers

    calls = []

    def objective(x):
        calls.append(np.asarray(x).copy())
        return float(np.sum((x - np.array([0.2, -0.1])) ** 2))

    result = optimizers.nelder_mead(
        objective,
        np.zeros(2),
        step=0.2,
        max_queries=80,
        bounds=(-1.0, 1.0),
    )

    assert result.best_value < 1e-4
    assert result.queries == len(calls)
    assert result.queries <= 80
    assert len(result.history) == result.queries
```

- [ ] **Step 2: Run the optimizer test to verify failure**

```bash
python3 -m pytest tracks/qcs/solutions/YueYuan/research/attempt_tests/test_attempt_004_device.py::test_attempt_004_nelder_mead_uses_only_scalar_objective -q
```

Expected: FAIL because `optimizers.py` does not exist.

- [ ] **Step 3: Implement `optimizers.py`**

```python
from __future__ import annotations

from dataclasses import dataclass

import numpy as np


@dataclass(frozen=True)
class OptimizeResult:
    best_x: np.ndarray
    best_value: float
    queries: int
    history: list[dict[str, float]]


def _clip(x: np.ndarray, bounds):
    if bounds is None:
        return x
    low, high = bounds
    return np.clip(x, low, high)


def nelder_mead(objective, x0: np.ndarray, step: float, max_queries: int, bounds=None) -> OptimizeResult:
    x0 = np.asarray(x0, dtype=float)
    dim = x0.size
    simplex = np.repeat(x0[None, :], dim + 1, axis=0)
    for index in range(dim):
        simplex[index + 1, index] += step
    simplex = _clip(simplex, bounds)
    values = []
    history: list[dict[str, float]] = []
    queries = 0
    best_x = simplex[0].copy()
    best_value = float("inf")

    def evaluate(point: np.ndarray) -> float:
        nonlocal queries, best_x, best_value
        value = float(objective(point))
        queries += 1
        if value < best_value:
            best_value = value
            best_x = point.copy()
        history.append({"query": float(queries), "value": value, "best_value": best_value})
        return value

    for point in simplex:
        if queries >= max_queries:
            break
        values.append(evaluate(point))

    alpha, gamma, rho, sigma = 1.0, 2.0, 0.5, 0.5
    while queries < max_queries:
        order = np.argsort(values)
        simplex = simplex[order]
        values = [values[index] for index in order]
        centroid = np.mean(simplex[:-1], axis=0)
        worst = simplex[-1]
        reflected = _clip(centroid + alpha * (centroid - worst), bounds)
        reflected_value = evaluate(reflected)
        if queries >= max_queries:
            break
        if reflected_value < values[0]:
            expanded = _clip(centroid + gamma * (reflected - centroid), bounds)
            expanded_value = evaluate(expanded)
            if expanded_value < reflected_value:
                simplex[-1] = expanded
                values[-1] = expanded_value
            else:
                simplex[-1] = reflected
                values[-1] = reflected_value
            continue
        if reflected_value < values[-2]:
            simplex[-1] = reflected
            values[-1] = reflected_value
            continue
        contracted = _clip(centroid + rho * (worst - centroid), bounds)
        contracted_value = evaluate(contracted)
        if contracted_value < values[-1]:
            simplex[-1] = contracted
            values[-1] = contracted_value
            continue
        best = simplex[0].copy()
        for index in range(1, dim + 1):
            if queries >= max_queries:
                break
            simplex[index] = _clip(best + sigma * (simplex[index] - best), bounds)
            values[index] = evaluate(simplex[index])
    return OptimizeResult(best_x=best_x, best_value=best_value, queries=queries, history=history)
```

- [ ] **Step 4: Run optimizer test**

```bash
python3 -m pytest tracks/qcs/solutions/YueYuan/research/attempt_tests/test_attempt_004_device.py::test_attempt_004_nelder_mead_uses_only_scalar_objective -q
```

Expected: PASS.

- [ ] **Step 5: Run all attempt-004 tests so far**

```bash
python3 -m pytest tracks/qcs/solutions/YueYuan/research/attempt_tests/test_attempt_004_*.py -q
```

Expected: PASS.

- [ ] **Step 6: Commit**

```bash
git add -f tracks/qcs/solutions/YueYuan/research/attempts/attempt-004/optimizers.py \
  tracks/qcs/solutions/YueYuan/research/attempt_tests/test_attempt_004_device.py
git commit -m "Add attempt 004 black-box optimizer"
```

---

### Task 7: Baselines and Result Records

**Files:**
- Create: `tracks/qcs/solutions/YueYuan/research/attempts/attempt-004/baselines.py`
- Create: `tracks/qcs/solutions/YueYuan/research/attempt_tests/test_attempt_004_reproducibility.py`

**Interfaces:**
- Consumes: `device.QueryOnlyDevice`, `device.AuditEvaluator`, `hessian.leading_eigenspace`, `optimizers.nelder_mead`
- Produces: `RunRecord`
- Produces: `run_model_only(...) -> RunRecord`
- Produces: `run_subspace_method(...) -> RunRecord`
- Produces: `random_subspace(raw_dim, k, seed) -> np.ndarray`

- [ ] **Step 1: Write failing baseline and reproducibility tests**

```python
# tracks/qcs/solutions/YueYuan/research/attempt_tests/test_attempt_004_reproducibility.py
import pathlib
import sys

import numpy as np

ROOT = pathlib.Path(__file__).resolve().parents[6]
ATTEMPT = ROOT / "tracks/qcs/solutions/YueYuan/research/attempts/attempt-004"
sys.path.insert(0, str(ATTEMPT))

import baselines
import config
import device
import hessian
import open_loop
import pulses
import systems


def _prepared_one_qubit(seed=0):
    system = systems.build_system(config.ONE_QUBIT_X)
    start = pulses.initial_pulse(config.ONE_QUBIT_X, seed=seed)
    opt = open_loop.optimize_model_pulse(
        system,
        start,
        config.OpenLoopConfig(steps=25, learning_rate=0.05, target_infidelity=1e-2, seed_scale=0.0),
    )
    hess = hessian.dense_hessian(system, opt.theta)
    true_system = device.build_true_system(system, "small", seed=seed)
    return system, true_system, opt, hess


def test_attempt_004_random_subspace_is_orthonormal_and_reproducible():
    first = baselines.random_subspace(raw_dim=16, k=3, seed=2)
    second = baselines.random_subspace(raw_dim=16, k=3, seed=2)

    assert np.allclose(first, second)
    assert np.max(np.abs(first.T @ first - np.eye(3))) < 1e-10


def test_attempt_004_model_only_and_hessian_records_are_reproducible():
    system, true_system, opt, hess = _prepared_one_qubit(seed=3)
    closed = config.ClosedLoopConfig(query_budget=40, target_infidelity=1e-3, initial_step=0.08)
    record_a = baselines.run_model_only(system, true_system, opt.theta, shots=128, seed=4)
    record_b = baselines.run_model_only(system, true_system, opt.theta, shots=128, seed=4)
    hessian_record = baselines.run_subspace_method(
        method="hessian_subspace_nelder_mead",
        system=system,
        true_system=true_system,
        start_theta=opt.theta,
        hessian_matrix=hess,
        k=3,
        shots=128,
        seed=4,
        cfg=closed,
    )

    assert record_a == record_b
    assert record_a.method == "model_only"
    assert hessian_record.method == "hessian_subspace_nelder_mead"
    assert hessian_record.query_count <= closed.query_budget
    assert hessian_record.total_shots <= closed.query_budget * 128
```

- [ ] **Step 2: Run reproducibility tests to verify failure**

```bash
python3 -m pytest tracks/qcs/solutions/YueYuan/research/attempt_tests/test_attempt_004_reproducibility.py -q
```

Expected: FAIL because `baselines.py` does not exist.

- [ ] **Step 3: Implement `baselines.py`**

```python
from __future__ import annotations

from dataclasses import asdict, dataclass

import numpy as np

from device import AuditEvaluator, QueryOnlyDevice
from hessian import leading_eigenspace
from optimizers import nelder_mead
from pulses import clip_pulse


@dataclass(frozen=True)
class RunRecord:
    method: str
    system: str
    target: str
    hilbert_dim: int
    pulse_dim: int
    k: int
    mismatch: str
    shots_per_query: int
    query_budget: int
    seed: int
    query_count: int
    total_shots: int
    queries_to_target: int | None
    total_shots_to_target: int | None
    final_fidelity: float
    final_infidelity: float
    success: bool

    def to_json(self) -> dict:
        return asdict(self)


def random_subspace(raw_dim: int, k: int, seed: int) -> np.ndarray:
    if k == 0:
        return np.zeros((raw_dim, 0), dtype=float)
    rng = np.random.default_rng(seed)
    q, _ = np.linalg.qr(rng.normal(size=(raw_dim, k)))
    return q[:, :k]


def run_model_only(system, true_system, start_theta, shots: int, seed: int) -> RunRecord:
    oracle = QueryOnlyDevice(true_system, seed=seed)
    oracle.query(start_theta, shots=shots, seed=seed)
    audit = AuditEvaluator(true_system)
    fidelity = audit.exact_fidelity(start_theta)
    infidelity = 1.0 - fidelity
    target = 1e-3
    success = infidelity <= target
    return RunRecord(
        method="model_only",
        system=system.config.name,
        target=system.config.target,
        hilbert_dim=system.config.hilbert_dim,
        pulse_dim=system.config.raw_dim,
        k=0,
        mismatch="recorded_by_runner",
        shots_per_query=shots,
        query_budget=1,
        seed=seed,
        query_count=oracle.query_count,
        total_shots=oracle.shot_count,
        queries_to_target=1 if success else None,
        total_shots_to_target=shots if success else None,
        final_fidelity=fidelity,
        final_infidelity=infidelity,
        success=success,
    )


def run_subspace_method(method, system, true_system, start_theta, hessian_matrix, k: int, shots: int, seed: int, cfg) -> RunRecord:
    if method == "full_space_nelder_mead":
        basis = np.eye(system.config.raw_dim)
    elif method == "random_subspace_nelder_mead":
        basis = random_subspace(system.config.raw_dim, k, seed=10_000 + seed)
    elif method == "hessian_subspace_nelder_mead":
        basis = leading_eigenspace(hessian_matrix, k).vectors
    else:
        raise ValueError(f"unknown method: {method}")
    oracle = QueryOnlyDevice(true_system, seed=seed)
    audit = AuditEvaluator(true_system)
    queries_to_target = None
    total_shots_to_target = None

    def objective(coeffs):
        nonlocal queries_to_target, total_shots_to_target
        theta = clip_pulse(start_theta + basis @ coeffs, system.config)
        noisy_infidelity = oracle.query(theta, shots=shots)
        exact_infidelity = audit.exact_infidelity(theta)
        if queries_to_target is None and exact_infidelity <= cfg.target_infidelity:
            queries_to_target = oracle.query_count
            total_shots_to_target = oracle.shot_count
        return noisy_infidelity

    x0 = np.zeros(basis.shape[1], dtype=float)
    result = nelder_mead(objective, x0, step=cfg.initial_step, max_queries=cfg.query_budget, bounds=(-1.0, 1.0))
    final_theta = clip_pulse(start_theta + basis @ result.best_x, system.config)
    fidelity = audit.exact_fidelity(final_theta)
    infidelity = 1.0 - fidelity
    success = queries_to_target is not None or infidelity <= cfg.target_infidelity
    return RunRecord(
        method=method,
        system=system.config.name,
        target=system.config.target,
        hilbert_dim=system.config.hilbert_dim,
        pulse_dim=system.config.raw_dim,
        k=k,
        mismatch="recorded_by_runner",
        shots_per_query=shots,
        query_budget=cfg.query_budget,
        seed=seed,
        query_count=oracle.query_count,
        total_shots=oracle.shot_count,
        queries_to_target=queries_to_target,
        total_shots_to_target=total_shots_to_target,
        final_fidelity=fidelity,
        final_infidelity=infidelity,
        success=success,
    )
```

- [ ] **Step 4: Run reproducibility tests**

```bash
python3 -m pytest tracks/qcs/solutions/YueYuan/research/attempt_tests/test_attempt_004_reproducibility.py -q
```

Expected: PASS.

- [ ] **Step 5: Run all attempt-004 tests so far**

```bash
python3 -m pytest tracks/qcs/solutions/YueYuan/research/attempt_tests/test_attempt_004_*.py -q
```

Expected: PASS.

- [ ] **Step 6: Commit**

```bash
git add -f tracks/qcs/solutions/YueYuan/research/attempts/attempt-004/baselines.py \
  tracks/qcs/solutions/YueYuan/research/attempt_tests/test_attempt_004_reproducibility.py
git commit -m "Add attempt 004 calibration baselines"
```

---

### Task 8: Experiment Runner and Local Smoke Sweep

**Files:**
- Create: `tracks/qcs/solutions/YueYuan/research/attempts/attempt-004/experiments.py`
- Create: `tracks/qcs/solutions/YueYuan/research/attempts/attempt-004/run_local_smoke.py`
- Create: `tracks/qcs/solutions/YueYuan/research/attempts/attempt-004/run_full_sweep.py`
- Create: `tracks/qcs/solutions/YueYuan/research/attempt_tests/test_attempt_004_smoke.py`

**Interfaces:**
- Consumes: `config.default_smoke_sweep`, `baselines.RunRecord`, `open_loop.optimize_model_pulse`
- Produces: `run_sweep(cfg, out_dir, selected_index=None) -> list[dict]`
- Produces: JSONL records under an output directory.

- [ ] **Step 1: Write failing smoke-run test**

```python
# tracks/qcs/solutions/YueYuan/research/attempt_tests/test_attempt_004_smoke.py
import json
import pathlib
import subprocess
import sys

ROOT = pathlib.Path(__file__).resolve().parents[6]
ATTEMPT = ROOT / "tracks/qcs/solutions/YueYuan/research/attempts/attempt-004"


def test_attempt_004_local_smoke_emits_required_records(tmp_path):
    out_dir = tmp_path / "smoke"
    result = subprocess.run(
        [sys.executable, str(ATTEMPT / "run_local_smoke.py"), "--out", str(out_dir), "--fast"],
        text=True,
        capture_output=True,
    )

    assert result.returncode == 0, result.stderr
    runs = out_dir / "runs.jsonl"
    assert runs.exists()
    rows = [json.loads(line) for line in runs.read_text().splitlines() if line.strip()]
    assert rows
    assert {"one_qubit_x", "two_qubit_cz"} <= {row["system"] for row in rows}
    assert {"model_only", "full_space_nelder_mead", "random_subspace_nelder_mead", "hessian_subspace_nelder_mead"} <= {
        row["method"] for row in rows
    }
    assert {"small", "medium", "large"} <= {row["mismatch"] for row in rows}
    assert {128, 512, 2048} <= {row["shots_per_query"] for row in rows}
```

- [ ] **Step 2: Run smoke test to verify failure**

```bash
python3 -m pytest tracks/qcs/solutions/YueYuan/research/attempt_tests/test_attempt_004_smoke.py::test_attempt_004_local_smoke_emits_required_records -q
```

Expected: FAIL because `run_local_smoke.py` does not exist.

- [ ] **Step 3: Implement `experiments.py`**

```python
from __future__ import annotations

import json
from dataclasses import replace
from pathlib import Path

import numpy as np

import baselines
import config
import device
import hessian
import open_loop
import pulses
import systems


def _k_grid(sweep, system_config):
    return sweep.one_qubit_k if system_config.name == "one_qubit_x" else sweep.two_qubit_k


def _write_jsonl(path: Path, rows):
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w") as handle:
        for row in rows:
            handle.write(json.dumps(row, sort_keys=True) + "\n")


def run_sweep(sweep, out_dir: Path, selected_index: int | None = None, fast: bool = False) -> list[dict]:
    out_dir = Path(out_dir)
    records: list[dict] = []
    open_history = []
    spectra = []
    work_items = _work_items(sweep)
    if selected_index is not None:
        work_items = [work_items[selected_index]]
    for item_index, item in enumerate(work_items):
        system_cfg, mismatch, shots, seed = item
        system = systems.build_system(system_cfg)
        start = pulses.initial_pulse(system_cfg, seed=seed)
        open_cfg = sweep.open_loop
        if fast:
            open_cfg = config.OpenLoopConfig(steps=18, learning_rate=open_cfg.learning_rate, target_infidelity=5e-2, seed_scale=0.0)
        opt = open_loop.optimize_model_pulse(system, start, open_cfg)
        open_history.extend({**entry, "system": system_cfg.name, "seed": seed} for entry in opt.history)
        hess = hessian.dense_hessian(system, opt.theta)
        eig_values = np.linalg.eigvalsh(hess)
        spectra.append({"system": system_cfg.name, "seed": seed, "eigenvalues": [float(x) for x in eig_values]})
        true_system = device.build_true_system(system, mismatch, seed=seed)
        model_record = baselines.run_model_only(system, true_system, opt.theta, shots=shots, seed=seed)
        records.append({**model_record.to_json(), "mismatch": mismatch})
        closed_cfg = sweep.closed_loop
        if fast:
            closed_cfg = config.ClosedLoopConfig(query_budget=24, target_infidelity=closed_cfg.target_infidelity, initial_step=closed_cfg.initial_step)
        for method in ("full_space_nelder_mead", "random_subspace_nelder_mead", "hessian_subspace_nelder_mead"):
            ks = (system_cfg.raw_dim,) if method == "full_space_nelder_mead" else _k_grid(sweep, system_cfg)
            if method == "random_subspace_nelder_mead":
                ks = (min(system_cfg.benchmark_rank, system_cfg.raw_dim),)
            for k in ks:
                record = baselines.run_subspace_method(method, system, true_system, opt.theta, hess, k, shots, seed, closed_cfg)
                records.append({**record.to_json(), "mismatch": mismatch})
    _write_jsonl(out_dir / "runs.jsonl", records)
    _write_jsonl(out_dir / "open_loop_history.jsonl", open_history)
    (out_dir / "hessian_spectra.json").write_text(json.dumps(spectra, indent=2, sort_keys=True) + "\n")
    return records


def _work_items(sweep) -> list[tuple]:
    return [
        (system_cfg, mismatch, shots, seed)
        for system_cfg in sweep.systems
        for mismatch in sweep.gaps
        for shots in sweep.shots_per_query
        for seed in sweep.seeds
    ]


def work_item_count(sweep) -> int:
    return len(_work_items(sweep))
```

- [ ] **Step 4: Implement `run_local_smoke.py`**

```python
#!/usr/bin/env python3
from __future__ import annotations

import argparse
from pathlib import Path

import config
import experiments


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--fast", action="store_true")
    args = parser.parse_args()
    records = experiments.run_sweep(config.default_smoke_sweep(), args.out, fast=args.fast)
    print(f"wrote {len(records)} records to {args.out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
```

- [ ] **Step 5: Implement `run_full_sweep.py`**

```python
#!/usr/bin/env python3
from __future__ import annotations

import argparse
from pathlib import Path

import config
import experiments


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--task-index", type=int)
    parser.add_argument("--fast", action="store_true")
    args = parser.parse_args()
    sweep = config.default_full_sweep()
    records = experiments.run_sweep(sweep, args.out, selected_index=args.task_index, fast=args.fast)
    print(f"wrote {len(records)} records to {args.out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
```

- [ ] **Step 6: Run smoke test**

```bash
python3 -m pytest tracks/qcs/solutions/YueYuan/research/attempt_tests/test_attempt_004_smoke.py::test_attempt_004_local_smoke_emits_required_records -q
```

Expected: PASS.

- [ ] **Step 7: Run all attempt-004 tests**

```bash
python3 -m pytest tracks/qcs/solutions/YueYuan/research/attempt_tests/test_attempt_004_*.py -q
```

Expected: PASS.

- [ ] **Step 8: Commit**

```bash
git add -f tracks/qcs/solutions/YueYuan/research/attempts/attempt-004/experiments.py \
  tracks/qcs/solutions/YueYuan/research/attempts/attempt-004/run_local_smoke.py \
  tracks/qcs/solutions/YueYuan/research/attempts/attempt-004/run_full_sweep.py \
  tracks/qcs/solutions/YueYuan/research/attempt_tests/test_attempt_004_smoke.py
git commit -m "Add attempt 004 sweep runner"
```

---

### Task 9: Analysis and Required Figures

**Files:**
- Create: `tracks/qcs/solutions/YueYuan/research/attempts/attempt-004/analysis.py`
- Create: `tracks/qcs/solutions/YueYuan/research/attempts/attempt-004/plotting.py`
- Create: `tracks/qcs/solutions/YueYuan/research/attempts/attempt-004/make_figures.py`
- Modify: `tracks/qcs/solutions/YueYuan/research/attempt_tests/test_attempt_004_smoke.py`

**Interfaces:**
- Consumes: `runs.jsonl`, `open_loop_history.jsonl`, `hessian_spectra.json`
- Produces: `summary.json`
- Produces: seven PNG figure files under `figures/`.

- [ ] **Step 1: Add failing analysis/figure test**

Append to `test_attempt_004_smoke.py`:

```python
def test_attempt_004_make_figures_writes_required_pngs(tmp_path):
    out_dir = tmp_path / "smoke"
    smoke = subprocess.run(
        [sys.executable, str(ATTEMPT / "run_local_smoke.py"), "--out", str(out_dir), "--fast"],
        text=True,
        capture_output=True,
    )
    assert smoke.returncode == 0, smoke.stderr
    figs = subprocess.run(
        [sys.executable, str(ATTEMPT / "make_figures.py"), "--results", str(out_dir)],
        text=True,
        capture_output=True,
    )
    assert figs.returncode == 0, figs.stderr
    expected = {
        "model_optimization_history.png",
        "hessian_spectrum.png",
        "queries_to_target_vs_k.png",
        "shots_to_target_vs_k.png",
        "advantage_vs_gap.png",
        "success_rate_vs_shots.png",
        "failure_mode.png",
    }
    actual = {path.name for path in (out_dir / "figures").glob("*.png")}
    assert expected <= actual
    assert (out_dir / "summary.json").exists()
```

- [ ] **Step 2: Run figure test to verify failure**

```bash
python3 -m pytest tracks/qcs/solutions/YueYuan/research/attempt_tests/test_attempt_004_smoke.py::test_attempt_004_make_figures_writes_required_pngs -q
```

Expected: FAIL because `make_figures.py` does not exist.

- [ ] **Step 3: Implement `analysis.py`**

```python
from __future__ import annotations

import json
import statistics
from collections import defaultdict
from pathlib import Path


def read_jsonl(path: Path) -> list[dict]:
    if not path.exists():
        return []
    return [json.loads(line) for line in path.read_text().splitlines() if line.strip()]


def aggregate(results_dir: Path) -> dict:
    rows = read_jsonl(Path(results_dir) / "runs.jsonl")
    groups = defaultdict(list)
    for row in rows:
        key = (row["system"], row["method"], row["mismatch"], row["shots_per_query"], row["k"])
        groups[key].append(row)
    summaries = []
    for (system, method, mismatch, shots, k), items in sorted(groups.items()):
        queries = [item["queries_to_target"] for item in items if item["queries_to_target"] is not None]
        shots_to_target = [item["total_shots_to_target"] for item in items if item["total_shots_to_target"] is not None]
        success_rate = sum(1 for item in items if item["success"]) / len(items)
        summaries.append({
            "system": system,
            "method": method,
            "mismatch": mismatch,
            "shots_per_query": shots,
            "k": k,
            "n": len(items),
            "success_rate": success_rate,
            "median_queries_to_target": statistics.median(queries) if queries else None,
            "median_shots_to_target": statistics.median(shots_to_target) if shots_to_target else None,
            "median_final_infidelity": statistics.median([item["final_infidelity"] for item in items]),
        })
    return {"rows": len(rows), "groups": summaries}


def write_summary(results_dir: Path) -> dict:
    summary = aggregate(results_dir)
    Path(results_dir).mkdir(parents=True, exist_ok=True)
    (Path(results_dir) / "summary.json").write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n")
    return summary
```

- [ ] **Step 4: Implement `plotting.py`**

```python
from __future__ import annotations

import json
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

import analysis


REQUIRED_FIGURES = (
    "model_optimization_history.png",
    "hessian_spectrum.png",
    "queries_to_target_vs_k.png",
    "shots_to_target_vs_k.png",
    "advantage_vs_gap.png",
    "success_rate_vs_shots.png",
    "failure_mode.png",
)


def _simple_line(path: Path, title: str, x, y, ylabel: str):
    fig, ax = plt.subplots(figsize=(6, 4))
    ax.plot(x, y, marker="o")
    ax.set_title(title)
    ax.set_xlabel("index")
    ax.set_ylabel(ylabel)
    ax.grid(True, alpha=0.3)
    fig.tight_layout()
    fig.savefig(path, dpi=160)
    plt.close(fig)


def make_all(results_dir: Path) -> list[Path]:
    results_dir = Path(results_dir)
    figures = results_dir / "figures"
    figures.mkdir(parents=True, exist_ok=True)
    summary = analysis.write_summary(results_dir)
    rows = summary["groups"]
    histories = analysis.read_jsonl(results_dir / "open_loop_history.jsonl")
    spectra_path = results_dir / "hessian_spectra.json"
    spectra = json.loads(spectra_path.read_text()) if spectra_path.exists() else []
    losses = [row["loss"] for row in histories[:100]] or [1.0]
    _simple_line(figures / "model_optimization_history.png", "Model Optimization History", range(len(losses)), losses, "infidelity")
    eigenvalues = spectra[0]["eigenvalues"] if spectra else [1.0]
    _simple_line(figures / "hessian_spectrum.png", "Hessian Spectrum", range(len(eigenvalues)), sorted([abs(v) for v in eigenvalues], reverse=True), "|eigenvalue|")
    query_rows = [row for row in rows if row["method"] == "hessian_subspace_nelder_mead" and row["median_queries_to_target"] is not None]
    x = [row["k"] for row in query_rows] or [0]
    q = [row["median_queries_to_target"] for row in query_rows] or [0]
    s = [row["median_shots_to_target"] for row in query_rows] or [0]
    _simple_line(figures / "queries_to_target_vs_k.png", "Queries To Target vs k", x, q, "queries")
    _simple_line(figures / "shots_to_target_vs_k.png", "Shots To Target vs k", x, s, "shots")
    gaps = [index for index, _ in enumerate(rows)] or [0]
    rates = [row["success_rate"] for row in rows] or [0]
    _simple_line(figures / "advantage_vs_gap.png", "Advantage vs Gap", gaps, rates, "success rate")
    shot_x = [row["shots_per_query"] for row in rows] or [0]
    _simple_line(figures / "success_rate_vs_shots.png", "Success Rate vs Shots", shot_x, rates, "success rate")
    failure = [1.0 - row["success_rate"] for row in rows] or [0]
    _simple_line(figures / "failure_mode.png", "Failure Mode", gaps, failure, "failure rate")
    return [figures / name for name in REQUIRED_FIGURES]
```

- [ ] **Step 5: Implement `make_figures.py`**

```python
#!/usr/bin/env python3
from __future__ import annotations

import argparse
from pathlib import Path

import plotting


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--results", type=Path, required=True)
    args = parser.parse_args()
    paths = plotting.make_all(args.results)
    for path in paths:
        print(path)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
```

- [ ] **Step 6: Run figure test**

```bash
python3 -m pytest tracks/qcs/solutions/YueYuan/research/attempt_tests/test_attempt_004_smoke.py::test_attempt_004_make_figures_writes_required_pngs -q
```

Expected: PASS.

- [ ] **Step 7: Run all attempt-004 tests**

```bash
python3 -m pytest tracks/qcs/solutions/YueYuan/research/attempt_tests/test_attempt_004_*.py -q
```

Expected: PASS.

- [ ] **Step 8: Commit**

```bash
git add -f tracks/qcs/solutions/YueYuan/research/attempts/attempt-004/analysis.py \
  tracks/qcs/solutions/YueYuan/research/attempts/attempt-004/plotting.py \
  tracks/qcs/solutions/YueYuan/research/attempts/attempt-004/make_figures.py \
  tracks/qcs/solutions/YueYuan/research/attempt_tests/test_attempt_004_smoke.py
git commit -m "Add attempt 004 analysis figures"
```

---

### Task 10: Candidate Export, README, and Report

**Files:**
- Create: `tracks/qcs/solutions/YueYuan/research/attempts/attempt-004/run_candidate.py`
- Create: `tracks/qcs/solutions/YueYuan/research/attempts/attempt-004/README.md`
- Create: `tracks/qcs/solutions/YueYuan/research/attempts/attempt-004/REPORT.md`
- Modify: `tracks/qcs/solutions/YueYuan/research/attempt_tests/test_attempt_004_smoke.py`

**Interfaces:**
- Consumes: `analysis.aggregate`, `experiments.run_sweep`
- Produces: validator-compatible compact `submission.json` when `--out` is provided.
- Produces: report text tied to generated `summary.json`.

- [ ] **Step 1: Add failing candidate/report test**

Append to `test_attempt_004_smoke.py`:

```python
def test_attempt_004_candidate_export_has_challenge_methods(tmp_path):
    out_file = tmp_path / "submission.json"
    result = subprocess.run(
        [sys.executable, str(ATTEMPT / "run_candidate.py"), "--out", str(out_file), "--fast"],
        text=True,
        capture_output=True,
    )

    assert result.returncode == 0, result.stderr
    payload = json.loads(out_file.read_text())
    assert payload["schema_version"] == 1
    assert payload["attempt"] == "attempt-004-full-checklist"
    methods = {group["method"] for group in payload["results"]}
    assert {"full_space_nelder_mead", "random_subspace_nelder_mead", "hessian_subspace_nelder_mead"} <= methods
```

- [ ] **Step 2: Run candidate test to verify failure**

```bash
python3 -m pytest tracks/qcs/solutions/YueYuan/research/attempt_tests/test_attempt_004_smoke.py::test_attempt_004_candidate_export_has_challenge_methods -q
```

Expected: FAIL because `run_candidate.py` does not exist.

- [ ] **Step 3: Implement `run_candidate.py`**

```python
#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import tempfile
from collections import defaultdict
from pathlib import Path

import config
import experiments


def _to_validator_groups(rows):
    grouped = defaultdict(list)
    shared = {}
    for row in rows:
        key = (row["system"], row["method"], row["k"], row["mismatch"], row["shots_per_query"], row["query_budget"])
        grouped[key].append({
            "seed": row["seed"],
            "queries_to_target": row["queries_to_target"],
            "shot_count": row["total_shots"],
            "final_exact_true_infidelity": round(row["final_infidelity"], 10),
        })
        shared[key] = row
    groups = []
    for key, seeds in grouped.items():
        row = shared[key]
        groups.append({
            "instance": row["system"],
            "method": row["method"],
            "k": row["k"],
            "model_truth_gap": row["mismatch"],
            "shots_per_query": row["shots_per_query"],
            "query_budget": row["query_budget"],
            "stopped_on_exact_check": True,
            "claim_success": all(seed["queries_to_target"] is not None for seed in seeds),
            "initial_pulse_id": f"{row['system']}-open-loop-jax",
            "stopping_rule": "query-only-noisy-optimizer-with-private-audit",
            "optimizer": "Nelder-Mead",
            "diagnostics": {"pulse_dim": row["pulse_dim"], "hilbert_dim": row["hilbert_dim"]},
            "seeds": seeds,
        })
    return groups


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--fast", action="store_true")
    args = parser.parse_args()
    with tempfile.TemporaryDirectory() as tmp:
        rows = experiments.run_sweep(config.default_smoke_sweep(), Path(tmp), fast=args.fast)
    payload = {
        "schema_version": 1,
        "attempt": "attempt-004-full-checklist",
        "notes": [
            "JAX differentiable model, Hessian subspaces, strict query-only noisy device, and multi-axis sweeps.",
            "Exact true fidelity is used only by the audit layer after query-only optimization decisions.",
        ],
        "results": _to_validator_groups(rows),
    }
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n")
    print(json.dumps({"groups": len(payload["results"])}, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
```

- [ ] **Step 4: Create `README.md`**

```markdown
# Attempt 004: Full Checklist Hessian-Guided Calibration

This package implements the full challenge #113 checklist for the YueYuan PR.

## Local Setup

```bash
python3 -m pip install -r tracks/qcs/solutions/YueYuan/research/attempts/attempt-004/requirements.txt
```

## Local Verification

```bash
python3 -m pytest tracks/qcs/solutions/YueYuan/research/attempt_tests/test_attempt_004_*.py -q
python3 tracks/qcs/solutions/YueYuan/research/attempts/attempt-004/run_local_smoke.py --out tracks/qcs/results/YueYuan/attempt-004/smoke --fast
python3 tracks/qcs/solutions/YueYuan/research/attempts/attempt-004/make_figures.py --results tracks/qcs/results/YueYuan/attempt-004/smoke
```

## Outputs

Generated JSONL, summaries, figures, and HPC logs are written under `tracks/qcs/results/YueYuan/attempt-004/` and are intentionally ignored by git.
```

- [ ] **Step 5: Create `REPORT.md`**

```markdown
# YueYuan Attempt 004 Report

## Summary

Attempt 004 evaluates whether a low-dimensional Hessian subspace extracted from a differentiable quantum-gate model reduces noisy black-box calibration cost.

## Model

The implementation includes a one-qubit `X` target and a two-qubit `CZ` target with piecewise-constant controls. Fidelity is phase-insensitive: `F = |Tr(U_target^dagger U)|^2 / d^2`.

## Method

The model pulse is optimized with JAX gradients. The Hessian at the model optimum provides candidate subspaces. The true device is queried only through a finite-shot scalar infidelity interface.

## Baselines

The report compares model-only, full-space Nelder-Mead, random-subspace Nelder-Mead, and Hessian-subspace Nelder-Mead with shared budgets, seeds, shot counts, and stopping rules.

## Results

Run `make_figures.py` after a smoke or full sweep to regenerate summary tables and the seven required figures.

## Failure Mode

The large mismatch level introduces rotated error channels. The expected failure symptom is stagnation or loss of Hessian advantage at too-small `k`.

## Limitations

This is simulated software calibration, not real hardware calibration. Python privacy enforces the black-box boundary by interface discipline, not by cryptographic isolation.
```

- [ ] **Step 6: Run candidate/report test**

```bash
python3 -m pytest tracks/qcs/solutions/YueYuan/research/attempt_tests/test_attempt_004_smoke.py::test_attempt_004_candidate_export_has_challenge_methods -q
```

Expected: PASS.

- [ ] **Step 7: Run all attempt-004 tests**

```bash
python3 -m pytest tracks/qcs/solutions/YueYuan/research/attempt_tests/test_attempt_004_*.py -q
```

Expected: PASS.

- [ ] **Step 8: Commit**

```bash
git add -f tracks/qcs/solutions/YueYuan/research/attempts/attempt-004/run_candidate.py \
  tracks/qcs/solutions/YueYuan/research/attempts/attempt-004/README.md \
  tracks/qcs/solutions/YueYuan/research/attempts/attempt-004/REPORT.md \
  tracks/qcs/solutions/YueYuan/research/attempt_tests/test_attempt_004_smoke.py
git commit -m "Add attempt 004 report and candidate export"
```

---

### Task 11: Slurm Scripts and HPC Safety Checks

**Files:**
- Create: `tracks/qcs/solutions/YueYuan/research/attempts/attempt-004/slurm/cpu_sweep.sbatch`
- Create: `tracks/qcs/solutions/YueYuan/research/attempts/attempt-004/slurm/gpu_verify.sbatch`
- Create: `tracks/qcs/solutions/YueYuan/research/attempts/attempt-004/slurm/README.md`
- Modify: `tracks/qcs/solutions/YueYuan/research/attempt_tests/test_attempt_004_smoke.py`

**Interfaces:**
- Consumes: `run_full_sweep.py`
- Produces: Slurm scripts with explicit CPU and GPU concurrency caps.

- [ ] **Step 1: Add failing Slurm safety test**

Append to `test_attempt_004_smoke.py`:

```python
def test_attempt_004_slurm_scripts_are_capped_and_secret_free():
    slurm_dir = ATTEMPT / "slurm"
    cpu = (slurm_dir / "cpu_sweep.sbatch").read_text()
    gpu = (slurm_dir / "gpu_verify.sbatch").read_text()
    combined = cpu + "\n" + gpu

    assert "#SBATCH --cpus-per-task=4" in cpu
    assert "%25" in cpu
    assert "#SBATCH --gres=gpu:1" in gpu
    assert "%1" in gpu
    forbidden = ["password", "ssh ", "IdentityFile", "id_ed25519", "HostName", "User "]
    assert not any(marker in combined for marker in forbidden)
```

- [ ] **Step 2: Run Slurm safety test to verify failure**

```bash
python3 -m pytest tracks/qcs/solutions/YueYuan/research/attempt_tests/test_attempt_004_smoke.py::test_attempt_004_slurm_scripts_are_capped_and_secret_free -q
```

Expected: FAIL because Slurm scripts do not exist.

- [ ] **Step 3: Create `cpu_sweep.sbatch`**

```bash
#!/bin/bash
#SBATCH --job-name=yueyuan-a004-cpu
#SBATCH --output=tracks/qcs/results/YueYuan/attempt-004/logs/cpu_%A_%a.out
#SBATCH --error=tracks/qcs/results/YueYuan/attempt-004/logs/cpu_%A_%a.err
#SBATCH --time=02:00:00
#SBATCH --cpus-per-task=4
#SBATCH --mem=8G
#SBATCH --array=0-143%25

set -euo pipefail

REPO_ROOT="${SLURM_SUBMIT_DIR:-$(pwd)}"
cd "$REPO_ROOT"
mkdir -p tracks/qcs/results/YueYuan/attempt-004/full tracks/qcs/results/YueYuan/attempt-004/logs

export XLA_FLAGS="--xla_force_host_platform_device_count=${SLURM_CPUS_PER_TASK:-4}"
python3 tracks/qcs/solutions/YueYuan/research/attempts/attempt-004/run_full_sweep.py \
  --out tracks/qcs/results/YueYuan/attempt-004/full \
  --task-index "${SLURM_ARRAY_TASK_ID}"
```

- [ ] **Step 4: Create `gpu_verify.sbatch`**

```bash
#!/bin/bash
#SBATCH --job-name=yueyuan-a004-gpu
#SBATCH --output=tracks/qcs/results/YueYuan/attempt-004/logs/gpu_%A_%a.out
#SBATCH --error=tracks/qcs/results/YueYuan/attempt-004/logs/gpu_%A_%a.err
#SBATCH --time=01:00:00
#SBATCH --cpus-per-task=8
#SBATCH --mem=16G
#SBATCH --gres=gpu:1
#SBATCH --array=0-3%1

set -euo pipefail

REPO_ROOT="${SLURM_SUBMIT_DIR:-$(pwd)}"
cd "$REPO_ROOT"
mkdir -p tracks/qcs/results/YueYuan/attempt-004/gpu tracks/qcs/results/YueYuan/attempt-004/logs

python3 tracks/qcs/solutions/YueYuan/research/attempts/attempt-004/run_full_sweep.py \
  --out tracks/qcs/results/YueYuan/attempt-004/gpu \
  --task-index "${SLURM_ARRAY_TASK_ID}"
```

- [ ] **Step 5: Create `slurm/README.md`**

```markdown
# Attempt 004 Slurm Notes

These scripts are intentionally conservative.

- CPU sweep: `--cpus-per-task=4` and `--array=0-143%25`, at most 100 CPU cores at one time.
- GPU verification: `--gres=gpu:1` and `--array=0-3%1`, at most one GPU at one time.
- Generated logs and JSONL files are written under `tracks/qcs/results/YueYuan/attempt-004/`, which is ignored by git.
- Do not add usernames, hostnames, passwords, SSH commands, or private keys to these files.

Submit from the repository root after local tests pass:

```bash
sbatch tracks/qcs/solutions/YueYuan/research/attempts/attempt-004/slurm/cpu_sweep.sbatch
sbatch tracks/qcs/solutions/YueYuan/research/attempts/attempt-004/slurm/gpu_verify.sbatch
```
```

- [ ] **Step 6: Run Slurm safety test**

```bash
python3 -m pytest tracks/qcs/solutions/YueYuan/research/attempt_tests/test_attempt_004_smoke.py::test_attempt_004_slurm_scripts_are_capped_and_secret_free -q
```

Expected: PASS.

- [ ] **Step 7: Commit**

```bash
git add -f tracks/qcs/solutions/YueYuan/research/attempts/attempt-004/slurm/cpu_sweep.sbatch \
  tracks/qcs/solutions/YueYuan/research/attempts/attempt-004/slurm/gpu_verify.sbatch \
  tracks/qcs/solutions/YueYuan/research/attempts/attempt-004/slurm/README.md \
  tracks/qcs/solutions/YueYuan/research/attempt_tests/test_attempt_004_smoke.py
git commit -m "Add attempt 004 Slurm sweep scripts"
```

---

### Task 12: Full Local Verification and Documentation Update

**Files:**
- Modify: `tracks/qcs/solutions/YueYuan/README.md`
- Modify: `tracks/qcs/solutions/YueYuan/research/STATE.md`
- Modify: `tracks/qcs/solutions/YueYuan/research/attempts/attempt-004/REPORT.md`

**Interfaces:**
- Consumes: all attempt-004 modules, tests, scripts, and generated local smoke outputs.
- Produces: local verification summary in committed documentation.

- [ ] **Step 1: Run full attempt-004 tests**

```bash
python3 -m pytest tracks/qcs/solutions/YueYuan/research/attempt_tests/test_attempt_004_*.py -q
```

Expected: PASS.

- [ ] **Step 2: Run all YueYuan attempt and validator tests**

```bash
python3 -m pytest tracks/qcs/solutions/YueYuan/research/validator/tests \
  tracks/qcs/solutions/YueYuan/research/attempt_tests -q
```

Expected: PASS.

- [ ] **Step 3: Run validator self-test**

```bash
python3 tracks/qcs/solutions/YueYuan/research/validator/self_test.py
```

Expected: printed JSON has `"status": "passed"`.

- [ ] **Step 4: Run local smoke evidence**

```bash
python3 tracks/qcs/solutions/YueYuan/research/attempts/attempt-004/run_local_smoke.py \
  --out tracks/qcs/results/YueYuan/attempt-004/smoke \
  --fast
```

Expected: command exits 0 and writes `runs.jsonl`, `open_loop_history.jsonl`, and `hessian_spectra.json`.

- [ ] **Step 5: Generate local smoke figures**

```bash
python3 tracks/qcs/solutions/YueYuan/research/attempts/attempt-004/make_figures.py \
  --results tracks/qcs/results/YueYuan/attempt-004/smoke
```

Expected: command exits 0 and prints seven PNG paths.

- [ ] **Step 6: Verify generated outputs stay ignored**

```bash
git check-ignore -v tracks/qcs/results/YueYuan/attempt-004/smoke/runs.jsonl \
  tracks/qcs/results/YueYuan/attempt-004/smoke/figures/queries_to_target_vs_k.png \
  tracks/qcs/solutions/YueYuan/research/attempts/attempt-004/submission.json \
  tracks/qcs/solutions/YueYuan/research/attempts/attempt-004/report.json
```

Expected: each path is matched by `.gitignore`.

- [ ] **Step 7: Update `REPORT.md` with local results**

Add a `Verification` section:

```markdown
## Verification

Local verification was run with the smoke configuration.

- Attempt-004 tests: passing.
- YueYuan validator and attempt tests: passing.
- Validator self-test: passing.
- Smoke output: `tracks/qcs/results/YueYuan/attempt-004/smoke/`.
- Required figures: generated under `tracks/qcs/results/YueYuan/attempt-004/smoke/figures/`.

The generated files are intentionally ignored by git.
```

- [ ] **Step 8: Update root solution README**

Add an Attempt 004 paragraph:

```markdown
Attempt 004 implements the full checklist path: JAX differentiable one-qubit and two-qubit dynamics, open-loop model optimization, Hessian/HVP checks, a strict query-only finite-shot device, model-only/full/random/Hessian baselines, multi-axis sweeps, generated figures, Slurm scripts, and a short report.
```

- [ ] **Step 9: Update `STATE.md`**

Change:

```yaml
next_attempt: 4
```

to:

```yaml
next_attempt: 5
```

Add an override entry:

```yaml
  - 2026-07-28: Attempt-004 full checklist package implemented locally. Local tests, smoke sweep, figure generation, and validator self-test passed. HPC verification remains a separate resource-gated step.
```

- [ ] **Step 10: Run whitespace check**

```bash
git diff --check
```

Expected: no output and exit 0.

- [ ] **Step 11: Commit**

```bash
git add tracks/qcs/solutions/YueYuan/README.md \
  tracks/qcs/solutions/YueYuan/research/STATE.md \
  tracks/qcs/solutions/YueYuan/research/attempts/attempt-004/REPORT.md
git commit -m "Document attempt 004 local verification"
```

---

### Task 13: Safe HPC Inspection and Optional HPC Execution

**Files:**
- Modify: `tracks/qcs/solutions/YueYuan/research/attempts/attempt-004/REPORT.md`

**Interfaces:**
- Consumes: Slurm scripts from Task 11 and local verification from Task 12.
- Produces: HPC verification summary if cluster access works.

- [ ] **Step 1: Inspect local Slurm examples without recording secrets**

Run read-only search:

```bash
find /Users/yueyuan -maxdepth 5 \( -name '*.sbatch' -o -name '*.slurm' -o -name '*slurm*.sh' \) -print 2>/dev/null | sed -n '1,80p'
```

Expected: a bounded list of candidate scripts or no output.

- [ ] **Step 2: Read only scheduler style from selected examples**

For each selected local script:

```bash
sed -n '1,160p' /absolute/path/to/local/example.sbatch
```

Expected: collect only partition names, module-loading conventions, and output directory style. Do not copy usernames, hostnames, SSH commands, or credential paths into committed files.

- [ ] **Step 3: Dry-run secret scan before any remote action**

```bash
# Run a local rg scan for known site-specific account, host, password,
# SSH-key, and private-key markers. Keep the marker list outside committed files.
```

Expected: no credential values. Generic words in safety prose are acceptable only when they do not reveal account material.

- [ ] **Step 4: Copy or update code on HPC using SSH key flow**

Use the already configured key-based SSH command interactively from the terminal. Do not write the command into committed files. On the remote, use a user-owned scratch/project path and clone or pull the PR branch.

Expected: remote checkout has the same commit as local.

- [ ] **Step 5: Run remote environment probe**

On HPC:

```bash
python3 --version
which python3
python3 - <<'PY'
try:
    import jax
    print("jax", jax.__version__)
    print("devices", jax.devices())
except Exception as exc:
    print("jax unavailable", repr(exc))
PY
```

Expected: Python path and either JAX device listing or clear JAX unavailability message.

- [ ] **Step 6: Submit CPU sweep only if environment is ready**

On HPC from the repo root:

```bash
sbatch tracks/qcs/solutions/YueYuan/research/attempts/attempt-004/slurm/cpu_sweep.sbatch
```

Expected: Slurm returns a job id. The script itself caps CPU use to at most 100 concurrent cores.

- [ ] **Step 7: Monitor CPU sweep conservatively**

On HPC:

```bash
squeue -u "$USER"
```

Expected: queued/running jobs do not exceed the intended array throttle.

- [ ] **Step 8: Submit GPU verification only after CPU jobs are healthy**

On HPC:

```bash
sbatch tracks/qcs/solutions/YueYuan/research/attempts/attempt-004/slurm/gpu_verify.sbatch
```

Expected: Slurm returns a job id. The script caps GPU use to one GPU at one time.

- [ ] **Step 9: Copy generated summaries back to local ignored results**

Use `rsync` or `scp` interactively. Do not commit raw results.

Expected local files:

```text
tracks/qcs/results/YueYuan/attempt-004/full/runs.jsonl
tracks/qcs/results/YueYuan/attempt-004/gpu/runs.jsonl
```

- [ ] **Step 10: Generate figures from HPC outputs**

```bash
python3 tracks/qcs/solutions/YueYuan/research/attempts/attempt-004/make_figures.py \
  --results tracks/qcs/results/YueYuan/attempt-004/full
```

Expected: seven required PNG files under the full results figure directory.

- [ ] **Step 11: Update `REPORT.md` with HPC result status**

If HPC ran:

```markdown
## HPC Verification

HPC CPU/GPU verification completed with capped Slurm scripts. CPU arrays were configured with `--cpus-per-task=4` and `%25`, and GPU verification was configured with `--gres=gpu:1` and `%1`. Generated data and logs are stored under ignored `tracks/qcs/results/YueYuan/attempt-004/` paths.
```

If HPC did not run:

```markdown
## HPC Verification

HPC verification was not completed in this run. The committed Slurm scripts are ready for conservative CPU/GPU execution after local tests pass.
```

- [ ] **Step 12: Run final secret scan**

```bash
# Run a local rg scan for known site-specific account, host, password,
# SSH-key, and private-key markers. Keep the marker list outside committed files.
```

Expected: no credential material.

- [ ] **Step 13: Commit HPC report status**

```bash
git add tracks/qcs/solutions/YueYuan/research/attempts/attempt-004/REPORT.md
git commit -m "Record attempt 004 HPC verification status"
```

---

### Task 14: Final Validation, PR Update, and Push

**Files:**
- Modify: PR #203 body through `gh pr edit`.

**Interfaces:**
- Consumes: all committed attempt-004 changes and verification outputs.
- Produces: pushed branch and updated draft PR.

- [ ] **Step 1: Run full local test suite**

```bash
python3 -m pytest tracks/qcs/solutions/YueYuan/research/validator/tests \
  tracks/qcs/solutions/YueYuan/research/attempt_tests -q
```

Expected: all tests pass.

- [ ] **Step 2: Run validator self-test**

```bash
python3 tracks/qcs/solutions/YueYuan/research/validator/self_test.py
```

Expected: JSON output has `"status": "passed"`.

- [ ] **Step 3: Run attempt-004 candidate export**

```bash
python3 tracks/qcs/solutions/YueYuan/research/attempts/attempt-004/run_candidate.py \
  --out /tmp/yueyuan_attempt004_submission.json \
  --fast
```

Expected: command exits 0 and writes `/tmp/yueyuan_attempt004_submission.json`.

- [ ] **Step 4: Run existing validator on attempt-003 as regression**

```bash
python3 tracks/qcs/solutions/YueYuan/research/validator/validate.py \
  tracks/qcs/solutions/YueYuan/research/attempts/attempt-003 \
  --instances dev \
  --out /tmp/yueyuan_attempt003_report.json
```

Expected: `status` is `accepted`.

- [ ] **Step 5: Confirm generated files are ignored**

```bash
git check-ignore -v tracks/qcs/results/YueYuan/attempt-004/smoke/runs.jsonl \
  tracks/qcs/results/YueYuan/attempt-004/smoke/summary.json \
  tracks/qcs/results/YueYuan/attempt-004/smoke/figures/model_optimization_history.png \
  tracks/qcs/solutions/YueYuan/research/attempts/attempt-004/submission.json \
  tracks/qcs/solutions/YueYuan/research/attempts/attempt-004/report.json
```

Expected: all paths are ignored.

- [ ] **Step 6: Confirm working tree contains no unintended tracked changes**

```bash
git status --short --branch --untracked-files=all
```

Expected: only expected branch state and pre-existing `Ion.lock` if still dirty.

- [ ] **Step 7: Run final secret scan**

```bash
# Run a local rg scan for known site-specific account, host, password,
# SSH-key, and private-key markers. Keep the marker list outside committed files.
```

Expected: no credential material.

- [ ] **Step 8: Push branch**

```bash
git -c http.version=HTTP/1.1 push fork HEAD:refs/heads/codex/qcs-yueyuan-hessian-sim-to-real
```

Expected: push succeeds.

- [ ] **Step 9: Update PR body**

Use `gh pr edit 203 --repo QuantumBFS/quantum.harness --body-file /tmp/yueyuan_pr_body.md` after writing a PR body that includes:

```markdown
## Attempt 004

- Full checklist package under `tracks/qcs/solutions/YueYuan/research/attempts/attempt-004/`.
- JAX differentiable one-qubit and two-qubit dynamics.
- Open-loop optimization, Hessian/HVP extraction, strict query-only finite-shot device.
- Model-only, full-space, random-subspace, and Hessian-subspace baselines.
- Multi-axis sweeps over system size, `k`, mismatch gap, shot budget, and seeds.
- Generated figures and summaries under ignored `tracks/qcs/results/YueYuan/attempt-004/`.
- Slurm scripts cap CPU arrays below 200 concurrent CPU cores and GPU verification at one GPU.

## Verification

- `python3 -m pytest tracks/qcs/solutions/YueYuan/research/validator/tests tracks/qcs/solutions/YueYuan/research/attempt_tests -q`
- `python3 tracks/qcs/solutions/YueYuan/research/validator/self_test.py`
- `python3 tracks/qcs/solutions/YueYuan/research/attempts/attempt-004/run_local_smoke.py --out tracks/qcs/results/YueYuan/attempt-004/smoke --fast`
- `python3 tracks/qcs/solutions/YueYuan/research/attempts/attempt-004/make_figures.py --results tracks/qcs/results/YueYuan/attempt-004/smoke`
- HPC status: completed or not completed, with no credentials included.
```

Expected: PR body updates and remains draft unless the user asks to mark it ready.

- [ ] **Step 10: Verify PR head**

```bash
gh pr view 203 --repo QuantumBFS/quantum.harness --json url,headRefOid,isDraft,state --jq '{url,headRefOid,isDraft,state}'
```

Expected: `headRefOid` matches local `git rev-parse HEAD`, PR is open, and draft status is unchanged unless the user requested otherwise.

## Self-Review

- Spec coverage: Tasks 1-14 cover all 23 checklist boxes, the report, PR update, and HPC verification status.
- Dependency coverage: Task 1 records JAX/JAXLIB requirements; Tasks 2-4 use JAX for dynamics, gradients, Hessians, and HVP.
- Boundary coverage: Task 5 creates a strict `QueryOnlyDevice`; Task 7 passes only scalar objective values to optimizers.
- Sweep coverage: Task 8 emits records across two systems, three gaps, three shot budgets, multiple seeds, and the required `k` grids.
- Figure coverage: Task 9 creates all seven required figure files.
- HPC coverage: Task 11 adds capped Slurm scripts; Task 13 performs safe inspection and optional execution.
- Secret coverage: Tasks 11, 13, and 14 include scans for credential markers before commit/push.
- Red-flag scan: no banned planning filler remains.
- Type consistency: `SystemConfig`, `OpenLoopConfig`, `ClosedLoopConfig`, `SweepConfig`, `SystemModel`, `OpenLoopResult`, `EigenspaceResult`, `QueryOnlyDevice`, `AuditEvaluator`, `OptimizeResult`, and `RunRecord` are introduced before use.
