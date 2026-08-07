# VQETape AD-Aware Contraction Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Analyze and execute complete differentiated spatial contractions so
VQETape can rank paths by forward plus reverse cost and compare an explicit
contraction VJP with generic JAX reverse mode.

**Architecture:** A new pure static-analysis module reconstructs active
operand shapes for every serialized contraction step, generates the reverse
einsums, and accounts for forward/reverse FLOPs, traffic, residual elements,
and largest intermediates. A custom-VJP contraction executor saves leaf
operands, recomputes forward intermediates during backward, and applies the
explicit reverse einsums. Spatial planning aggregates these costs across
first, repeated block, tail, and last programs and reports an AD-aware rank
before empirical fresh-process selection.

**Tech Stack:** Python 3.12, JAX custom VJP, NumPy, opt_einsum, pytest,
fresh-process VQETape workers.

## Global Constraints

- Preserve exact complex-valued JAX cotangent conventions.
- Validate every explicit VJP against `jax.vjp` and complete VQE gradients.
- Do not use measured warm time as an input to the first static cost model.
- Keep the existing forward-only paths and AD schedules as controls.
- Serialize every measured path and cost vector in the JSON report.
- Static ranking may prune only when an explicit budget is requested; the
  default scientific report measures the complete comparison set.

---

### Task 1: Reconstruct differentiated contraction costs

**Files:**
- Create: `src/vqetape/ad_analysis.py`
- Create: `tests/test_ad_analysis.py`

**Interfaces:**

```python
@dataclass(frozen=True)
class DifferentiatedContractionCost:
    forward_flops: int
    backward_flops: int
    forward_read_elements: int
    forward_write_elements: int
    backward_read_elements: int
    backward_write_elements: int
    residual_elements: int
    peak_live_residual_elements: int
    largest_forward_intermediate_elements: int
    largest_backward_intermediate_elements: int
    forward_contractions: int
    backward_contractions: int

    @property
    def total_flops(self) -> int:
        return self.forward_flops + self.backward_flops

    @property
    def traffic_elements(self) -> int:
        return (
            self.forward_read_elements
            + self.forward_write_elements
            + self.backward_read_elements
            + self.backward_write_elements
        )

    def to_dict(self) -> dict[str, int]:
        payload = asdict(self)
        payload["total_flops"] = self.total_flops
        payload["traffic_elements"] = self.traffic_elements
        return payload


@dataclass(frozen=True)
class ReverseStep:
    forward_step_index: int
    input_index: int
    equation: str
    input_shapes: tuple[tuple[int, ...], ...]
    output_shape: tuple[int, ...]
    flops: int
    largest_intermediate_elements: int


def reverse_einsum_equation(
    forward_equation: str,
    input_index: int,
) -> str:
    left, output = forward_equation.split("->", maxsplit=1)
    inputs = tuple(left.split(","))
    parts = (output,) + tuple(
        value
        for index, value in enumerate(inputs)
        if index != input_index
    )
    return ",".join(parts) + "->" + inputs[input_index]


def analyze_contraction_steps(
    input_shapes: tuple[tuple[int, ...], ...],
    steps: tuple[ContractionStep, ...],
) -> tuple[
    DifferentiatedContractionCost,
    tuple[tuple[ReverseStep, ...], ...],
]:
    """Analyze the serialized forward steps and their generated VJPs."""
```

- [ ] **Step 1: Write hand-checkable reverse-equation tests**

```python
def test_reverse_equations_for_matrix_product():
    equation = "ab,bc->ac"
    assert reverse_einsum_equation(equation, 0) == "ac,bc->ab"
    assert reverse_einsum_equation(equation, 1) == "ac,ab->bc"


def test_reverse_equation_for_scalar_inner_product():
    equation = "ab,ab->"
    assert reverse_einsum_equation(equation, 0) == ",ab->ab"
    assert reverse_einsum_equation(equation, 1) == ",ab->ab"
```

- [ ] **Step 2: Write a differentiated-cost test**

Construct:

```python
steps = (
    ContractionStep(
        positions=(1, 0),
        einsum="bc,ab->ac",
        output_subscript="ac",
        output_elements=8,
    ),
    ContractionStep(
        positions=(1, 0),
        einsum="ac,ac->",
        output_subscript="",
        output_elements=1,
    ),
)
```

