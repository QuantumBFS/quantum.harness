# Challenge 113 Sim-to-Real Quantum-Gate Control Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a reproducible d=2/4 study proving when a model-Hessian subspace reduces query and shot cost for noisy black-box gate calibration, and identify the model-gap regime where it fails.

**Architecture:** A dedicated JAX package uses piecewise-constant controls and matrix-exponential propagation for open-loop optimization and landscape extraction. A strict query-only device boundary feeds the same derivative-free optimizer in full, model-Hessian, random, and oracle coordinate spaces. Content-addressed, atomic artifacts support paired statistical analysis and restartable production sweeps.

**Tech Stack:** Python 3.12, uv, JAX/JAXlib, NumPy, SciPy, CMA-ES (`cma`), Matplotlib, pytest.

## Global Constraints

- All files created by this plan remain under `tracks/qcs/solutions/frustration-free/challenge-113/`.
- Do not modify repository-root lockfiles, shared skills, or another challenge directory.
- Use JAX x64 for all geometry, rank, and scientific-acceptance runs.
- System duration is immutable and hashed: one-qubit defaults to `1.0`;
  two-qubit defaults to `8.0`.
- Use process infidelity `1 - |Tr(U_target† U)|² / d²` without regularization for landscape rank.
- Hard amplitude bounds replace fluence/smoothness penalties in the rank objective.
- Model open-loop acceptance is infidelity at most `1e-8`.
- Black-box target is independently certified fidelity at least `0.999`.
- Numerical rank is reported over relative thresholds `1e-6`, `1e-8`, and `1e-10`; `1e-8` is primary.
- Device optimizers receive no exact truth loss, Hamiltonian, gradient, or Hessian.
- The device boundary is an in-process capability/API boundary, not a security
  sandbox against hostile Python memory or closure introspection.
- Development and production artifacts use distinct run kinds and are never aggregated together.
- Every task follows red-green-refactor, runs focused tests, runs `git diff --check`, and creates one local commit.

---

### Task 1: Dedicated runtime, package skeleton, and validated configuration

**Files:**
- Create: `tracks/qcs/solutions/frustration-free/challenge-113/pyproject.toml`
- Create: `tracks/qcs/solutions/frustration-free/challenge-113/uv.lock`
- Create: `tracks/qcs/solutions/frustration-free/challenge-113/src/qcontrol/__init__.py`
- Create: `tracks/qcs/solutions/frustration-free/challenge-113/src/qcontrol/config.py`
- Create: `tracks/qcs/solutions/frustration-free/challenge-113/tests/test_config.py`
- Create: `tracks/qcs/solutions/frustration-free/challenge-113/tests/test_runtime.py`

**Interfaces:**
- Produces: `SystemConfig(name: str, segments: int, amplitude_bound: float, duration: float | None = None)`.
- Produces: `DeviceConfig(gap: float = 0.0, shots: int | None = None, perturbation_seed: int = 0)`.
- Produces: `SearchConfig(method: str, dimension: int, budget: int)`.
- Produces: `ExperimentConfig(run_kind, system, device, search, trial_seed)`.
- Produces: `ExperimentConfig.canonical_dict() -> dict[str, object]`.
- Produces: `ExperimentConfig.content_id() -> str`.
- Consumes: no earlier implementation task.

- [ ] **Step 1: Write failing configuration tests**

```python
from dataclasses import replace

import pytest

from qcontrol.config import DeviceConfig, ExperimentConfig, SearchConfig, SystemConfig


def valid_config() -> ExperimentConfig:
    return ExperimentConfig(
        run_kind="development",
        system=SystemConfig(name="two_qubit", segments=20, amplitude_bound=4.0),
        device=DeviceConfig(gap=0.05, shots=1000, perturbation_seed=7),
        search=SearchConfig(method="model_hessian", dimension=15, budget=200),
        trial_seed=11,
    )


def test_config_id_is_stable_and_semantic() -> None:
    config = valid_config()
    assert config.content_id() == config.content_id()
    assert replace(config, trial_seed=12).content_id() != config.content_id()


@pytest.mark.parametrize(
    ("field", "value"),
    [("gap", -0.1), ("shots", -1)],
)
def test_device_config_rejects_invalid_values(field: str, value: float) -> None:
    with pytest.raises(ValueError):
        DeviceConfig(**{field: value})


def test_production_cannot_use_development_budget() -> None:
    with pytest.raises(ValueError, match="production budget"):
        replace(valid_config(), run_kind="production").validate()
```

- [ ] **Step 2: Run tests and verify the package is absent**

Run:

```bash
cd tracks/qcs/solutions/frustration-free/challenge-113
uv run --with pytest pytest tests/test_config.py -q
```

Expected: collection fails because `qcontrol.config` does not exist.

- [ ] **Step 3: Create the isolated project and lock**

Create a `pyproject.toml` with:

```toml
[project]
name = "challenge-113-sim-to-real"
version = "0.1.0"
requires-python = ">=3.12,<3.13"
dependencies = [
  "cma",
  "jax",
  "matplotlib",
  "numpy",
  "scipy",
]

[dependency-groups]
dev = ["pytest"]

[tool.pytest.ini_options]
pythonpath = ["src"]
testpaths = ["tests"]
```

Run `uv lock` rather than writing package versions manually. Commit the
resulting exact resolver output.

- [ ] **Step 4: Implement frozen validated dataclasses**

Use frozen dataclasses, reject booleans where integers are required, serialize
floats and enums without environment-dependent values, and compute:

```python
def content_id(self) -> str:
    payload = json.dumps(
        self.canonical_dict(),
        sort_keys=True,
        separators=(",", ":"),
        allow_nan=False,
    ).encode("utf-8")
    return hashlib.sha256(payload).hexdigest()[:20]
```

Validation must enforce:

- systems are `one_qubit` or `two_qubit`;
- segments and budgets are positive integers;
- amplitude bounds are finite and positive;
- explicit durations are finite and positive; `None` resolves canonically to
  `1.0` for one qubit and `8.0` for two qubits;
- gaps are finite and nonnegative;
- shots are either `None` for exact mode or a positive integer;
- search methods are `full`, `model_hessian`, `random`, or `oracle`;
- dimensions are positive and do not exceed the system parameter count;
- development budget is 200 and production budget is 2000.

- [ ] **Step 5: Add runtime smoke tests**

```python
import jax


def test_jax_x64_can_be_enabled() -> None:
    jax.config.update("jax_enable_x64", True)
    assert jax.config.x64_enabled
    assert jax.devices()
```

- [ ] **Step 6: Verify and commit**

Run:

```bash
uv sync --group dev
uv run pytest tests/test_config.py tests/test_runtime.py -q
git diff --check
```

Expected: all tests pass. Commit with `Build isolated Challenge 113 runtime`.

---

### Task 2: Physical systems, target gates, and controllability

**Files:**
- Create: `tracks/qcs/solutions/frustration-free/challenge-113/src/qcontrol/systems.py`
- Create: `tracks/qcs/solutions/frustration-free/challenge-113/tests/test_systems.py`

**Interfaces:**
- Consumes: `SystemConfig`.
- Produces: `ControlSystem(drift, controls, target, amplitude_scales, name, duration)`.
- Produces: `make_system(config: SystemConfig) -> ControlSystem`.
- Produces: `lie_algebra_dimension(system: ControlSystem, tolerance=1e-10) -> int`.
- Produces: `perturb_system(system, gap, seed) -> ControlSystem`.

- [ ] **Step 1: Write exact system tests**

```python
import numpy as np

from qcontrol.config import SystemConfig
from qcontrol.systems import lie_algebra_dimension, make_system, perturb_system


def test_one_qubit_system_is_su2_controllable() -> None:
    system = make_system(SystemConfig("one_qubit", 12, 4.0))
    assert system.dimension == 2
    assert system.duration == 1.0
    assert len(system.controls) == 2
    assert lie_algebra_dimension(system) == 3


def test_two_qubit_system_is_su4_controllable() -> None:
    system = make_system(SystemConfig("two_qubit", 20, 4.0))
    assert system.dimension == 4
    assert system.duration == 8.0
    assert len(system.controls) == 4
    assert lie_algebra_dimension(system) == 15


def test_gap_zero_preserves_model_and_nonzero_gap_is_reproducible() -> None:
    model = make_system(SystemConfig("two_qubit", 20, 4.0))
    zero_gap = perturb_system(model, 0.0, 3)
    np.testing.assert_allclose(zero_gap.drift, model.drift)
    for actual, expected in zip(zero_gap.controls, model.controls, strict=True):
        np.testing.assert_allclose(actual, expected)
    truth_a = perturb_system(model, 0.05, 3)
    truth_b = perturb_system(model, 0.05, 3)
    np.testing.assert_allclose(truth_a.drift, truth_b.drift)
    assert not np.allclose(truth_a.drift, model.drift)
```

- [ ] **Step 2: Verify red**

Run `uv run pytest tests/test_systems.py -q`.

Expected: import failure for `qcontrol.systems`.

- [ ] **Step 3: Implement normalized Pauli systems**

Use normalized Hermitian Pauli products. The one-qubit drift contains `0.37 Z`
and controls `X`, `Y`. The two-qubit drift is:

```python
0.31 * kron(Z, I) + 0.47 * kron(I, Z) + 0.23 * kron(Z, Z)
```

and controls are `XI`, `YI`, `IX`, `IY`. Use Hadamard as the one-qubit target
and CNOT as the two-qubit target. Verify all matrices are Hermitian and targets
unitary during construction.

- [ ] **Step 4: Implement deterministic Lie closure**

Represent skew-Hermitian generators as real vectors formed by concatenating
real and imaginary matrix parts. Repeatedly add commutators whose residual
after projection onto the current orthonormal basis exceeds the tolerance.
Remove the trace before rank tests. Stop at `d**2 - 1` or when no generator is
added.

