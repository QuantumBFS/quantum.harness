# VQETape Direct Tensor-Network Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add an exact direct bra-Hamiltonian-ket tensor-network VQE backend with explicit contraction paths and per-step reverse-mode rematerialization.

**Architecture:** A static template builder assigns indices and tensor sources once per VQE specification. A path planner turns the reusable topology into explicit pairwise einsum steps, and a JAX executor binds parameter-dependent gate tensors and optionally checkpoints selected steps before differentiating the scalar energy.

**Tech Stack:** Python 3.12, JAX, NumPy, opt_einsum, pytest.

## Global Constraints

- Direct-TN energy and full gradients must match the existing state-vector oracle.
- The tensor network must contract directly to a scalar.
- All TFIM Pauli terms reuse one topology and contraction program.
- Contraction paths are selected before JAX tracing.
- Rematerialization decisions apply to explicit pairwise contraction steps.
- No approximate truncation, slicing, MPO, or cuTensorNet is introduced in this phase.

---

### Task 1: Reusable Gate Matrices and Tensor-Network Template

**Files:**
- Modify: `pyproject.toml`
- Modify: `src/vqetape/kernels.py`
- Create: `src/vqetape/tn_template.py`
- Create: `tests/test_tn_template.py`

**Interfaces:**
- Produces: `rx_matrix`, `rzz_matrix`, `TensorSlot`, `TensorNetworkTemplate`,
  `ProductPauliTerm`, `build_expectation_template(spec)`, and
  `bind_term_tensors(template, theta, term)`.

- [x] **Step 1: Write template topology and binding tests**

```python
from collections import Counter

import jax.numpy as jnp

from vqetape.spec import TFIMVQESpec
from vqetape.tn_template import (
    ProductPauliTerm,
    bind_term_tensors,
    build_expectation_template,
)


def test_expectation_template_is_closed_scalar_network():
    spec = TFIMVQESpec(nqubits=3, depth=2)
    template = build_expectation_template(spec)
    counts = Counter(index for slot in template.slots for index in slot.indices)
    assert set(counts.values()) == {2}
    assert template.equation.endswith("->")
    assert len(template.slots) == 3 * spec.nqubits + 2 * spec.depth * (2 * spec.nqubits - 1)


def test_bound_term_matches_declared_shapes():
    spec = TFIMVQESpec(nqubits=3, depth=2)
    template = build_expectation_template(spec)
    theta = jnp.zeros(spec.parameter_shape)
    tensors = bind_term_tensors(
        template,
        theta,
        ProductPauliTerm(coefficient=-1.0, operators=("Z", "Z", "I")),
    )
    assert tuple(tensor.shape for tensor in tensors) == template.shapes
```

- [x] **Step 2: Run the tests and observe missing-module failure**

Run: `JAX_ENABLE_X64=1 python -m pytest tests/test_tn_template.py -q`

Expected: import failure for `vqetape.tn_template`.

- [x] **Step 3: Refactor reusable gate matrices and implement the template**

`TensorSlot` must contain `kind`, `indices`, `shape`, `layer`, and `wire`.
`TensorNetworkTemplate` must contain `spec`, `slots`, `equation`, and `shapes`.
Use `opt_einsum.get_symbol` to turn monotonically allocated integer indices
into an einsum equation. Gate tensor axes are `(output, input)` for `RX` and
`(output0, output1, input0, input1)` for `RZZ`.

- [x] **Step 4: Run existing and new kernel/template tests**

Run: `JAX_ENABLE_X64=1 python -m pytest tests/test_kernels.py tests/test_tn_template.py -q`

Expected: all pass.

- [x] **Step 5: Commit**

```bash
git add pyproject.toml src/vqetape/kernels.py src/vqetape/tn_template.py tests/test_tn_template.py
git commit -m "feat: build direct VQE tensor-network templates"
```

### Task 2: Path Planning and Explicit Pairwise Execution

**Files:**
- Create: `src/vqetape/tn_program.py`
- Create: `tests/test_tn_program.py`