with input shapes `((2, 3), (3, 4), (2, 4))`. Assert:

```python
cost, reverse = analyze_contraction_steps(input_shapes, steps)
assert cost.forward_flops > 0
assert cost.backward_flops > cost.forward_flops
assert cost.residual_elements == 6 + 12 + 8 + 8
assert cost.peak_live_residual_elements == cost.residual_elements
assert cost.forward_contractions == 2
assert cost.backward_contractions == 4
assert len(reverse) == 2
assert tuple(len(group) for group in reverse) == (2, 2)
```

- [ ] **Step 3: Run tests and verify failure**

Run:

```bash
.venv/bin/pytest tests/test_ad_analysis.py -q
```

Expected: import failure because the module does not exist.

- [ ] **Step 4: Implement equation parsing and shape propagation**

Split every equation with:

```python
left, output_subscript = equation.split("->", maxsplit=1)
input_subscripts = tuple(left.split(","))
```

Map symbols to extents from each `(subscript, shape)` pair and reject:

```python
if len(subscript) != len(shape):
    raise ValueError("einsum subscript rank does not match shape")
```

Build reverse equations with output cotangent first, followed by every other
forward operand in original order:

```python
parts = (output_subscript,) + tuple(
    subscript
    for index, subscript in enumerate(input_subscripts)
    if index != input_index
)
return ",".join(parts) + "->" + input_subscripts[input_index]
```

- [ ] **Step 5: Implement FLOP and intermediate accounting**

For each forward or reverse equation call:

```python
_, info = oe.contract_path(
    equation,
    *shapes,
    shapes=True,
    optimize="greedy",
)
```

Use `int(info.opt_cost)` and `int(info.largest_intermediate)`. Simulate the
active operand list using the same sequential `pop(position)` semantics as
the runtime executor.

Count each original input and each non-root forward output once in
`residual_elements`. A contraction tree consumes every active value once, so
the save-all peak at backward entry equals this sum.

- [ ] **Step 6: Run tests**

Run:

```bash
.venv/bin/pytest tests/test_ad_analysis.py -q
```

Expected: all tests pass.

- [ ] **Step 7: Commit**

```bash
git add src/vqetape/ad_analysis.py tests/test_ad_analysis.py
git commit -m "feat: analyze differentiated contraction costs"
```

---

### Task 2: Aggregate AD costs over spatial programs

**Files:**
- Modify: `src/vqetape/ad_analysis.py`
- Modify: `tests/test_ad_analysis.py`

**Interfaces:**

```python
@dataclass(frozen=True)
class SpatialDifferentiatedCost:
    first: DifferentiatedContractionCost
    bulk: DifferentiatedContractionCost | None
    tail: DifferentiatedContractionCost | None
    last: DifferentiatedContractionCost
    bulk_block_count: int
    dtype_bytes: int

    def _sum_metric(self, name: str) -> int:
        return (
            int(getattr(self.first, name))
            + self.bulk_block_count
            * (
                int(getattr(self.bulk, name))
                if self.bulk is not None
                else 0
            )
            + (
                int(getattr(self.tail, name))
                if self.tail is not None
                else 0
            )
            + int(getattr(self.last, name))
        )

    @property
    def peak_role_residual_elements(self) -> int:
        return max(
            item.peak_live_residual_elements
            for item in (
                self.first,
                self.bulk,
                self.tail,
                self.last,
            )
            if item is not None
        )

    @property
    def total_forward_flops(self) -> int:
        return self._sum_metric("forward_flops")

    @property
    def total_backward_flops(self) -> int:
        return self._sum_metric("backward_flops")

    @property
    def total_traffic_bytes(self) -> int:
        return self._sum_metric("traffic_elements") * self.dtype_bytes

    @property
    def static_score(self) -> int:
        return (
            self.total_forward_flops
            + self.total_backward_flops
            + 4 * self._sum_metric("traffic_elements")
            + 16 * self.peak_role_residual_elements
        )

    def to_dict(self) -> dict[str, object]:
        return {
            "total_forward_flops": self.total_forward_flops,
            "total_backward_flops": self.total_backward_flops,
            "total_traffic_bytes": self.total_traffic_bytes,
            "static_score": self.static_score,
        }


def analyze_spatial_transfer(
    transfer: SpatialTransferProgram,
) -> SpatialDifferentiatedCost:
    """Aggregate differentiated costs for all spatial program roles."""
```

