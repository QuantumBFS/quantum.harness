# VQETape Exact Spatial-Transfer Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use completed Markdown checkboxes for tracking.

**Goal:** Lower the exact one-dimensional TFIM bra–MPO–ket VQE network into first/bulk/last spatial contraction programs, execute the bulk with a rolled JAX scan, and compare default, rematerialized, and segmented custom adjoints against the global MPO.

**Architecture:** `spatial_plan.py` partitions the verified operator-Schmidt MPO template and plans carry-fused column contractions with exact boundary dimension \(3\cdot4^L\). `spatial_programs.py` binds site-local parameters and executes default/remat/segmented scan programs. `spatial_candidates.py` integrates fresh-process validation, Pareto selection, global-MPO controls, and reproducible CLI reports.

**Tech Stack:** Python 3.12, JAX 0.11, NumPy 2.x, opt_einsum 3.4, pytest 9

## Global Constraints

- The physical workload remains the exact open-boundary TFIM `-J sum(ZZ) - g sum(X)`.
- The source network must use exact operator-Schmidt RZZ factors and the exact bond-dimension-3 TFIM MPO.
- Every candidate returns exact energy and the complete padded gradient.
- The unused parameter gradient `gradient[:, 0, -1]` remains exactly zero.
- A bulk column contraction receives the current carry as operand zero and outputs only the next carry; it must not materialize a \(D\times D\) transfer matrix.
- The exact cut dimension is `3 * 4**depth`.
- The bulk loop must lower through `jax.lax.scan`.
- Fresh-process timing and memory metrics remain distinct from static FLOPs, logical residual bytes, and modeled checkpoint bytes.
- Global-MPO controls and spatial candidates use the same seed, dtype, correctness tolerance, hardware, and synchronization protocol.
- Every adjoint/unroll candidate for one path strategy reuses the same serialized first/bulk/last spatial paths.
- No approximation, truncation, mixed precision, slicing, multi-GPU execution, optimizer co-design, or ansatz search is added in this phase.

---

### Task 1: Spatial Program Configuration and Serialization

**Files:**
- Modify: `src/vqetape/spec.py`
- Modify: `src/vqetape/selection.py`
- Modify: `tests/test_spec.py`
- Modify: `tests/test_metrics_selection.py`

**Interfaces:**
- Produces: `SpatialAdjoint = Literal["default", "remat", "segmented"]`
- Produces: `SpatialProgramConfig`
- Produces: `CandidateResult.config` support for spatial programs

- [x] **Step 1: Write configuration validation and round-trip tests**

Add to `tests/test_spec.py`:

```python
from vqetape.spec import SpatialProgramConfig


def test_spatial_program_config_round_trip():
    config = SpatialProgramConfig(
        path_strategy="greedy",
        adjoint="segmented",
        unroll=2,
        segment_length=3,
    )
    assert SpatialProgramConfig.from_dict(config.to_dict()) == config
    assert config.label == "spatial-transfer-greedy-segmented-u2-s3"


@pytest.mark.parametrize(
    "kwargs",
    [
        {"path_strategy": "unknown", "adjoint": "default"},
        {"path_strategy": "greedy", "adjoint": "unknown"},
        {"path_strategy": "greedy", "adjoint": "default", "unroll": 0},
        {
            "path_strategy": "greedy",
            "adjoint": "segmented",
            "segment_length": None,
        },
        {
            "path_strategy": "greedy",
            "adjoint": "default",
            "segment_length": 2,
        },
    ],
)
def test_spatial_program_config_rejects_invalid_values(kwargs):
    with pytest.raises(ValueError):
        SpatialProgramConfig(**kwargs)
```

Add a `CandidateResult` JSON round-trip using this config to
`tests/test_metrics_selection.py`.

- [x] **Step 2: Run the tests and verify the missing type**

Run:

```bash
.venv/bin/pytest -q tests/test_spec.py tests/test_metrics_selection.py
```

Expected: import failure for `SpatialProgramConfig`.

- [x] **Step 3: Implement the config**

Add to `src/vqetape/spec.py`:

```python
SpatialAdjoint = Literal["default", "remat", "segmented"]


@dataclass(frozen=True)
class SpatialProgramConfig:
    path_strategy: Literal["greedy", "random-greedy", "auto-hq"]
    adjoint: SpatialAdjoint
    unroll: int = 1
    segment_length: int | None = None
    column_paths: (
        tuple[tuple[tuple[int, ...], ...], ...] | None
    ) = None
    representation: Literal["spatial_transfer"] = "spatial_transfer"

    def __post_init__(self) -> None:
        if self.path_strategy not in ("greedy", "random-greedy", "auto-hq"):
            raise ValueError(
                f"unsupported path_strategy: {self.path_strategy}"
            )
        if self.adjoint not in ("default", "remat", "segmented"):
            raise ValueError(f"unsupported adjoint: {self.adjoint}")
        if self.unroll < 1:
            raise ValueError("unroll must be positive")
        if self.representation != "spatial_transfer":
            raise ValueError(
                f"unsupported representation: {self.representation}"
            )
        if self.adjoint == "segmented":
            if self.segment_length is None or self.segment_length < 1:
                raise ValueError(
                    "segmented adjoint requires positive segment_length"
                )
        elif self.segment_length is not None:
            raise ValueError(
                "segment_length is only valid for segmented adjoint"
            )
        if self.column_paths is not None:
            if len(self.column_paths) not in (2, 3):
                raise ValueError(
                    "column paths must contain first/last or "
                    "first/bulk/last paths"
                )

    @property
    def label(self) -> str:
        base = (
            f"spatial-transfer-{self.path_strategy}-"
            f"{self.adjoint}-u{self.unroll}"
        )
        if self.segment_length is not None:
            return f"{base}-s{self.segment_length}"
        return base

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, payload: dict[str, Any]) -> SpatialProgramConfig:
        values = dict(payload)
        if values.get("column_paths") is not None:
            values["column_paths"] = tuple(
                tuple(
                    tuple(int(position) for position in step)
                    for step in path
                )
                for path in values["column_paths"]
            )
        return cls(**values)
```

Extend the config union and representation branch in `selection.py`:

```python
config: ProgramConfig | TensorProgramConfig | SpatialProgramConfig
```

and:

```python
if config_payload.get("representation") == "direct_tn":
    values["config"] = TensorProgramConfig.from_dict(config_payload)
elif config_payload.get("representation") == "spatial_transfer":
    values["config"] = SpatialProgramConfig.from_dict(config_payload)
else:
    values["config"] = ProgramConfig.from_dict(config_payload)
```