- [ ] **Step 5: Implement hidden-truth perturbations**

Generate a seeded traceless Hermitian drift direction with unit Frobenius norm,
seeded independent control gain changes, and a seeded unmodeled traceless term.
Scale the aggregate perturbation so:

```python
np.linalg.norm(truth.drift - model.drift, "fro") / np.linalg.norm(model.drift, "fro")
```

equals `gap` within `1e-12`. Store perturbation descriptors only in the private
truth object used by experiment construction.

- [ ] **Step 6: Verify and commit**

Run:

```bash
uv run pytest tests/test_systems.py -q
git diff --check
```

Expected: all tests pass. Commit with `Add controllable gate-control systems`.

---

### Task 3: Pulse coordinates, unitary propagation, and fidelity objective

**Files:**
- Create: `tracks/qcs/solutions/frustration-free/challenge-113/src/qcontrol/pulses.py`
- Create: `tracks/qcs/solutions/frustration-free/challenge-113/src/qcontrol/propagation.py`
- Create: `tracks/qcs/solutions/frustration-free/challenge-113/src/qcontrol/objectives.py`
- Create: `tracks/qcs/solutions/frustration-free/challenge-113/tests/test_dynamics.py`

**Interfaces:**
- Consumes: `ControlSystem`.
- Produces: `PulseSpace(control_count, segments, amplitude_scales, bound)`.
- Produces: `PulseSpace.to_physical(normalized) -> jax.Array`.
- Produces: `PulseSpace.to_normalized(physical) -> jax.Array`.
- Produces: `propagate(system, physical_pulse, duration=None) -> jax.Array`;
  `None` uses the immutable system duration.
- Produces: `process_infidelity_from_unitary(unitary, target) -> jax.Array`.
- Produces: `normalized_infidelity(normalized, system, space) -> jax.Array`.

- [ ] **Step 1: Write dynamics tests**

```python
import jax
import jax.numpy as jnp
import numpy as np

from qcontrol.config import SystemConfig
from qcontrol.objectives import normalized_infidelity, process_infidelity_from_unitary
from qcontrol.propagation import propagate
from qcontrol.pulses import PulseSpace
from qcontrol.systems import make_system


jax.config.update("jax_enable_x64", True)


def test_normalized_coordinates_round_trip() -> None:
    space = PulseSpace.from_system(make_system(SystemConfig("two_qubit", 20, 4.0)), 20)
    pulse = jnp.linspace(-0.8, 0.8, space.parameter_count)
    np.testing.assert_allclose(space.to_normalized(space.to_physical(pulse)), pulse)


def test_propagator_is_unitary() -> None:
    system = make_system(SystemConfig("two_qubit", 20, 4.0))
    pulse = jnp.zeros((4, 20))
    unitary = propagate(system, pulse)
    np.testing.assert_allclose(unitary.conj().T @ unitary, jnp.eye(4), atol=1e-12)


def test_infidelity_is_global_phase_invariant() -> None:
    system = make_system(SystemConfig("one_qubit", 12, 4.0))
    pulse = jnp.zeros((2, 12))
    unitary = propagate(system, pulse)
    assert np.isclose(
        process_infidelity_from_unitary(unitary, system.target),
        process_infidelity_from_unitary(jnp.exp(0.3j) * unitary, system.target),
    )


def test_gradient_matches_central_difference() -> None:
    system = make_system(SystemConfig("one_qubit", 12, 4.0))
    space = PulseSpace.from_system(system, 12)
    x = jnp.linspace(-0.1, 0.1, space.parameter_count)
    value, gradient = jax.value_and_grad(normalized_infidelity)(x, system, space)
    direction = jnp.arange(space.parameter_count, dtype=jnp.float64)
    direction /= jnp.linalg.norm(direction)
    step = 1e-5
    finite = (
        normalized_infidelity(x + step * direction, system, space)
        - normalized_infidelity(x - step * direction, system, space)
    ) / (2 * step)
    np.testing.assert_allclose(jnp.vdot(gradient, direction), finite, rtol=1e-6, atol=1e-8)
```

- [ ] **Step 2: Verify red**

Run `uv run pytest tests/test_dynamics.py -q`.

- [ ] **Step 3: Implement normalized pulse mapping**

Store normalized coordinates as a flat vector ordered by control then segment.
Map to a `(control_count, segments)` physical array. Reject wrong shapes,
nonfinite values, and normalized amplitudes outside `[-1, 1]`.

- [ ] **Step 4: Implement segment-exponential propagation**

Use `jax.lax.scan` over segment Hamiltonians and
`jax.scipy.linalg.expm(-1j * dt * hamiltonian)`. JIT a stable-shape kernel.
Do not project the result back to a unitary matrix; projection would hide
numerical errors. The total duration defaults to `system.duration`; an explicit
override is permitted only for resolution and reachability diagnostics.

- [ ] **Step 5: Implement the smooth phase-insensitive objective**