**Interfaces:**
- Consumes: `TensorNetworkTemplate`.
- Produces: `ContractionProgram`, `plan_contraction(template, strategy)`, and
  `execute_contraction(program, tensors, remat_steps=frozenset())`.

- [x] **Step 1: Write explicit-executor equivalence tests**

```python
import jax.numpy as jnp
import numpy as np
import opt_einsum as oe

from vqetape.tn_program import execute_contraction, plan_contraction


def test_explicit_program_matches_opt_einsum_expression(template_and_tensors):
    template, tensors = template_and_tensors
    program = plan_contraction(template, "greedy")
    actual = execute_contraction(program, tensors)
    expected = oe.contract(
        template.equation,
        *tensors,
        optimize=list(program.path),
        backend="jax",
    )
    np.testing.assert_allclose(np.asarray(actual), np.asarray(expected), atol=1e-6)
    assert program.flops > 0
    assert program.largest_intermediate_elements > 0
    assert len(program.step_output_bytes) == len(program.steps)
```

- [x] **Step 2: Verify the missing-module failure**

Run: `python -m pytest tests/test_tn_program.py -q`

Expected: import failure for `vqetape.tn_program`.

- [x] **Step 3: Implement path planning and execution**

Call `opt_einsum.contract_path(template.equation, *template.shapes,
shapes=True, optimize=strategy)`. Build a `contract_expression` using the
explicit path and retain its `contraction_list`. For every step, pop operands
in the exact position order supplied by opt_einsum and evaluate the step's
einsum string with `jax.numpy.einsum`.

- [x] **Step 4: Run tests**

Run: `python -m pytest tests/test_tn_program.py -q`

Expected: explicit and opt_einsum execution agree for all tested paths.

- [x] **Step 5: Commit**

```bash
git add src/vqetape/tn_program.py tests/test_tn_program.py
git commit -m "feat: plan and execute explicit tensor contractions"
```

### Task 3: Exact Direct-TN VQE Value and Gradient

**Files:**
- Create: `src/vqetape/tn_vqe.py`
- Create: `tests/test_tn_vqe.py`

**Interfaces:**
- Produces: `build_tn_energy(spec, path_strategy, remat_policy, threshold_bytes)`
  and `build_tn_value_and_grad(...)`.

- [x] **Step 1: Write energy and full-gradient equivalence tests**

```python
import jax.numpy as jnp
import numpy as np
import pytest

from vqetape.programs import build_value_and_grad
from vqetape.spec import ProgramConfig, TFIMVQESpec
from vqetape.tn_vqe import build_tn_value_and_grad


@pytest.mark.parametrize("strategy", ["greedy", "random-greedy"])
@pytest.mark.parametrize("policy", ["none", "all", "output-ge-threshold"])
def test_direct_tn_matches_statevector(strategy, policy):
    spec = TFIMVQESpec(nqubits=3, depth=2)
    theta = jnp.linspace(-0.2, 0.3, np.prod(spec.parameter_shape)).reshape(spec.parameter_shape)
    reference = build_value_and_grad(
        spec, ProgramConfig(control_flow="unrolled", adjoint="default")
    )
    candidate = build_tn_value_and_grad(
        spec,
        path_strategy=strategy,
        remat_policy=policy,
        threshold_bytes=64,
    )
    ref_energy, ref_gradient = reference(theta)
    energy, gradient = candidate(theta)
    np.testing.assert_allclose(np.asarray(energy), np.asarray(ref_energy), atol=1e-5)
    np.testing.assert_allclose(np.asarray(gradient), np.asarray(ref_gradient), rtol=1e-4, atol=1e-5)
    np.testing.assert_array_equal(np.asarray(gradient[:, 0, -1]), np.zeros(spec.depth))
```

- [x] **Step 2: Verify failure**

Run: `python -m pytest tests/test_tn_vqe.py -q`

Expected: import failure for `vqetape.tn_vqe`.

- [x] **Step 3: Implement term generation and remat policies**