- [ ] **Step 1: Write aggregate-scaling tests**

```python
def test_spatial_ad_cost_multiplies_repeated_blocks():
    one = analyze_spatial_transfer(
        plan_spatial_transfer(
            TFIMVQESpec(nqubits=8, depth=1),
            "greedy",
            block_width=1,
        )
    )
    two = analyze_spatial_transfer(
        plan_spatial_transfer(
            TFIMVQESpec(nqubits=8, depth=1),
            "greedy",
            block_width=2,
        )
    )
    assert one.bulk_block_count == 6
    assert two.bulk_block_count == 3
    assert one.total_forward_flops > 0
    assert one.total_backward_flops > 0
    assert one.total_traffic_bytes > 0
    assert one.static_score > 0
```

- [ ] **Step 2: Run and verify failure**

Run:

```bash
.venv/bin/pytest tests/test_ad_analysis.py -q
```

Expected: missing aggregate interface.

- [ ] **Step 3: Implement exact role aggregation**

For every metric \(m\), use:

```python
total = (
    getattr(first, metric)
    + bulk_block_count * (
        getattr(bulk, metric) if bulk is not None else 0
    )
    + (getattr(tail, metric) if tail is not None else 0)
    + getattr(last, metric)
)
```

Define the initial dimensionless static score:

```python
static_score = (
    total_forward_flops
    + total_backward_flops
    + 4 * total_traffic_elements
    + 16 * peak_role_residual_elements
)
```

This is a deterministic first model, not a calibrated runtime prediction.

- [ ] **Step 4: Run tests**

Run:

```bash
.venv/bin/pytest tests/test_ad_analysis.py -q
```

Expected: all pass.

- [ ] **Step 5: Commit**

```bash
git add src/vqetape/ad_analysis.py tests/test_ad_analysis.py
git commit -m "feat: score differentiated spatial programs"
```

---

### Task 3: Add the explicit spatial adjoint configuration

**Files:**
- Modify: `src/vqetape/spec.py`
- Modify: `tests/test_spec.py`

**Interfaces:**
- `SpatialAdjoint` becomes
  `Literal["default", "remat", "segmented", "explicit"]`.
- `SpatialProgramConfig("greedy", "explicit", block_width=2)` round-trips and
  labels distinctly.

- [ ] **Step 1: Add failing configuration tests**

```python
def test_explicit_spatial_adjoint_round_trip():
    config = SpatialProgramConfig(
        "greedy",
        "explicit",
        block_width=2,
        unroll=2,
    )
    assert SpatialProgramConfig.from_dict(config.to_dict()) == config
    assert "explicit" in config.label
```

Add `"explicit"` to the valid parametrized adjoint set.

- [ ] **Step 2: Run and verify failure**

Run:

```bash
.venv/bin/pytest tests/test_spec.py -q
```

Expected: unsupported adjoint.

- [ ] **Step 3: Extend the type and validation**

Update both the literal and `__post_init__` tuple. Keep
`segment_length is None` mandatory for explicit mode.

- [ ] **Step 4: Run tests**

Run:

```bash
.venv/bin/pytest tests/test_spec.py -q
```

Expected: all pass.

- [ ] **Step 5: Commit**

```bash
git add src/vqetape/spec.py tests/test_spec.py
git commit -m "feat: configure explicit spatial adjoints"
```

---

### Task 4: Execute explicit complex contraction VJPs

**Files:**
- Create: `src/vqetape/explicit_vjp.py`
- Create: `tests/test_explicit_vjp.py`

**Interfaces:**

```python
ExplicitContraction = Callable[..., Array]


def build_explicit_contraction_vjp(
    input_shapes: tuple[tuple[int, ...], ...],
    steps: tuple[ContractionStep, ...],
) -> ExplicitContraction:
    """Return a custom-VJP executor for the serialized contraction."""
```

The returned function takes one positional array per input shape and returns
the contraction output.

- [ ] **Step 1: Write value and VJP comparisons**