```python
overlap = jnp.trace(target.conj().T @ unitary)
fidelity = jnp.real(overlap.conj() * overlap) / (dimension**2)
return jnp.clip(1.0 - fidelity, 0.0, 1.0)
```

Keep the unclipped internal loss available for derivatives near the optimum;
clipping is only for reported observations.

- [ ] **Step 6: Verify and commit**

Run:

```bash
uv run pytest tests/test_dynamics.py -q
git diff --check
```

Expected: all tests pass. Commit with `Add differentiable unitary propagation`.

---

### Task 4: Deterministic open-loop optimization

**Files:**
- Create: `tracks/qcs/solutions/frustration-free/challenge-113/src/qcontrol/open_loop.py`
- Create: `tracks/qcs/solutions/frustration-free/challenge-113/tests/test_open_loop.py`

**Interfaces:**
- Consumes: `ControlSystem`, `PulseSpace`.
- Produces: `OpenLoopResult(normalized_pulse, loss, gradient_norm, starts, evaluations)`.
- Produces: `optimize_open_loop(system, space, seed, starts=5) -> OpenLoopResult`.

The accepted two-qubit system uses total duration `8.0`. This is not a tuning
convenience: with normalized Pauli products, the configured `0.23 ZZ` term has
effective nonlocal strength `0.115`, giving the ideal-local CNOT lower bound
`pi / (4 * 0.115) = 6.82955`. Controlled diagnostics found losses `0.4422`,
`0.3273`, `0.1814`, `0.1472`, `0.00868`, and `1.03e-13` at durations
`1`, `2`, `3.5`, `4`, `7`, and `8`, respectively.

- [ ] **Step 1: Write open-loop acceptance tests**

```python
from qcontrol.config import SystemConfig
from qcontrol.open_loop import optimize_open_loop
from qcontrol.pulses import PulseSpace
from qcontrol.systems import make_system


def test_one_qubit_open_loop_reaches_acceptance() -> None:
    system = make_system(SystemConfig("one_qubit", 12, 4.0))
    space = PulseSpace.from_system(system, 12)
    result = optimize_open_loop(system, space, seed=5, starts=5)
    assert result.loss <= 1e-8
    assert result.gradient_norm <= 1e-5
    assert result.evaluations > 0


def test_open_loop_is_reproducible() -> None:
    system = make_system(SystemConfig("one_qubit", 12, 4.0))
    space = PulseSpace.from_system(system, 12)
    assert optimize_open_loop(system, space, 5) == optimize_open_loop(system, space, 5)
```

- [ ] **Step 2: Verify red**

Run `uv run pytest tests/test_open_loop.py -q`.

- [ ] **Step 3: Implement JAX-to-SciPy value-and-gradient bridge**

Compile one `jax.value_and_grad` function. Convert values to Python floats and
gradients to contiguous NumPy float64 arrays. Use SciPy `L-BFGS-B` with
`(-1, 1)` bounds in normalized coordinates.

- [ ] **Step 4: Implement deterministic multistart**

Use a seeded NumPy generator to create one zero start and four bounded random
starts. Select by `(loss, gradient_norm, start_index)`. Raise
`OpenLoopAcceptanceError` with all start diagnostics if no start reaches
`1e-8`; never silently publish a poor optimum.

- [ ] **Step 5: Add the two-qubit development acceptance**

Add a marked integration test with five starts and assert loss at most `1e-8`.
Record its measured wall time with `pytest --durations=5`; do not weaken the
scientific threshold to make the test faster.

- [ ] **Step 6: Verify and commit**

Run:

```bash
uv run pytest tests/test_open_loop.py -q
git diff --check
```

Expected: all tests pass. Commit with `Add deterministic open-loop gate optimization`.

---

### Task 5: Hessian geometry and endpoint-map validation

**Files:**
- Create: `tracks/qcs/solutions/frustration-free/challenge-113/src/qcontrol/landscape.py`
- Create: `tracks/qcs/solutions/frustration-free/challenge-113/tests/test_landscape.py`

**Interfaces:**
- Consumes: accepted `OpenLoopResult`.
- Produces: `hessian_vector_product(loss_fn, point, vector) -> jax.Array`.
- Produces: `endpoint_jacobian(system, space, point) -> np.ndarray`.
- Produces: `analyze_landscape(...) -> LandscapeResult`.
- `LandscapeResult` contains dense/leading eigenpairs, Jacobian singular values,
  ranks at all three thresholds, and orthonormal subspace bases.

- [ ] **Step 1: Write dense/HVP and rank tests**