Generate `nqubits - 1` `ZZ` terms with coefficient `-coupling` and `nqubits`
`X` terms with coefficient `-field`. `none` produces an empty step set, `all`
selects every step, and `output-ge-threshold` selects steps whose output byte
estimate is at least `threshold_bytes`.

- [x] **Step 4: Run tests**

Run: `JAX_ENABLE_X64=1 python -m pytest tests/test_tn_vqe.py -q`

Expected: all direct-TN values and gradients match the oracle.

- [x] **Step 5: Commit**

```bash
git add src/vqetape/tn_vqe.py tests/test_tn_vqe.py
git commit -m "feat: add exact direct-TN VQE gradients"
```

### Task 4: Tensor Candidate Benchmark and Pareto Search

**Files:**
- Create: `src/vqetape/tn_candidates.py`
- Modify: `src/vqetape/worker.py`
- Modify: `src/vqetape/benchmark.py`
- Create: `tests/test_tn_candidates.py`

**Interfaces:**
- Produces: tagged tensor-program candidate requests and fresh-process results
  using the existing `CandidateResult` report contract.

- [x] **Step 1: Write candidate uniqueness and one-worker tests**

Create tests that assert three path strategies, `none`, `all`, and every unique
threshold policy generate unique labels, then run one `greedy/none` tensor
candidate in a fresh worker and assert finite compile, warm, RSS, path FLOPs,
and largest-intermediate fields.

- [x] **Step 2: Run tests and verify unsupported request failure**

Run: `python -m pytest tests/test_tn_candidates.py -q`

Expected: tensor candidate request is unsupported.

- [x] **Step 3: Implement tagged worker requests**

Add a `"program_kind": "statevector" | "direct_tn"` field to worker payloads.
For direct-TN requests, build `build_tn_value_and_grad`, attach path metrics to
`static_estimate`, and otherwise reuse the existing timing/memory protocol.

- [x] **Step 4: Run tests**

Run: `python -m pytest tests/test_tn_candidates.py tests/test_benchmark.py -q`

Expected: state-vector protocol remains compatible and tensor worker passes.

- [x] **Step 5: Commit**

```bash
git add src/vqetape/tn_candidates.py src/vqetape/worker.py src/vqetape/benchmark.py tests/test_tn_candidates.py
git commit -m "feat: search direct-TN path and tape candidates"
```

### Task 5: Evidence and Decision Audit

**Files:**
- Modify: `README.md`
- Create: `outputs/vqetape-direct-tn-report.json`
- Create: `outputs/vqetape-direct-tn-findings.md`

**Interfaces:**
- Produces: reproducible evidence for all four phase decision gates.

- [x] **Step 1: Run all tests**

Run: `JAX_ENABLE_X64=1 python -m pytest -q`

Expected: all tests pass.

- [x] **Step 2: Run the direct-TN experiment**

Run the tensor search for `nqubits=4`, `depth=3`, `complex64`, three path
strategies, all remat policies, and at least three synchronized warm repeats.
Write `outputs/vqetape-direct-tn-report.json`.

- [x] **Step 3: Audit the four gates**

Use measured report fields to state pass/fail for path diversity, measured path
effect, fixed-path remat effect, and joint Pareto improvement. Label CPU RSS
and JAX memory analysis exactly as in the oracle report.

- [x] **Step 4: Update README and mark the plan complete**

Document the direct-TN API, current scale limit, path strategies, and remat
policies. Replace each unchecked plan checkbox with a checked one only after
its command succeeds.

- [x] **Step 5: Commit**

```bash
git add README.md docs/superpowers/plans/2026-07-28-vqetape-direct-tn.md outputs/vqetape-direct-tn-report.json outputs/vqetape-direct-tn-findings.md
git commit -m "test: record direct-TN VQETape evidence"
```

## Self-Review Record

- The plan implements the approved direct scalar-contraction phase and does not
  silently include later MPO, slicing, or cuTensorNet work.
- Each task produces independently testable behavior.
- Names used by later tasks are defined in earlier task interfaces.
- Execution remains inline because subagent dispatch is not authorized.