```python
@pytest.mark.parametrize(
    ("equation", "shapes"),
    [
        ("ab,bc->ac", ((2, 3), (3, 4))),
        ("ab,ab->", ((2, 3), (2, 3))),
    ],
)
def test_explicit_complex_vjp_matches_jax(equation, shapes):
    output_shape = (
        (2, 4)
        if equation == "ab,bc->ac"
        else ()
    )
    step = ContractionStep(
        positions=(0, 0),
        einsum=equation,
        output_subscript=equation.split("->", maxsplit=1)[1],
        output_elements=int(np.prod(output_shape)),
    )
    values = tuple(
        (
            jnp.arange(
                np.prod(shape),
                dtype=jnp.float32,
            ).reshape(shape)
            + 1j
            * jnp.linspace(
                0.1,
                0.9,
                np.prod(shape),
                dtype=jnp.float32,
            ).reshape(shape)
        )
        for shape in shapes
    )
    explicit = build_explicit_contraction_vjp(
        shapes,
        (step,),
    )
    reference = lambda *xs: jnp.einsum(
        equation,
        *xs,
        optimize=True,
    )
    output = explicit(*values)
    cotangent = jnp.full_like(output, 0.7 + 0.2j)
    actual_value, actual_pullback = jax.vjp(explicit, *values)
    expected_value, expected_pullback = jax.vjp(reference, *values)
    np.testing.assert_allclose(
        actual_value,
        expected_value,
        rtol=1e-5,
        atol=1e-5,
    )
    for actual, expected in zip(
        actual_pullback(cotangent),
        expected_pullback(cotangent),
        strict=True,
    ):
        np.testing.assert_allclose(
            actual,
            expected,
            rtol=1e-5,
            atol=1e-5,
        )
```

The concrete test implementation must construct values with:

```python
values = tuple(
    (
        jnp.arange(np.prod(shape), dtype=jnp.float32)
        .reshape(shape)
        + 1j
        * jnp.linspace(
            0.1,
            0.9,
            np.prod(shape),
            dtype=jnp.float32,
        ).reshape(shape)
    )
    for shape in shapes
)
```

Compare returned values and every cotangent against:

```python
reference = lambda *xs: jnp.einsum(
    equation,
    *xs,
    optimize=True,
)
```

with `rtol=1e-5, atol=1e-5`.

- [ ] **Step 2: Run and verify failure**

Run:

```bash
.venv/bin/pytest tests/test_explicit_vjp.py -q
```

Expected: missing module.

- [ ] **Step 3: Implement forward recomputation metadata**

Assign leaf IDs `0..len(inputs)-1`. For each step, sequentially pop
`(node_id, value, subscript)` tuples, execute the forward einsum, assign the
next node ID, and append:

```python
(
    output_node_id,
    selected_node_ids,
    input_subscripts,
    output_subscript,
    selected_values,
)
```

The ordinary function and custom forward rule both call the same helper. The
custom forward residual stores only the original input tuple.

- [ ] **Step 4: Implement reverse contractions**

Recompute the trace from saved leaves. Seed the root cotangent. Traverse
records in reverse. For input \(i\), execute:

```python
equation = reverse_einsum_equation(
    forward_equation,
    i,
)
reverse_inputs = (
    output_cotangent,
    *(
        jnp.conj(value)
        for index, value in enumerate(selected_values)
        if index != i
    ),
)
input_cotangent = jnp.einsum(
    equation,
    *reverse_inputs,
    optimize=True,
)
```

Return leaf cotangents in original input order.

- [ ] **Step 5: Run explicit VJP tests**

Run:

```bash
.venv/bin/pytest tests/test_explicit_vjp.py -q
```

Expected: all pass for matrix and scalar outputs with complex operands.

- [ ] **Step 6: Commit**

```bash
git add src/vqetape/explicit_vjp.py tests/test_explicit_vjp.py
git commit -m "feat: execute explicit contraction VJPs"
```

---

### Task 5: Integrate explicit VJPs into blocked spatial execution

**Files:**
- Modify: `src/vqetape/spatial_programs.py`
- Modify: `tests/test_spatial_programs.py`
- Modify: `tests/test_tape.py`

**Interfaces:**
- Consumes: `build_explicit_contraction_vjp`.
- Produces exact `SpatialProgramConfig(..., adjoint="explicit")` energy and
  complete gradients for first, bulk, tail, and last roles.

- [ ] **Step 1: Add complete-gradient tests**