```python
import jax
import numpy as np

from qcontrol.landscape import analyze_landscape, dense_hessian, hessian_vector_product


def test_hvp_matches_dense_hessian(accepted_one_qubit_fixture) -> None:
    loss_fn, point = accepted_one_qubit_fixture
    dense = dense_hessian(loss_fn, point)
    vector = np.linspace(-1.0, 1.0, point.size)
    np.testing.assert_allclose(
        hessian_vector_product(loss_fn, point, vector),
        dense @ vector,
        rtol=1e-7,
        atol=1e-9,
    )


def test_one_qubit_geometry_has_rank_three(accepted_one_qubit_fixture) -> None:
    result = analyze_landscape(*accepted_one_qubit_fixture, leading_count=6)
    assert result.hessian_ranks[1e-8] == 3
    assert result.jacobian_ranks[1e-8] == 3
    np.testing.assert_allclose(result.model_basis.T @ result.model_basis, np.eye(6), atol=1e-10)
```

- [ ] **Step 2: Verify red**

Run `uv run pytest tests/test_landscape.py -q`.

- [ ] **Step 3: Implement a single linearization convention**

Map endpoint variations to coefficients in an orthonormal generalized-Pauli
basis of traceless Hermitian matrices. Hold `reference = U(point)` fixed,
define `relative = reference.conj().T @ U(x)`, and use the local Hermitian
tangent:

```python
delta_a = (relative - relative.conj().T) / (2j)
coefficient_j = real(trace(generator_j.conj().T @ traceless(delta_a)))
```

Differentiate this local endpoint-coordinate function at the accepted optimum
with JAX. This construction is branch-free and is used only for the endpoint
Jacobian at `relative = I`.

- [ ] **Step 4: Implement dense Hessian and matrix-free HVP**

Use `jax.hessian` only for validation dimensions. Implement:

```python
_, hvp = jax.jvp(jax.grad(loss_fn), (point,), (vector,))
```

Wrap the compiled HVP in SciPy `LinearOperator` and use `eigsh(..., which="LA")`
for leading algebraic eigenpairs.

- [ ] **Step 5: Implement stable eigenspace comparisons**

Sort descending, symmetrize dense Hessians, orthonormalize selected columns,
and compare degenerate spaces with projection residuals and principal angles.
Never compare eigenvector signs.

- [ ] **Step 6: Add d=4 acceptance and resolution checks**

Assert the accepted d=4 fixture has Hessian and endpoint-Jacobian rank 15 at
the primary threshold, and that leading dense and HVP projectors differ by at
most `1e-7` in operator norm. Repeat propagation with twice as many segments
representing the same held pulse and require the rank conclusion to remain
unchanged.

- [ ] **Step 7: Verify and commit**

Run:

```bash
uv run pytest tests/test_landscape.py -q
git diff --check
```

Expected: all tests pass. Commit with `Validate Hessian control geometry`.

---

### Task 6: Opaque noisy device and immutable accounting ledger

**Files:**
- Create: `tracks/qcs/solutions/frustration-free/challenge-113/src/qcontrol/device.py`
- Create: `tracks/qcs/solutions/frustration-free/challenge-113/tests/test_device.py`

**Interfaces:**
- Consumes: a private truth `ControlSystem`, `PulseSpace`, `DeviceConfig`.
- Produces: public `QueryDevice.query(normalized_pulse) -> Observation`.
- Produces: `QueryDevice.validate(normalized_pulse, shots=100_000) -> Observation`.
- Produces: append-only `QueryLedger`.
- `Observation` contains estimate, shots, optimizer_query_index, validation flag,
  and deterministic observation seed; it does not contain exact fidelity.

- [ ] **Step 1: Write boundary and accounting tests**

```python
import pytest


def test_fixed_seed_observations_are_reproducible(device_factory, pulse) -> None:
    first = device_factory(seed=4).query(pulse)
    second = device_factory(seed=4).query(pulse)
    assert first == second


def test_query_and_validation_accounting(device_factory, pulse) -> None:
    device = device_factory(seed=4, shots=1000)
    device.query(pulse)
    device.query(pulse)
    device.validate(pulse, shots=100_000)
    assert device.ledger.optimizer_queries == 2
    assert device.ledger.optimizer_shots == 2000
    assert device.ledger.validation_shots == 100_000


def test_public_device_has_no_truth_api(device_factory) -> None:
    device = device_factory(seed=4)
    assert not hasattr(device, "exact_fidelity")
    assert not hasattr(device, "hamiltonian")
    with pytest.raises(AttributeError):
        _ = device.truth
```

- [ ] **Step 2: Verify red**

Run `uv run pytest tests/test_device.py -q`.

- [ ] **Step 3: Implement exact and finite-shot observations**

Exact black-box mode returns the clipped scalar process fidelity as the
observation and records zero shots; it exposes no separately named truth field
or truth object.
Finite-shot mode draws:

```python
successes = rng.binomial(shots, exact_process_fidelity)
estimate = successes / shots
```

Derive each observation seed from the immutable device seed, query index, and
validation flag so resume and replay are deterministic.

Every invocation reserves and records a monotonic attempt index before
evaluation. Failed propagation, validation, or sampling attempts remain in the
internal ledger with explicit failure status and cannot reuse an index. Public
observations and snapshots are detached copies; mutating one cannot alter
internal accounting. QueryDevice and ledger serialization are disabled.