- [x] **Step 4: Run configuration tests**

Run:

```bash
.venv/bin/pytest -q tests/test_spec.py tests/test_metrics_selection.py
```

Expected: all pass.

- [x] **Step 5: Commit**

```bash
git add src/vqetape/spec.py src/vqetape/selection.py tests/test_spec.py tests/test_metrics_selection.py
git commit -m "feat: configure spatial-transfer VQETape programs"
```

---

### Task 2: Exact Spatial Partition and Boundary Analysis

**Files:**
- Create: `src/vqetape/spatial_plan.py`
- Create: `tests/test_spatial_plan.py`

**Interfaces:**
- Produces: `SpatialColumnSlot`
- Produces: `SpatialColumnProgram`
- Produces: `SpatialTransferProgram`
- Produces: `spatial_slot_site(slot: TensorSlot) -> int`
- Produces: `plan_spatial_transfer(spec, strategy) -> SpatialTransferProgram`

- [x] **Step 1: Write slot-ownership and cut-dimension tests**

Create `tests/test_spatial_plan.py`:

```python
from math import prod

import pytest

from vqetape.spatial_plan import (
    plan_spatial_transfer,
    spatial_slot_site,
)
from vqetape.spec import TFIMVQESpec
from vqetape.tn_template import build_mpo_expectation_template


@pytest.mark.parametrize("depth", [1, 2, 3])
def test_spatial_partition_has_exact_boundary_dimension(depth):
    spec = TFIMVQESpec(nqubits=4, depth=depth)
    program = plan_spatial_transfer(spec, "greedy")
    expected_shape = (2,) * (2 * depth) + (3,)
    assert program.boundary_shape == expected_shape
    assert program.boundary_dimension == 3 * 4**depth
    assert prod(program.boundary_shape) == program.boundary_dimension
    assert program.first.right_boundary_shape == expected_shape
    assert program.last.left_boundary_shape == expected_shape
    assert program.bulk is not None
    assert program.bulk.left_boundary_shape == expected_shape
    assert program.bulk.right_boundary_shape == expected_shape
    assert program.first.output_elements == program.boundary_dimension
    assert program.bulk.output_elements == program.boundary_dimension
    assert program.last.output_elements == 1


def test_rzz_factor_ownership_uses_physical_site():
    spec = TFIMVQESpec(nqubits=3, depth=1)
    template = build_mpo_expectation_template(
        spec,
        gate_representation="operator_schmidt",
    )
    left = next(slot for slot in template.slots if slot.kind == "ket_rzz_left")
    right = next(
        slot for slot in template.slots if slot.kind == "ket_rzz_right"
    )
    assert spatial_slot_site(left) == left.wire
    assert spatial_slot_site(right) == right.wire + 1


def test_two_qubit_program_has_no_bulk_column():
    program = plan_spatial_transfer(
        TFIMVQESpec(nqubits=2, depth=2),
        "greedy",
    )
    assert program.bulk is None
```

- [x] **Step 2: Verify the planner module is missing**

Run:

```bash
.venv/bin/pytest -q tests/test_spatial_plan.py
```

Expected: import failure for `vqetape.spatial_plan`.

- [x] **Step 3: Add planning records and site ownership**

Create `src/vqetape/spatial_plan.py` with:

```python
from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass
from math import prod
from typing import Literal

import opt_einsum as oe

from vqetape.spec import TFIMVQESpec
from vqetape.tn_program import ContractionStep, PathStrategy
from vqetape.tn_template import (
    SlotKind,
    TensorSlot,
    build_mpo_expectation_template,
)


@dataclass(frozen=True)
class SpatialColumnSlot:
    kind: SlotKind
    layer: int | None
    shape: tuple[int, ...]


@dataclass(frozen=True)
class SpatialColumnProgram:
    role: Literal["first", "bulk", "last"]
    equation: str
    path: tuple[tuple[int, ...], ...]
    slots: tuple[SpatialColumnSlot, ...]
    input_shapes: tuple[tuple[int, ...], ...]
    carry_is_input: bool
    left_boundary_shape: tuple[int, ...]
    right_boundary_shape: tuple[int, ...]
    flops: int
    largest_intermediate_elements: int
    output_elements: int
    steps: tuple[ContractionStep, ...]


@dataclass(frozen=True)
class SpatialTransferProgram:
    spec: TFIMVQESpec
    strategy: PathStrategy
    first: SpatialColumnProgram
    bulk: SpatialColumnProgram | None
    last: SpatialColumnProgram
    boundary_shape: tuple[int, ...]
    boundary_dimension: int


def spatial_slot_site(slot: TensorSlot) -> int:
    if slot.wire is None:
        raise ValueError(f"slot {slot.kind} has no physical location")
    if slot.kind in (
        "ket_rzz_right",
        "bra_rzz_right",
    ):
        return slot.wire + 1
    if slot.kind in (
        "ket_rzz",
        "bra_rzz",
    ):
        raise ValueError("dense RZZ tensors cannot be spatially partitioned")
    return slot.wire
```

- [x] **Step 4: Implement cut analysis**

Inside `plan_spatial_transfer`, construct the exact source template and index
uses:

```python
template = build_mpo_expectation_template(
    spec,
    gate_representation="operator_schmidt",
)
slots_by_site: dict[int, list[TensorSlot]] = defaultdict(list)
index_uses: dict[int, list[tuple[int, int]]] = defaultdict(list)
for slot in template.slots:
    site = spatial_slot_site(slot)
    if site < 0 or site >= spec.nqubits:
        raise ValueError(f"slot {slot.kind} maps outside the chain")
    slots_by_site[site].append(slot)
    for index, extent in zip(slot.indices, slot.shape, strict=True):
        index_uses[index].append((site, extent))

cuts: list[list[int]] = [[] for _ in range(spec.nqubits - 1)]
dimensions: dict[int, int] = {}
for index, uses in index_uses.items():
    extent, cut_site = _cut_for_index(index, uses)
    dimensions[index] = extent
    if cut_site is None:
        continue
    cuts[cut_site].append(index)

for cut in cuts:
    cut.sort()
cut_shapes = tuple(
    tuple(dimensions[index] for index in cut)
    for cut in cuts
)
expected_shape = (2,) * (2 * spec.depth) + (3,)
_validate_cut_shapes(cut_shapes, expected_shape)
```

- [x] **Step 5: Add explicit spatial validation helpers**

Use these helpers from Step 4 so malformed topology behavior is independently
testable:

```python
def _cut_for_index(
    index: int,
    uses: list[tuple[int, int]],
) -> tuple[int, int | None]:
    sites = sorted({site for site, _ in uses})
    extents = {extent for _, extent in uses}
    if len(extents) != 1:
        raise ValueError(f"inconsistent extent for spatial index {index}")
    extent = extents.pop()
    if len(sites) == 1:
        return extent, None
    if len(sites) != 2 or sites[1] != sites[0] + 1:
        raise ValueError(f"index {index} is not nearest-neighbor local")
    return extent, sites[0]


def _validate_cut_shapes(
    cut_shapes: tuple[tuple[int, ...], ...],
    expected_shape: tuple[int, ...],
) -> None:
    if any(shape != expected_shape for shape in cut_shapes):
        raise ValueError(
            f"inconsistent spatial cut shapes: {cut_shapes}; "
            f"expected {expected_shape}"
        )
```

- [x] **Step 6: Implement carry-fused column planning**

Add a private `_plan_column` that prepends a synthetic carry operand for bulk
and last roles:

```python
def _plan_column(
    *,
    role: Literal["first", "bulk", "last"],
    local_slots: tuple[TensorSlot, ...],
    left_indices: tuple[int, ...],
    right_indices: tuple[int, ...],
    dimensions: dict[int, int],
    strategy: PathStrategy,
) -> SpatialColumnProgram:
    carry_is_input = bool(left_indices)
    operand_indices: list[tuple[int, ...]] = []
    input_shapes: list[tuple[int, ...]] = []
    if carry_is_input:
        operand_indices.append(left_indices)
        input_shapes.append(
            tuple(dimensions[index] for index in left_indices)
        )
    for slot in local_slots:
        operand_indices.append(slot.indices)
        input_shapes.append(slot.shape)
    equation = (
        ",".join(
            "".join(oe.get_symbol(index) for index in indices)
            for indices in operand_indices
        )
        + "->"
        + "".join(oe.get_symbol(index) for index in right_indices)
    )
    path, info = oe.contract_path(
        equation,
        *input_shapes,
        shapes=True,
        optimize=strategy,
    )
    explicit_path = tuple(
        tuple(int(position) for position in item)
        for item in path
    )
```

Build the explicit steps:

```python
expression = oe.contract_expression(
    equation,
    *input_shapes,
    optimize=explicit_path,
)
symbol_dimensions = {
    oe.get_symbol(index): extent
    for index, extent in dimensions.items()
}
steps: list[ContractionStep] = []
for contraction in expression.contraction_list:
    positions, _, einsum, _, _ = contraction
    output_subscript = einsum.split("->", maxsplit=1)[1]
    step_output_elements = prod(
        symbol_dimensions[symbol] for symbol in output_subscript
    )
    steps.append(
        ContractionStep(
            positions=tuple(int(position) for position in positions),
            einsum=einsum,
            output_subscript=output_subscript,
            output_elements=step_output_elements,
        )
    )
```

Set:

```python
output_elements = prod(
    dimensions[index] for index in right_indices
)
```

with `prod(()) == 1`. Convert source slots to `SpatialColumnSlot`.

Build every site program, verify the canonical structural signature of all
bulk sites is identical, and return the first, representative bulk, and last
program. Canonicalize each index pattern before comparing bulk signatures:

```python
def _canonical_pattern(
    operands: tuple[tuple[int, ...], ...],
    output: tuple[int, ...],
) -> tuple[tuple[tuple[int, ...], ...], tuple[int, ...]]:
    mapping: dict[int, int] = {}

    def canonical(index: int) -> int:
        if index not in mapping:
            mapping[index] = len(mapping)
        return mapping[index]

    canonical_operands = tuple(
        tuple(canonical(index) for index in operand)
        for operand in operands
    )
    canonical_output = tuple(canonical(index) for index in output)
    return canonical_operands, canonical_output
```

The bulk signature is:

```python
(
    tuple((slot.kind, slot.layer, slot.shape) for slot in local_slots),
    tuple(input_shapes),
    _canonical_pattern(tuple(operand_indices), right_indices),
)
```

- [x] **Step 7: Add topology rejection tests**

Add:

```python
from vqetape.spatial_plan import (
    _cut_for_index,
    _validate_cut_shapes,
)


def test_dense_rzz_slot_has_no_spatial_owner():
    slot = TensorSlot(
        "ket_rzz",
        (0, 1, 2, 3),
        (2, 2, 2, 2),
        layer=0,
        wire=0,
    )
    with pytest.raises(ValueError, match="dense RZZ"):
        spatial_slot_site(slot)


def test_spatial_cut_rejects_nonlocal_index():
    with pytest.raises(ValueError, match="nearest-neighbor"):
        _cut_for_index(7, [(0, 2), (2, 2)])


def test_spatial_cut_rejects_inconsistent_shapes():
    with pytest.raises(ValueError, match="cut shapes"):
        _validate_cut_shapes(((2, 2, 3), (2, 3)), (2, 2, 3))
```

- [x] **Step 8: Run planning tests**

Run:

```bash
.venv/bin/pytest -q tests/test_spatial_plan.py
```

Expected: all pass.

- [x] **Step 9: Commit**

```bash
git add src/vqetape/spatial_plan.py tests/test_spatial_plan.py
git commit -m "feat: plan carry-fused spatial VQE columns"
```

---

### Task 3: Column Binding and Sequential Exactness

**Files:**
- Create: `src/vqetape/spatial_programs.py`
- Create: `tests/test_spatial_programs.py`

**Interfaces:**
- Produces: `SpatialSiteParameters`
- Produces: `bind_spatial_column(...)`
- Produces: `execute_spatial_column(...)`
- Produces: `spatial_energy_unrolled(theta, program)`

- [x] **Step 1: Write sequential energy equivalence tests**

Create `tests/test_spatial_programs.py`:

```python
import jax
import jax.numpy as jnp
import numpy as np
import pytest

from vqetape.spatial_plan import plan_spatial_transfer
from vqetape.spatial_programs import spatial_energy_unrolled
from vqetape.spec import TFIMVQESpec
from vqetape.tn_vqe import build_tn_energy


@pytest.mark.parametrize("nqubits", [2, 3, 4, 5])
@pytest.mark.parametrize("depth", [1, 2])
@pytest.mark.parametrize("initial_state", ["zero", "plus"])
def test_sequential_spatial_energy_matches_global_mpo(
    nqubits,
    depth,
    initial_state,
):
    spec = TFIMVQESpec(
        nqubits=nqubits,
        depth=depth,
        coupling=0.7,
        field=0.3,
        initial_state=initial_state,
    )
    theta = jnp.linspace(
        -0.2,
        0.3,
        np.prod(spec.parameter_shape),
        dtype=jnp.float32,
    ).reshape(spec.parameter_shape)
    program = plan_spatial_transfer(spec, "greedy")
    actual = spatial_energy_unrolled(theta, program)
    reference, _, _ = build_tn_energy(
        spec,
        path_strategy="greedy",
        remat_policy="none",
        gate_representation="operator_schmidt",
        hamiltonian_representation="mpo",
    )
    np.testing.assert_allclose(
        np.asarray(actual),
        np.asarray(reference(theta)),
        rtol=1e-5,
        atol=1e-5,
    )
```

- [x] **Step 2: Run the test and verify the runtime module is missing**

Run:

```bash
.venv/bin/pytest -q tests/test_spatial_programs.py
```

Expected: import failure for `vqetape.spatial_programs`.

- [x] **Step 3: Implement site-local parameter extraction**

Create:

```python
from typing import NamedTuple

import jax.numpy as jnp
from jax import Array


class SpatialSiteParameters(NamedTuple):
    left_rzz: Array
    right_rzz: Array
    rx: Array


def _site_parameters(
    theta: Array,
    site: int,
    spec: TFIMVQESpec,
) -> SpatialSiteParameters:
    real_dtype = theta.dtype
    zeros = jnp.zeros((spec.depth,), dtype=real_dtype)
    return SpatialSiteParameters(
        left_rzz=(
            theta[:, 0, site - 1] if site > 0 else zeros
        ),
        right_rzz=(
            theta[:, 0, site]
            if site < spec.nqubits - 1
            else zeros
        ),
        rx=theta[:, 1, site],
    )
```

Validate `theta.shape == spec.parameter_shape`.

- [x] **Step 4: Implement local tensor binding**

For every `SpatialColumnSlot`:

```python
if slot.kind == "initial_ket":
    tensor = product_state
elif slot.kind == "initial_bra":
    tensor = jnp.conj(product_state)
elif slot.kind in ("ket_rx", "bra_rx"):
    tensor = rx_matrix(parameters.rx[slot.layer], dtype)
    if slot.kind == "bra_rx":
        tensor = jnp.conj(tensor)
elif slot.kind in (
    "ket_rzz_left",
    "bra_rzz_left",
):
    tensor, _ = rzz_schmidt_factors(
        parameters.right_rzz[slot.layer],
        dtype,
    )
    if slot.kind == "bra_rzz_left":
        tensor = jnp.conj(tensor)
elif slot.kind in (
    "ket_rzz_right",
    "bra_rzz_right",
):
    _, tensor = rzz_schmidt_factors(
        parameters.left_rzz[slot.layer],
        dtype,
    )
    if slot.kind == "bra_rzz_right":
        tensor = jnp.conj(tensor)
elif slot.kind.startswith("hamiltonian_mpo_"):
    tensor = mpo_tensor_for_role
else:
    raise ValueError(f"unsupported spatial slot kind: {slot.kind}")
```

Use the exact product-state helper convention from `tn_template.py` and
`tfim_mpo_tensors(spec)` for first, bulk, and last MPO tensors. Verify every
bound shape against `slot.shape`.

Implement the product-state vector locally without importing a private
function:

```python
def _product_state_vector(spec: TFIMVQESpec) -> Array:
    dtype = (
        jnp.complex64
        if spec.dtype == "complex64"
        else jnp.complex128
    )
    if spec.initial_state == "zero":
        return jnp.asarray([1, 0], dtype=dtype)
    amplitude = jnp.asarray(1 / jnp.sqrt(2), dtype=dtype)
    return jnp.asarray([amplitude, amplitude], dtype=dtype)
```

- [x] **Step 5: Implement the explicit column executor**

`execute_spatial_column` receives `carry=None` for first and a correctly
shaped carry for bulk/last:

```python
operands = list(tensors)
if program.carry_is_input:
    if carry is None:
        raise ValueError("column requires a boundary carry")
    if tuple(carry.shape) != program.left_boundary_shape:
        raise ValueError("boundary carry shape does not match column")
    operands.insert(0, carry)
elif carry is not None:
    raise ValueError("first column does not accept a boundary carry")

for step in program.steps:
    selected = [operands.pop(position) for position in step.positions]
    contracted = jnp.einsum(step.einsum, *selected, optimize=True)
    operands.append(contracted)
```

Require one final operand with shape `right_boundary_shape`, or scalar shape
for last.

- [x] **Step 6: Implement sequential first/bulk/last execution**

`spatial_energy_unrolled`:

```python
carry = execute_spatial_column(
    program.first,
    None,
    bind_spatial_column(
        program.first,
        _site_parameters(theta, 0, program.spec),
        program.spec,
    ),
)
for site in range(1, program.spec.nqubits - 1):
    assert program.bulk is not None
    carry = execute_spatial_column(
        program.bulk,
        carry,
        bind_spatial_column(
            program.bulk,
            _site_parameters(theta, site, program.spec),
            program.spec,
        ),
    )
energy = execute_spatial_column(
    program.last,
    carry,
    bind_spatial_column(
        program.last,
        _site_parameters(
            theta,
            program.spec.nqubits - 1,
            program.spec,
        ),
        program.spec,
    ),
)
return jnp.real(energy)
```

- [x] **Step 7: Add complex128 and malformed-carry tests**

Under `jax.enable_x64()`, compare one `n=3`, `depth=1` case at `rtol=1e-10`,
`atol=1e-10`. Verify missing and wrong-shape carries raise the exact messages
from Step 5.

- [x] **Step 8: Run sequential runtime tests**

Run:

```bash
.venv/bin/pytest -q tests/test_spatial_programs.py
```

Expected: all pass.

- [x] **Step 9: Commit**

```bash
git add src/vqetape/spatial_programs.py tests/test_spatial_programs.py
git commit -m "feat: execute exact spatial VQE columns"
```

---

### Task 4: Rolled Spatial Scan and Full Gradient

**Files:**
- Modify: `src/vqetape/spatial_programs.py`
- Modify: `tests/test_spatial_programs.py`

**Interfaces:**
- Produces: `build_spatial_energy(spec, config)`
- Produces: `build_spatial_value_and_grad(spec, config)`

- [x] **Step 1: Write energy and complete-gradient matrix tests**

Add:

```python
from vqetape.spatial_programs import build_spatial_energy
from vqetape.spec import SpatialProgramConfig


@pytest.mark.parametrize("nqubits", [2, 3, 5])
@pytest.mark.parametrize("depth", [1, 2])
@pytest.mark.parametrize("adjoint", ["default", "remat"])
def test_spatial_scan_matches_statevector_full_gradient(
    nqubits,
    depth,
    adjoint,
):
    spec = TFIMVQESpec(nqubits=nqubits, depth=depth)
    theta = jnp.linspace(
        -0.1,
        0.2,
        np.prod(spec.parameter_shape),
        dtype=jnp.float32,
    ).reshape(spec.parameter_shape)
    config = SpatialProgramConfig("greedy", adjoint, unroll=1)
    energy = build_spatial_energy(spec, config)
    actual_energy, actual_gradient = jax.value_and_grad(energy)(theta)
    reference, _, _ = build_tn_energy(
        spec,
        path_strategy="greedy",
        remat_policy="none",
        hamiltonian_representation="mpo",
    )
    expected_energy, expected_gradient = jax.value_and_grad(reference)(theta)
    np.testing.assert_allclose(actual_energy, expected_energy, atol=1e-5)
    np.testing.assert_allclose(
        actual_gradient,
        expected_gradient,
        rtol=1e-4,
        atol=1e-5,
    )
    np.testing.assert_array_equal(
        np.asarray(actual_gradient[:, 0, -1]),
        np.zeros((depth,), dtype=np.float32),
    )
```

- [x] **Step 2: Implement packed bulk inputs**

```python
def _bulk_parameters(theta: Array) -> Array:
    return jnp.stack(
        (
            theta[:, 0, 0:-2].T,
            theta[:, 0, 1:-1].T,
            theta[:, 1, 1:-1].T,
        ),
        axis=1,
    )
```

The result shape is `(nqubits - 2, 3, depth)`, with axis one ordered
`left_rzz, right_rzz, rx`.

- [x] **Step 3: Implement one bulk transition**

```python
def _bulk_transition(
    carry: Array,
    packed_site: Array,
    *,
    spec: TFIMVQESpec,
    program: SpatialColumnProgram,
) -> Array:
    parameters = SpatialSiteParameters(
        left_rzz=packed_site[0],
        right_rzz=packed_site[1],
        rx=packed_site[2],
    )
    tensors = bind_spatial_column(program, parameters, spec)
    return execute_spatial_column(program, carry, tensors)
```

- [x] **Step 4: Build the rolled energy**

Plan once when `build_spatial_energy` is called. In the returned energy:

1. validate theta shape;
2. execute first;
3. for `nqubits > 2`, run:

```python
body = lambda carry, packed: (
    _bulk_transition(
        carry,
        packed,
        spec=spec,
        program=transfer.bulk,
    ),
    None,
)
if config.adjoint == "remat":
    body = jax.checkpoint(body)
carry, _ = jax.lax.scan(
    body,
    carry,
    _bulk_parameters(theta),
    unroll=min(config.unroll, spec.nqubits - 2),
)
```

4. execute last and return its real component.

`build_spatial_value_and_grad` returns:

```python
jax.jit(jax.value_and_grad(build_spatial_energy(spec, config)))
```

- [x] **Step 5: Verify rolled control flow**

For `nqubits=6`, `depth=1`, lower a default-u1 value-and-gradient executable:

```python
text = executable.lower(theta).as_text()
assert "while" in text.lower()
```

Also verify the energy and gradient still match when `unroll=2`.

- [x] **Step 6: Run scan tests**

Run:

```bash
.venv/bin/pytest -q tests/test_spatial_programs.py
```

Expected: all pass.

- [x] **Step 7: Commit**

```bash
git add src/vqetape/spatial_programs.py tests/test_spatial_programs.py
git commit -m "feat: lower spatial VQE through rolled scan"
```

---

### Task 5: Segmented Bulk Custom Adjoint

**Files:**
- Modify: `src/vqetape/spatial_programs.py`
- Modify: `tests/test_spatial_programs.py`
- Modify: `tests/test_tape.py`

**Interfaces:**
- Produces: segmented behavior in `build_spatial_energy`
- Produces: `modeled_spatial_checkpoint_count(spec, config)`

- [x] **Step 1: Write segmented correctness tests**

Add:

```python
@pytest.mark.parametrize(
    ("nqubits", "segment_length"),
    [(4, 1), (7, 2), (8, 3)],
)
def test_segmented_spatial_adjoint_matches_default(
    nqubits,
    segment_length,
):
    spec = TFIMVQESpec(nqubits=nqubits, depth=1)
    theta = jnp.linspace(
        -0.2,
        0.2,
        np.prod(spec.parameter_shape),
        dtype=jnp.float32,
    ).reshape(spec.parameter_shape)
    default = build_spatial_energy(
        spec,
        SpatialProgramConfig("greedy", "default"),
    )
    segmented = build_spatial_energy(
        spec,
        SpatialProgramConfig(
            "greedy",
            "segmented",
            segment_length=segment_length,
        ),
    )
    default_value = jax.value_and_grad(default)(theta)
    segmented_value = jax.value_and_grad(segmented)(theta)
    np.testing.assert_allclose(
        segmented_value[0],
        default_value[0],
        atol=1e-5,
    )
    np.testing.assert_allclose(
        segmented_value[1],
        default_value[1],
        rtol=1e-4,
        atol=1e-5,
    )
```

Add a config/runtime test that segmented execution rejects `nqubits=2`
because no shape-preserving bulk recurrence exists.

- [x] **Step 2: Implement fixed-size segment preparation**

For `m = spec.nqubits - 2`:

```python
segment_count = ceil(m / segment_length)
padded_count = segment_count * segment_length
padding = padded_count - m
packed = _bulk_parameters(theta)
if padding:
    packed = jnp.pad(packed, ((0, padding), (0, 0), (0, 0)))
mask = jnp.arange(padded_count) < m
segments = packed.reshape(
    segment_count,
    segment_length,
    3,
    spec.depth,
)
masks = mask.reshape(segment_count, segment_length)
```

- [x] **Step 3: Implement a masked segment transition**

```python
def run_segment(
    boundary: Array,
    packed_segment: Array,
    mask_segment: Array,
) -> Array:
    def step(carry, inputs):
        packed_site, valid = inputs
        next_carry = _bulk_transition(
            carry,
            packed_site,
            spec=spec,
            program=transfer.bulk,
        )
        return jnp.where(valid, next_carry, carry), None

    final, _ = jax.lax.scan(
        step,
        boundary,
        (packed_segment, mask_segment),
        unroll=min(config.unroll, segment_length),
    )
    return final
```