```python
@pytest.mark.parametrize(
    ("nqubits", "block_width"),
    [(5, 1), (8, 2), (8, 3), (10, 4)],
)
def test_explicit_spatial_adjoint_matches_default(
    nqubits,
    block_width,
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
        SpatialProgramConfig(
            "greedy",
            "default",
            block_width=block_width,
        ),
    )
    explicit = build_spatial_energy(
        spec,
        SpatialProgramConfig(
            "greedy",
            "explicit",
            block_width=block_width,
        ),
    )
    expected = jax.value_and_grad(default)(theta)
    actual = jax.value_and_grad(explicit)(theta)
    np.testing.assert_allclose(actual[0], expected[0], atol=1e-5)
    np.testing.assert_allclose(
        actual[1],
        expected[1],
        rtol=1e-4,
        atol=1e-5,
    )
```

- [ ] **Step 2: Run and verify failure**

Run:

```bash
.venv/bin/pytest \
  tests/test_spatial_programs.py::test_explicit_spatial_adjoint_matches_default \
  -q
```

Expected: explicit mode follows no custom executor.

- [ ] **Step 3: Build one explicit executor per role**

Inside `build_spatial_energy`, create:

```python
explicit_first = build_explicit_contraction_vjp(
    transfer.first.input_shapes,
    transfer.first.steps,
)
```

and corresponding optional bulk/tail and last executors only when
`config.adjoint == "explicit"`.

Add an executor parameter to the local contraction helper. Its operand order
is exactly `(carry, *tensors)` when `carry_is_input`, otherwise `tensors`.

- [ ] **Step 4: Route every role through its explicit executor**

First, repeated block, tail, and last must all use the explicit executor.
Default, remat, and segmented code paths remain unchanged.

- [ ] **Step 5: Add a residual-profile comparison**

For `nqubits=12, depth=1, block_width=3`, compare explicit and default
profiles and assert:

```python
assert explicit_profile.total_bytes > 0
assert default_profile.total_bytes > 0
```

Do not require explicit to be lower until measured compiler/device evidence
supports that claim.

- [ ] **Step 6: Run focused tests**

Run:

```bash
.venv/bin/pytest \
  tests/test_spatial_programs.py \
  tests/test_tape.py \
  -q
```

Expected: all pass.

- [ ] **Step 7: Commit**

```bash
git add \
  src/vqetape/spatial_programs.py \
  tests/test_spatial_programs.py \
  tests/test_tape.py
git commit -m "feat: differentiate spatial blocks explicitly"
```

---

### Task 6: Rank and report AD-aware spatial candidates

**Files:**
- Modify: `src/vqetape/spatial_candidates.py`
- Modify: `src/vqetape/worker.py`
- Modify: `tests/test_spatial_candidates.py`
- Modify: `tests/test_benchmark.py`

**Interfaces:**

```python
@dataclass(frozen=True)
class RankedSpatialConfig:
    config: SpatialProgramConfig
    ad_cost: SpatialDifferentiatedCost


def rank_spatial_candidates_by_ad_cost(
    request: CompileRequest,
    candidates: tuple[SpatialProgramConfig, ...],
) -> tuple[RankedSpatialConfig, ...]:
    """Return every candidate sorted by deterministic differentiated cost."""
```

- [ ] **Step 1: Add deterministic ranking tests**

Build all greedy width-one and width-two default configs, rank twice, and
assert:

```python
assert first == second
assert {
    item.config for item in first
} == set(candidates)
assert all(item.ad_cost.static_score > 0 for item in first)
assert tuple(item.ad_cost.static_score for item in first) == tuple(
    sorted(item.ad_cost.static_score for item in first)
)
```

- [ ] **Step 2: Run and verify failure**

Run:

```bash
.venv/bin/pytest tests/test_spatial_candidates.py -q
```

Expected: missing ranking interface.

- [ ] **Step 3: Implement ranking with serialized paths**

Replan every config with:

```python
transfer = plan_spatial_transfer(
    request.spec,
    config.path_strategy,
    explicit_paths=config.column_paths,
    block_width=config.block_width,
)
```

Analyze it and sort by:

```python
(
    item.ad_cost.static_score,
    item.ad_cost.total_backward_flops,
    item.config.label,
)
```

- [ ] **Step 4: Enumerate explicit candidates without exploding the grid**