- [ ] **Step 4: Implement statistical certification**

Use a one-sided Wilson 95% lower confidence bound. `Observation.certifies(0.999)`
returns true only for validation observations whose lower bound is at least
`0.999`. Optimizer observations never certify completion.

- [ ] **Step 5: Enforce the optimizer boundary**

Create the truth evaluator in a closure and expose only the `QueryDevice`
protocol to closed-loop code. Offline analysis receives a separate evaluator
constructed from the same private experiment factory; the optimizer module
must not import it.

- [ ] **Step 6: Verify and commit**

Run:

```bash
uv run pytest tests/test_device.py -q
git diff --check
```

Expected: all tests pass. Commit with `Add query-only calibration device`.

---

### Task 7: Fair full, informed, random, and oracle closed-loop searches

**Files:**
- Create: `tracks/qcs/solutions/frustration-free/challenge-113/src/qcontrol/closed_loop.py`
- Create: `tracks/qcs/solutions/frustration-free/challenge-113/tests/test_closed_loop.py`

**Interfaces:**
- Consumes: model optimum, coordinate basis, `QueryDevice`, `SearchConfig`.
- Produces: `SearchSpace(origin, basis, lower_bounds, upper_bounds)`.
- Produces: `run_closed_loop(device, space, budget, seed) -> ClosedLoopResult`.
- `ClosedLoopResult` contains best pulse, observation history, budget status,
  provisional crossings, and validation result.

- [ ] **Step 1: Write search-space fairness tests**

```python
import numpy as np

from qcontrol.closed_loop import SearchSpace, run_closed_loop


def test_subspace_coordinates_map_to_identical_origin(model_optimum, model_basis) -> None:
    space = SearchSpace(model_optimum, model_basis[:, :15], bound=1.0)
    np.testing.assert_allclose(space.to_pulse(np.zeros(15)), model_optimum)


def test_budget_is_never_exceeded(device_factory, search_fixture) -> None:
    device = device_factory(shots=1000)
    result = run_closed_loop(device, *search_fixture, budget=37, seed=2)
    assert device.ledger.optimizer_queries <= 37
    assert result.evaluations == device.ledger.optimizer_queries


def test_seeded_random_basis_is_orthonormal_and_reproducible(random_space_factory) -> None:
    first = random_space_factory(dimension=15, seed=9)
    second = random_space_factory(dimension=15, seed=9)
    np.testing.assert_allclose(first.basis, second.basis)
    np.testing.assert_allclose(first.basis.T @ first.basis, np.eye(15), atol=1e-12)
```

- [ ] **Step 2: Verify red**

Run `uv run pytest tests/test_closed_loop.py -q`.

- [ ] **Step 3: Implement common candidate spaces**

Use the identity basis for full search, leading model eigenvectors for informed
search, QR-orthonormalized seeded Gaussian columns for random search, and
leading private truth eigenvectors only in the oracle experiment factory.
Clip or reject any mapped pulse outside normalized amplitude bounds consistently
for every method.

- [ ] **Step 4: Implement production CMA-ES**

Initialize all methods at zero coordinate displacement. Use the same initial
coordinate-space scale after whitening, population policy, bounds, and stopping
rules. Evaluate candidates sequentially through `QueryDevice.query` so every
call is ledgered. Stop at budget, not at an unvalidated noisy crossing.

- [ ] **Step 5: Implement independent target validation**

Whenever the current best optimizer estimate is at least 0.999, issue one
independent 100,000-shot validation. If it certifies the threshold, stop and
record the first optimizer query index. If it fails, continue without altering
optimizer history.

- [ ] **Step 6: Add deterministic scientific fixtures**

Use a constructed small-gap d=2 fixture to verify:

- top-3 reaches target within the fixture budget;
- paired random-3 does not outperform top-3;
- oracle-3 reaches at least as low an exact restricted floor;
- zero-gap starts at target and needs only a validation observation.

- [ ] **Step 7: Verify and commit**

Run:

```bash
uv run pytest tests/test_closed_loop.py -q
git diff --check
```

Expected: all tests pass. Commit with `Compare query-only calibration spaces`.

---

### Task 8: Atomic artifacts and restartable experiment orchestration

**Files:**
- Create: `tracks/qcs/solutions/frustration-free/challenge-113/src/qcontrol/artifacts.py`
- Create: `tracks/qcs/solutions/frustration-free/challenge-113/src/qcontrol/experiments.py`
- Create: `tracks/qcs/solutions/frustration-free/challenge-113/run.py`
- Create: `tracks/qcs/solutions/frustration-free/challenge-113/tests/test_artifacts.py`
- Create: `tracks/qcs/solutions/frustration-free/challenge-113/tests/test_experiments.py`

**Interfaces:**
- Consumes: all previous scientific components.
- Produces: `ArtifactStore.create_or_resume(config)`.
- Produces: `run_trial(config, store) -> TrialResult`.
- Produces CLI commands `geometry`, `trial`, `sweep`, `validate`, and `status`.