- [x] **Step 4: Implement the custom VJP**

Create a closure `segmented_bulk(initial_boundary, packed_bulk)` with
`@jax.custom_vjp`.

The forward helper scans segments and emits every segment input boundary:

```python
def segment_body(boundary, inputs):
    packed_segment, mask_segment = inputs
    next_boundary = run_segment(
        boundary,
        packed_segment,
        mask_segment,
    )
    return next_boundary, boundary

final, checkpoints = jax.lax.scan(
    segment_body,
    initial_boundary,
    (segments, masks),
)
```

Save `(segments, masks, checkpoints)` as the residual.

The backward scan:

```python
def reverse_segment(boundary_cotangent, inputs):
    packed_segment, mask_segment, left_boundary = inputs
    _, pullback = jax.vjp(
        lambda boundary, values: run_segment(
            boundary,
            values,
            mask_segment,
        ),
        left_boundary,
        packed_segment,
    )
    left_cotangent, packed_cotangent = pullback(
        boundary_cotangent
    )
    return left_cotangent, packed_cotangent

left_cotangent, segment_cotangents = jax.lax.scan(
    reverse_segment,
    final_cotangent,
    (segments, masks, checkpoints),
    reverse=True,
)
packed_cotangent = segment_cotangents.reshape(
    padded_count,
    3,
    spec.depth,
)[:m]
return left_cotangent, packed_cotangent
```

The outer energy keeps first/last outside this custom VJP. Confirm the padded
gradient is discarded by slicing to `m`.

- [x] **Step 5: Add the checkpoint storage model**

```python
def modeled_spatial_checkpoint_count(
    spec: TFIMVQESpec,
    config: SpatialProgramConfig,
) -> int:
    bulk_count = spec.nqubits - 2
    if config.adjoint == "segmented":
        assert config.segment_length is not None
        return (
            ceil(bulk_count / config.segment_length)
            + config.segment_length
        )
    return bulk_count
```

Test exact counts for `(n=8, s=2)` and `(n=8, s=3)`.

- [x] **Step 6: Compare structured residual profiles**

In `tests/test_tape.py`, profile default, remat, and segmented spatial energy
for `n=8`, `depth=1`. Require all profiles to be finite and nonempty. Require
segmented correctness independently; do not assert compiler peak from logical
residual bytes.

- [x] **Step 7: Run segmented and tape tests**

Run:

```bash
.venv/bin/pytest -q tests/test_spatial_programs.py tests/test_tape.py
```

Expected: all pass.

- [x] **Step 8: Commit**

```bash
git add src/vqetape/spatial_programs.py tests/test_spatial_programs.py tests/test_tape.py
git commit -m "feat: add segmented spatial VQE adjoint"
```

---

### Task 6: Fresh-Worker Measurement and Static Metrics

**Files:**
- Modify: `src/vqetape/benchmark.py`
- Modify: `src/vqetape/worker.py`
- Modify: `tests/test_benchmark.py`

**Interfaces:**
- Produces: `benchmark_spatial_candidate(...)`
- Consumes: `SpatialProgramConfig`, spatial program builders
- Produces: spatial `CandidateResult.static_estimate`

- [x] **Step 1: Write fresh-worker spatial metric tests**

Add:

```python
from vqetape.benchmark import benchmark_spatial_candidate
from vqetape.spec import SpatialProgramConfig


def test_spatial_candidate_runs_in_fresh_worker():
    spec = TFIMVQESpec(nqubits=4, depth=1)
    result = benchmark_spatial_candidate(
        spec=spec,
        config=SpatialProgramConfig("greedy", "default"),
        seed=0,
        warm_repeats=1,
        timeout_seconds=120,
    )
    assert result.valid
    assert result.worker_pid != result.parent_pid
    assert result.static_estimate["boundary_dimension"] == 12
    assert result.static_estimate["boundary_bytes"] == 96
    assert result.static_estimate["bulk_columns"] == 2
    assert result.static_estimate["bulk_path_flops"] > 0
    assert result.static_estimate["estimated_energy_flops"] > 0
    assert result.static_estimate["modeled_checkpoint_boundaries"] == 2
    assert result.static_estimate["residual_profile"]["total_bytes"] > 0
```

- [x] **Step 2: Verify the benchmark function is missing**

Run:

```bash
.venv/bin/pytest -q tests/test_benchmark.py
```

Expected: import failure.

- [x] **Step 3: Add parent-side spatial worker orchestration**

Add `benchmark_spatial_candidate` following the existing fresh-process
contract, with payload:

```python
{
    "program_kind": "spatial_transfer",
    "spec": spec.to_dict(),
    "config": config.to_dict(),
    "seed": seed,
    "warm_repeats": warm_repeats,
    "parent_pid": parent_pid,
}
```

Use a `vqetape-spatial-` temporary prefix and return an invalid
`CandidateResult` on timeout, missing result, malformed JSON, or inconsistent
exit status. Extend `_invalid_result` to accept:

```python
ProgramConfig | TensorProgramConfig | SpatialProgramConfig
```

- [x] **Step 4: Add the worker branch**

Parse:

```python
elif program_kind == "spatial_transfer":
    config = SpatialProgramConfig.from_dict(payload["config"])
```

Build:

```python
transfer = plan_spatial_transfer(
    spec,
    config.path_strategy,
    explicit_paths=config.column_paths,
)
energy_function = build_spatial_energy(spec, config)
residual_profile = profile_saved_residuals(energy_function, theta)
executable = jax.jit(jax.value_and_grad(energy_function))
bulk_flops = transfer.bulk.flops if transfer.bulk is not None else 0
boundary_bytes = transfer.boundary_dimension * dtype_bytes(spec.dtype)
checkpoint_count = modeled_spatial_checkpoint_count(spec, config)
```

Report:

```python
static_estimate = {
    "representation": "spatial_transfer",
    "path_strategy": config.path_strategy,
    "adjoint": config.adjoint,
    "unroll": config.unroll,
    "segment_length": config.segment_length,
    "boundary_rank": len(transfer.boundary_shape),
    "boundary_shape": list(transfer.boundary_shape),
    "boundary_dimension": transfer.boundary_dimension,
    "boundary_bytes": boundary_bytes,
    "bulk_columns": max(0, spec.nqubits - 2),
    "first_path_flops": transfer.first.flops,
    "bulk_path_flops": bulk_flops,
    "last_path_flops": transfer.last.flops,
    "estimated_energy_flops": (
        transfer.first.flops
        + max(0, spec.nqubits - 2) * bulk_flops
        + transfer.last.flops
    ),
    "modeled_checkpoint_boundaries": checkpoint_count,
    "modeled_checkpoint_bytes": checkpoint_count * boundary_bytes,
    "residual_profile": residual_profile.to_dict(),
}
```