For each `(strategy, block_width)` add explicit configs only for `unroll=1`
and for the largest applicable unroll. Reuse the same serialized paths.
Segmented remains width one only.

- [ ] **Step 5: Report AD cost from fresh workers**

Add:

```python
"differentiated_cost": analyze_spatial_transfer(transfer).to_dict()
```

to `static_estimate`. The report must include total forward/backward FLOPs,
traffic bytes, residual elements, and the deterministic static score.

- [ ] **Step 6: Run candidate and worker tests**

Run:

```bash
.venv/bin/pytest \
  tests/test_spatial_candidates.py \
  tests/test_benchmark.py \
  -q
```

Expected: all pass.

- [ ] **Step 7: Commit**

```bash
git add \
  src/vqetape/spatial_candidates.py \
  src/vqetape/worker.py \
  tests/test_spatial_candidates.py \
  tests/test_benchmark.py
git commit -m "feat: rank spatial paths by differentiated cost"
```

---

### Task 7: Measure AD-aware and explicit programs

**Files:**
- Create: `outputs/vqetape-ad-aware-report-n8-d2.json`
- Create: `outputs/vqetape-ad-aware-report-n12-d2.json`
- Create: `outputs/vqetape-ad-aware-findings.md`
- Modify: `README.md`

**Interfaces:**
- Consumes: complete candidate search and static AD metrics.
- Produces: correctness, performance, residual, and rank-correlation evidence.

- [ ] **Step 1: Run the eight-qubit report**

```bash
.venv/bin/vqetape \
  --mode spatial-transfer \
  --nqubits 8 \
  --depth 2 \
  --memory-budget-gib 2 \
  --expected-steps 100 \
  --warm-repeats 5 \
  --timeout-seconds 300 \
  --output outputs/vqetape-ad-aware-report-n8-d2.json
```

- [ ] **Step 2: Run the twelve-qubit report**

```bash
.venv/bin/vqetape \
  --mode spatial-transfer \
  --nqubits 12 \
  --depth 2 \
  --memory-budget-gib 2 \
  --expected-steps 100 \
  --warm-repeats 5 \
  --timeout-seconds 300 \
  --output outputs/vqetape-ad-aware-report-n12-d2.json
```

- [ ] **Step 3: Analyze rank quality**

For valid spatial candidates calculate Spearman rank correlation between:

- forward FLOPs and warm runtime;
- total differentiated FLOPs and warm runtime;
- static AD score and warm runtime;
- residual elements and compiler temporary bytes.

The findings must report the actual coefficients and candidate counts; it
must not claim improvement if the AD score is no better than forward FLOPs.

- [ ] **Step 4: Compare explicit versus fixed-path controls**

For every explicit candidate, locate the default candidate with identical
strategy, block width, unroll, and serialized path. Report compile, warm,
compiler temporary, logical tape, energy error, and gradient error deltas.

- [ ] **Step 5: Write decision gates**

Promote explicit VJP only if it is valid and nondominated on measured compile,
warm, and compiler temporary memory. Retain AD analysis even after a negative
execution result if its static ranking improves holdout correlation.

- [ ] **Step 6: Update README and validate**

Run:

```bash
.venv/bin/python -m json.tool \
  outputs/vqetape-ad-aware-report-n8-d2.json >/dev/null
.venv/bin/python -m json.tool \
  outputs/vqetape-ad-aware-report-n12-d2.json >/dev/null
.venv/bin/pytest -q
git diff --check
```

- [ ] **Step 7: Commit**

```bash
git add \
  README.md \
  outputs/vqetape-ad-aware-report-n8-d2.json \
  outputs/vqetape-ad-aware-report-n12-d2.json \
  outputs/vqetape-ad-aware-findings.md
git commit -m "docs: report AD-aware VQETape results"
```

## Self-review

- Spec coverage: static reverse graph, cost aggregation, complex explicit
  VJP, spatial integration, deterministic ranking, fresh-worker metrics, and
  measured decision gates each have a task.
- Placeholder scan: all implementation steps define exact interfaces,
  equations, tests, commands, and expected outcomes.
- Type consistency: `DifferentiatedContractionCost` is the column-level
  record; `SpatialDifferentiatedCost` aggregates roles; worker reports the
  latter; `RankedSpatialConfig` carries the same type.