- [ ] **Step 1: Write crash and provenance tests**

```python
from dataclasses import replace
import json

import pytest

from qcontrol.artifacts import ArtifactConflict, ArtifactStore


def test_failed_publish_preserves_previous_artifact(tmp_path, monkeypatch) -> None:
    store = ArtifactStore(tmp_path)
    store.publish_json("summary.json", {"version": 1})
    monkeypatch.setattr(store, "_replace", lambda *_: (_ for _ in ()).throw(OSError("boom")))
    with pytest.raises(OSError):
        store.publish_json("summary.json", {"version": 2})
    assert json.loads((tmp_path / "summary.json").read_text()) == {"version": 1}


def test_resume_rejects_changed_config(tmp_path, config) -> None:
    ArtifactStore.create(tmp_path, config)
    with pytest.raises(ArtifactConflict):
        ArtifactStore.resume(tmp_path, replace(config, trial_seed=config.trial_seed + 1))
```

- [ ] **Step 2: Verify red**

Run `uv run pytest tests/test_artifacts.py tests/test_experiments.py -q`.

- [ ] **Step 3: Implement canonical atomic publication**

Write canonical UTF-8 JSON with `allow_nan=False`, fsync the temporary file,
atomically replace, and fsync the parent directory. A failed overwrite restores
the prior valid artifact. Immutable trial IDs cannot be overwritten with
different bytes.

- [ ] **Step 4: Implement provenance**

Bind:

- Git revision and dirty state;
- SHA256 of `uv.lock`;
- hashes of all `src/qcontrol/*.py` files;
- Python, JAX, JAXlib, NumPy, and SciPy versions;
- JAX device platform and x64 state;
- canonical experiment configuration.

Resume recomputes and verifies every field.

- [ ] **Step 5: Implement paired trial generation**

Generate trial IDs from system, gap, perturbation orientation, shot regime,
search dimension, method, and seed. Reuse the same private device instance
identity across paired methods but provide independent observation streams.
Generate full-space trials once per device/shot/seed, not once for every `k`.

- [ ] **Step 6: Implement strict CLI modes**

Examples:

```bash
uv run python run.py geometry --system one_qubit --output results/dev-geometry
uv run python run.py sweep --kind development --output results/dev-sweep
uv run python run.py validate --output results/dev-sweep
uv run python run.py status --output results/dev-sweep
```

`validate` checks schemas, hashes, expected trial coverage, ledger totals, and
absence of unexpected files. It exits nonzero for partial production sweeps but
`status` reports partial progress successfully.

- [ ] **Step 7: Test interruption and resume**

Interrupt a five-trial fixture after two completed trials. Resume and assert
that exactly three trials execute, prior trial hashes do not change, and no
query ledger is duplicated.

- [ ] **Step 8: Verify and commit**

Run:

```bash
uv run pytest tests/test_artifacts.py tests/test_experiments.py -q
git diff --check
```

Expected: all tests pass. Commit with `Make Challenge 113 sweeps restartable`.

---

### Task 9: Statistical analysis and required figures

**Files:**
- Create: `tracks/qcs/solutions/frustration-free/challenge-113/src/qcontrol/analysis.py`
- Create: `tracks/qcs/solutions/frustration-free/challenge-113/src/qcontrol/figures.py`
- Create: `tracks/qcs/solutions/frustration-free/challenge-113/tests/test_analysis.py`
- Create: `tracks/qcs/solutions/frustration-free/challenge-113/tests/test_figures.py`

**Interfaces:**
- Consumes: verified trial and landscape artifacts.
- Produces: `aggregate_run(store) -> Summary`.
- Produces paired bootstrap confidence intervals and success probabilities.
- Produces the five required publication figures.

- [ ] **Step 1: Write statistical tests from hand-computable fixtures**

```python
from qcontrol.analysis import first_certified_query, success_probability


def test_first_certified_query_ignores_unvalidated_crossing() -> None:
    history = fixture_history(provisional_query=4, certified_query=9)
    assert first_certified_query(history) == 9


def test_budget_exhaustion_counts_as_failure() -> None:
    trials = [successful_trial(7), exhausted_trial(), successful_trial(12)]
    estimate = success_probability(trials)
    assert estimate.value == 2 / 3
    assert estimate.denominator == 3
```

- [ ] **Step 2: Verify red**

Run `uv run pytest tests/test_analysis.py tests/test_figures.py -q`.

- [ ] **Step 3: Implement paired summaries**

Compute:

- first certified query with failures right-censored at the budget for plots
  and separately reported as failures;
- total optimizer plus validation shots;
- success probability within budget;
- median best exact infidelity trajectories;
- paired differences between model-Hessian and each baseline;
- deterministic seeded bootstrap 95% confidence intervals.

Never drop failed trials.

- [ ] **Step 4: Implement failure diagnostics**

Aggregate principal angles, restricted noiseless fidelity floors, Hessian
effective ranks, and eigenvalue gaps by model-gap magnitude. Join only records
with matching system, device orientation, and trial seed.