Extend worker exception recovery and `CandidateResult` parsing for the new
representation.

- [x] **Step 5: Run benchmark tests**

Run:

```bash
.venv/bin/pytest -q tests/test_benchmark.py
```

Expected: all pass.

- [x] **Step 6: Commit**

```bash
git add src/vqetape/benchmark.py src/vqetape/worker.py tests/test_benchmark.py
git commit -m "feat: measure spatial VQE programs in fresh workers"
```

---

### Task 7: Joint Spatial and Global-MPO Search

**Files:**
- Create: `src/vqetape/spatial_candidates.py`
- Create: `tests/test_spatial_candidates.py`
- Modify: `src/vqetape/cli.py`
- Modify: `tests/test_compiler_cli.py`

**Interfaces:**
- Produces: `enumerate_spatial_candidates(request)`
- Produces: `search_spatial_candidates(request)`
- Produces: CLI mode `spatial-transfer`

- [x] **Step 1: Write candidate enumeration tests**

Create:

```python
from vqetape.spatial_candidates import enumerate_spatial_candidates


def test_spatial_candidates_cover_path_and_adjoint_axes():
    request = CompileRequest(
        spec=TFIMVQESpec(nqubits=8, depth=1),
        memory_budget_bytes=2 * 1024**3,
        expected_vqe_steps=100,
        warm_repeats=1,
    )
    candidates = enumerate_spatial_candidates(request)
    assert {item.path_strategy for item in candidates} == {
        "greedy",
        "random-greedy",
        "auto-hq",
    }
    assert {item.adjoint for item in candidates} == {
        "default",
        "remat",
        "segmented",
    }
    assert {
        item.unroll
        for item in candidates
        if item.adjoint in ("default", "remat")
    } == {1, 2}
    assert {
        item.segment_length
        for item in candidates
        if item.adjoint == "segmented"
    } == {2}
    assert len(candidates) == 15
```

Since `round(sqrt(6)) == 2`, the segmented candidate uses length two.

- [x] **Step 2: Implement deterministic enumeration**

For each path strategy emit:

```python
transfer = plan_spatial_transfer(request.spec, strategy)
column_paths = (
    (transfer.first.path, transfer.last.path)
    if transfer.bulk is None
    else (
        transfer.first.path,
        transfer.bulk.path,
        transfer.last.path,
    )
)
SpatialProgramConfig(
    strategy, "default", unroll=1, column_paths=column_paths
)
SpatialProgramConfig(
    strategy, "default", unroll=2, column_paths=column_paths
)
SpatialProgramConfig(
    strategy, "remat", unroll=1, column_paths=column_paths
)
SpatialProgramConfig(
    strategy, "remat", unroll=2, column_paths=column_paths
)
SpatialProgramConfig(
    strategy,
    "segmented",
    unroll=1,
    segment_length=max(1, round(sqrt(spec.nqubits - 2))),
    column_paths=column_paths,
)
```

Clamp unroll to the bulk count, deduplicate with a set, and sort by label. For
two qubits emit one default-u1 candidate per path and no segmented candidate.
Assert that all configs for one strategy contain exactly one common path
tuple and produce identical first/bulk/last FLOP counts.

- [x] **Step 3: Implement joint validation and controls**

Create `SpatialSearchResult` with:

```python
request: CompileRequest
selected: CandidateResult
pareto: tuple[CandidateResult, ...]
candidates: tuple[CandidateResult, ...]
reference: CandidateResult
```

Measure one state-vector reference. Measure three global controls using:

```python
TensorProgramConfig(
    path_strategy=strategy,
    remat_policy="none",
    gate_representation="dense",
    hamiltonian_representation="mpo",
)
```

Plan and serialize each global control path before benchmarking. Measure all
spatial configs. Validate every energy and gradient against the state-vector
reference with `CorrectnessTolerance.for_dtype`. Run Pareto selection and
horizon selection over the union of global controls and spatial candidates.

`to_report()` includes the reference separately and notes:

- global vs spatial representation;
- logical residuals are not liveness-aware peak;
- modeled checkpoint bytes are not measured device peak;
- process RSS is not GPU peak.

- [x] **Step 4: Add the CLI mode**

Extend:

```python
choices=("statevector", "direct-tn", "spatial-transfer")
```

Dispatch `spatial-transfer` to `search_spatial_candidates`.

- [x] **Step 5: Add an end-to-end CLI test**

Run `vqetape --mode spatial-transfer` with `nqubits=3`, `depth=1`,
`warm-repeats=1`, and a temporary output file. Assert:

```python
payload["selected"]["config"]["representation"] in {
    "direct_tn",
    "spatial_transfer",
}
assert payload["reference"]["valid"]
assert all(item["valid"] for item in payload["candidates"])
```

- [x] **Step 6: Run candidate and CLI tests**

Run:

```bash
.venv/bin/pytest -q tests/test_spatial_candidates.py tests/test_compiler_cli.py
```

Expected: all pass.

- [x] **Step 7: Commit**

```bash
git add src/vqetape/spatial_candidates.py tests/test_spatial_candidates.py src/vqetape/cli.py tests/test_compiler_cli.py
git commit -m "feat: search spatial and global MPO VQE programs"
```

---

### Task 8: Control-Flow and Scaling Evidence

**Files:**
- Modify: `tests/test_spatial_programs.py`
- Create: `outputs/vqetape-spatial-transfer-findings.md`

**Interfaces:**
- Consumes: complete spatial implementation
- Produces: compiler-control-flow evidence and experiment checklist

- [x] **Step 1: Add StableHLO size comparison**

For fixed `depth=1`, lower default-u1 value-and-gradient programs for
`nqubits=6` and `nqubits=10`:

```python
texts = {}
for nqubits in (6, 10):
    spec = TFIMVQESpec(nqubits=nqubits, depth=1)
    theta = jnp.zeros(spec.parameter_shape, dtype=jnp.float32)
    executable = build_spatial_value_and_grad(
        spec,
        SpatialProgramConfig("greedy", "default", unroll=1),
    )
    texts[nqubits] = executable.lower(theta).as_text()
    assert "while" in texts[nqubits].lower()
assert len(texts[10]) < 2 * len(texts[6])
```

This gate demonstrates rolled structure without claiming invariant total IR
size.

- [x] **Step 2: Add a no-transfer-matrix structural assertion**

For `depth=2`, require:

```python
program = plan_spatial_transfer(
    TFIMVQESpec(nqubits=5, depth=2),
    "greedy",
)
assert program.boundary_dimension == 48
assert program.bulk is not None
assert program.bulk.output_elements == 48
assert program.bulk.output_elements != 48**2
```

Also require:

```python
assert max(
    step.output_elements for step in program.bulk.steps
) < 48**2
```

This proves that the tested path does not emit a \(D^2\) intermediate as well
as not returning one.

- [x] **Step 3: Run control-flow tests**

Run:

```bash
.venv/bin/pytest -q tests/test_spatial_plan.py tests/test_spatial_programs.py
```

Expected: all pass.

- [x] **Step 4: Create the findings skeleton**

Create sections:

```markdown
# VQETape Exact Spatial-Transfer Findings

## Experimental contract
## Correctness and structural invariants
## Global MPO versus spatial-transfer results
## Default, remat, and segmented adjoints
## Fixed-depth scaling
## Decision-gate audit
## Interpretation and limitations
```

Record the test commands and structural facts already established. Leave
numeric benchmark tables out until Task 9 produces the reports.

- [x] **Step 5: Commit**

```bash
git add tests/test_spatial_programs.py tests/test_spatial_plan.py outputs/vqetape-spatial-transfer-findings.md
git commit -m "test: validate rolled spatial VQE structure"
```

---

### Task 9: Reproducible Spatial Benchmarks and Documentation

**Files:**
- Create: `outputs/vqetape-spatial-transfer-report-n8-d2.json`
- Create: `outputs/vqetape-spatial-transfer-report-n12-d2.json`
- Modify: `outputs/vqetape-spatial-transfer-findings.md`
- Modify: `README.md`

**Interfaces:**
- Consumes: complete joint search and fresh-worker metrics
- Produces: two fixed-depth scaling reports and decision-gate result

- [x] **Step 1: Run the primary benchmark**

```bash
.venv/bin/vqetape \
  --mode spatial-transfer \
  --nqubits 8 \
  --depth 2 \
  --memory-budget-gib 2 \
  --expected-steps 100 \
  --warm-repeats 3 \
  --timeout-seconds 600 \
  --output outputs/vqetape-spatial-transfer-report-n8-d2.json
```

- [x] **Step 2: Run the fixed-depth holdout**

```bash
.venv/bin/vqetape \
  --mode spatial-transfer \
  --nqubits 12 \
  --depth 2 \
  --coupling 0.7 \
  --field 0.3 \
  --initial-state zero \
  --memory-budget-gib 2 \
  --expected-steps 100 \
  --warm-repeats 3 \
  --timeout-seconds 600 \
  --output outputs/vqetape-spatial-transfer-report-n12-d2.json
```

- [x] **Step 3: Audit report invariants**

For both JSON reports verify:

```text
reference valid
all successful candidates have finite energy and gradient
maximum errors satisfy dtype tolerance
every spatial boundary dimension is 48
every spatial boundary shape contains four dimensions of 2 and one of 3
every spatial candidate contains a residual profile
global controls use direct_tn+dense+mpo
spatial candidates use spatial_transfer
selected candidate belongs to the reported Pareto frontier
```

Compute:

- best global and best spatial compile time;
- best global and best spatial warm median;
- compiler temporary bytes;
- process RSS;
- logical residual bytes;
- modeled checkpoint bytes;
- whether segmented is nondominated within a fixed path;
- representation selected for a 100-step horizon;
- fixed-depth changes from \(n=8\) to \(n=12\).

- [x] **Step 4: Complete the findings**

Populate exact numeric tables and audit every design decision gate. If
segmented checkpointing fails to reduce a measured/compiler memory metric,
state that negative result and retain default/remat as eligible defaults. If
spatial loses at \(n=8\) but improves scaling at \(n=12\), report the
crossover evidence without claiming universal superiority.

- [x] **Step 5: Update README**

Document:

- the `spatial-transfer` CLI mode;
- the exact \(D=3\cdot4^L\) boundary;
- carry-fused column contractions;
- default/remat/segmented spatial adjoints;
- the distinction between modeled checkpoint bytes and measured memory;
- links to the findings and two reports.

- [x] **Step 6: Run the full suite**

```bash
.venv/bin/pytest -q
```

Expected: all pass.

- [x] **Step 7: Commit**

```bash
git add README.md outputs/vqetape-spatial-transfer-report-n8-d2.json outputs/vqetape-spatial-transfer-report-n12-d2.json outputs/vqetape-spatial-transfer-findings.md
git commit -m "test: report spatial-transfer VQETape evidence"
```

---

### Task 10: Completion Audit

**Files:**
- Modify: `docs/superpowers/plans/2026-07-29-vqetape-spatial-transfer.md`
- Modify: `outputs/vqetape-spatial-transfer-findings.md`

**Interfaces:**
- Consumes: design, source, tests, reports, and git state
- Produces: checked implementation plan and exact completion evidence

- [x] **Step 1: Match requirements to authoritative evidence**

```text
configuration          -> config validation and JSON round-trip tests
spatial ownership      -> slot-site and nearest-neighbor cut tests
boundary dimension     -> L=1,2,3 exact structural tests
carry fusion           -> bulk output D, not D^2, and step audit
column algebra         -> sequential spatial/global-MPO comparisons
rolled scan            -> StableHLO while and IR-size comparison
full gradient          -> statevector/global-MPO matrix tests
segmented custom VJP   -> nondivisible-segment gradient tests
fresh measurements     -> isolated-worker PID and static metric tests
joint selection        -> global controls plus spatial candidate tests
fixed-depth evidence   -> n=8 and n=12 reports
decision gates         -> findings audit
```

- [x] **Step 2: Run final regression**

```bash
.venv/bin/pytest -q
```

Record the exact count and elapsed time in the findings.

- [x] **Step 3: Verify repository state**

```bash
git status --short
git diff --check
```

Expected: only the plan and findings completion edits are present.

- [x] **Step 4: Mark completed checkboxes and commit**

```bash
git add docs/superpowers/plans/2026-07-29-vqetape-spatial-transfer.md outputs/vqetape-spatial-transfer-findings.md
git commit -m "docs: complete spatial-transfer VQETape phase"
```