- [ ] **Step 5: Implement figures**

Generate:

1. `queries_vs_dimension.png`;
2. `advantage_vs_gap.png`;
3. `subspace_rotation_and_floor.png`;
4. `rank_invariant_d2_d4.png`;
5. `failure_case.png`.

Tests assert exact panel labels, logarithmic infidelity axes where used,
presence of all required methods, and deterministic file hashes for a fixed
small fixture after stripping metadata timestamps.

- [ ] **Step 6: Verify and commit**

Run:

```bash
MPLBACKEND=Agg uv run pytest tests/test_analysis.py tests/test_figures.py -q
git diff --check
```

Expected: all tests pass. Commit with `Add paired analysis and challenge figures`.

---

### Task 10: Local pilot, production gate, and report

**Files:**
- Create: `tracks/qcs/solutions/frustration-free/challenge-113/scripts/run_development.sh`
- Create: `tracks/qcs/solutions/frustration-free/challenge-113/scripts/run_production.sh`
- Create: `tracks/qcs/solutions/frustration-free/challenge-113/README.md`
- Create: `tracks/qcs/solutions/frustration-free/challenge-113/REPORT.md`
- Create locally, gitignored: `tracks/qcs/solutions/frustration-free/challenge-113/results/`
- Create: `tracks/qcs/solutions/frustration-free/challenge-113/.gitignore`

**Interfaces:**
- Consumes: the verified CLI and analysis pipeline.
- Produces: a three-seed development report and a guarded 20-seed production
  command.
- Produces: documented evidence for runtime, memory, and device selection.

- [ ] **Step 1: Add result-ignore and runner tests**

Add `results/` to the challenge-local `.gitignore`. Test both scripts with
`bash -n`. The production script must require:

```bash
: "${CHALLENGE113_ACK_PRODUCTION:?set CHALLENGE113_ACK_PRODUCTION=1}"
test "${CHALLENGE113_ACK_PRODUCTION}" = "1"
```

- [ ] **Step 2: Run the complete local verification**

Run:

```bash
uv sync --frozen --group dev
uv run pytest -q
git diff --check
```

Expected: all tests pass with no uncommitted generated results.

- [ ] **Step 3: Run and validate the development sweep**

Run:

```bash
bash scripts/run_development.sh
uv run python run.py validate --output results/development
```

The development sweep uses three seeds and a 200-query budget. Record wall
time, peak RSS, JAX platform, compilation time, warm trial throughput, and
projected production cost in `REPORT.md`.

- [ ] **Step 4: Enforce the production resource gate**

Production may proceed locally if projected wall time is at most 12 hours and
peak RSS is at most 70% of available memory. Otherwise generate a cluster
submission plan using one GPU, exact locked environment, immutable source
revision, and restartable trial shards. Do not submit until the recorded
projection exists.

- [ ] **Step 5: Run the production sweep**

After the gate passes:

```bash
CHALLENGE113_ACK_PRODUCTION=1 bash scripts/run_production.sh
uv run python run.py validate --output results/production
```

Expected coverage:

- d=2 invariant study with 20 seeds;
- d=4 headline study with 20 seeds;
- gap values `0, 0.02, 0.05, 0.10, 0.20`;
- exact, 1,000-shot, and 10,000-shot regimes;
- full, model-Hessian, random, and oracle baselines;
- no missing or duplicate paired trials.

- [ ] **Step 6: Complete the report**

`REPORT.md` must state:

- the conditional nature of the \(d^2-1\) rank;
- whether model-Hessian beats random dimensionality reduction;
- query and shot savings with paired confidence intervals;
- the model-gap crossover;
- an explicit failure case;
- numerical-resolution and rank-threshold sensitivity;
- that the finite-shot device is an abstract estimator, not randomized
  benchmarking;
- the official Colab authentication limitation;
- commands and hashes needed to reproduce the study.

- [ ] **Step 7: Final verification and commit**

Run:

```bash
uv run pytest -q
uv run python run.py validate --output results/production
git diff --check
git status --short
```

Expected: tests and production validation pass; only intended source,
documentation, and selected compact figure/report artifacts are tracked.
Commit with `Complete Challenge 113 sim-to-real study`.

## Execution order and review gates

Tasks are sequential because later scientific claims depend on validated
interfaces from earlier tasks. After every task:

1. run the focused tests;
2. inspect the commit diff;
3. review scientific correctness before continuing;
4. keep generated results untracked unless the final report explicitly selects
   compact artifacts.

Task 5 is the first scientific gate. If the d=2/d=4 geometry does not pass,
stop and diagnose controllability, objective, propagation, and regularity
before building closed-loop experiments.

Task 7 is the second scientific gate. If a deterministic small-gap fixture does
not separate model-Hessian from random subspaces, do not launch broad sweeps.

Task 10 is the compute gate. Production is authorized only by measured pilot
telemetry, not an estimate from code inspection.
