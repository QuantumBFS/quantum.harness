# VQETape Blocked Spatial Transfer Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add exact multi-site spatial blocks, rolled blocked execution, and
fresh-process autotuning that can reduce the current spatial warm-runtime gap
without losing correctness or fixed-depth compile/memory scaling.

**Architecture:** Extend the spatial planner from one reusable bulk column to
one reusable width-\(b\) bulk block plus an optional shorter tail. Each block
contracts the incoming boundary together with all local tensors and emits only
the outgoing boundary. Runtime packs interior-site parameters into blocks,
scans the repeated full blocks, executes one tail if required, and reuses the
same serialized block paths across every AD policy.

**Tech Stack:** Python 3.12, JAX, NumPy, opt_einsum, pytest, fresh-process
benchmark workers.

## Global Constraints

- Preserve exact open-boundary TFIM energy and complete-gradient semantics.
- Never materialize a full \(D\times D\) transfer tensor.
- Preserve old report/config deserialization with implicit `block_width=1`.
- Search a path once per `(path_strategy, block_width)` and reuse it across
  default, remat, unroll, and segmented schedules.
- Use fresh subprocesses for measured candidates.
- Keep GPU claims out of this CPU phase.

---

### Task 1: Serialize the block-width configuration axis

**Files:**
- Modify: `src/vqetape/spec.py`
- Modify: `tests/test_spec.py`

**Interfaces:**
- Consumes: existing `SpatialProgramConfig`.
- Produces: `SpatialProgramConfig.block_width: int` with default `1`; labels
  contain `-b{block_width}-`; old dictionaries without the field deserialize
  as width one.

- [ ] **Step 1: Write failing validation and round-trip tests**

Add:

```python
def test_spatial_config_round_trips_block_width():
    config = SpatialProgramConfig(
        "greedy",
        "remat",
        unroll=2,
        block_width=3,
    )
    assert SpatialProgramConfig.from_dict(config.to_dict()) == config
    assert "-b3-" in config.label


def test_spatial_config_rejects_nonpositive_block_width():
    with pytest.raises(ValueError, match="block_width"):
        SpatialProgramConfig(
            "greedy",
            "default",
            block_width=0,
        )


def test_old_spatial_config_defaults_to_width_one():
    payload = {
        "path_strategy": "greedy",
        "adjoint": "default",
        "unroll": 1,
        "segment_length": None,
        "column_paths": None,
        "representation": "spatial_transfer",
    }
    assert SpatialProgramConfig.from_dict(payload).block_width == 1
```

- [ ] **Step 2: Run the focused tests and verify failure**

Run:

```bash
pytest tests/test_spec.py -q
```

Expected: failures because `block_width` is not accepted or serialized.

- [ ] **Step 3: Add and validate `block_width`**

Add after `unroll`:

```python
block_width: int = 1
```

In `__post_init__` add:

```python
if self.block_width < 1:
    raise ValueError("block_width must be positive")
```

Change the label base to:

```python
base = (
    f"spatial-transfer-{self.path_strategy}-"
    f"b{self.block_width}-{self.adjoint}-u{self.unroll}"
)
```

Allow `column_paths` lengths from two through four:

```python
if len(self.column_paths) not in (2, 3, 4):
    raise ValueError(
        "column paths must contain first/last, "
        "first/block/last, or first/block/tail/last paths"
    )
```

- [ ] **Step 4: Run focused tests**

Run:

```bash
pytest tests/test_spec.py -q
```

Expected: all tests pass.

- [ ] **Step 5: Commit**

```bash
git add src/vqetape/spec.py tests/test_spec.py
git commit -m "feat: add spatial block-width configuration"
```

---

### Task 2: Plan exact multi-site spatial blocks

**Files:**
- Modify: `src/vqetape/spatial_plan.py`
- Modify: `tests/test_spatial_plan.py`

**Interfaces:**
- Consumes: `TFIMVQESpec`, `PathStrategy`, optional serialized paths, and
  `block_width`.
- Produces:

```python
ColumnRole = Literal["first", "bulk", "tail", "last"]

@dataclass(frozen=True)
class SpatialColumnSlot:
    kind: SlotKind
    layer: int | None
    site_offset: int
    shape: tuple[int, ...]

@dataclass(frozen=True)
class SpatialColumnProgram:
    ...
    width: int

@dataclass(frozen=True)
class SpatialTransferProgram:
    ...
    bulk: SpatialColumnProgram | None
    tail: SpatialColumnProgram | None
    block_width: int
    bulk_block_count: int
    tail_width: int
```

- [ ] **Step 1: Write failing planner tests**

Add:

```python
@pytest.mark.parametrize(
    ("nqubits", "block_width", "full_blocks", "tail_width"),
    [
        (8, 1, 6, 0),
        (8, 2, 3, 0),
        (8, 4, 1, 2),
        (5, 3, 1, 0),
        (4, 3, 0, 2),
    ],
)
def test_blocked_spatial_plan_partitions_interior(
    nqubits,
    block_width,
    full_blocks,
    tail_width,
):
    program = plan_spatial_transfer(
        TFIMVQESpec(nqubits=nqubits, depth=1),
        "greedy",
        block_width=block_width,
    )
    assert program.block_width == block_width
    assert program.bulk_block_count == full_blocks
    assert program.tail_width == tail_width
    assert (program.bulk.width if program.bulk else 0) == (
        block_width if full_blocks else 0
    )
    assert (program.tail.width if program.tail else 0) == tail_width


def test_block_program_keeps_only_external_boundary():
    program = plan_spatial_transfer(
        TFIMVQESpec(nqubits=8, depth=2),
        "greedy",
        block_width=3,
    )
    assert program.bulk is not None
    assert program.bulk.left_boundary_shape == program.boundary_shape
    assert program.bulk.right_boundary_shape == program.boundary_shape
    assert program.bulk.output_elements == program.boundary_dimension
    assert all(
        step.output_elements < program.boundary_dimension**2
        for step in program.bulk.steps
    )


def test_block_slots_record_site_offsets():
    program = plan_spatial_transfer(
        TFIMVQESpec(nqubits=6, depth=1),
        "greedy",
        block_width=2,
    )
    assert program.bulk is not None
    assert {slot.site_offset for slot in program.bulk.slots} == {0, 1}
```

- [ ] **Step 2: Run the planner tests and verify failure**

Run:

```bash
pytest tests/test_spatial_plan.py -q
```

Expected: failures for missing block planning fields and argument.

- [ ] **Step 3: Extend planner records**

Add `tail`, `width`, `site_offset`, `block_width`, `bulk_block_count`, and
`tail_width` exactly as declared in the Interfaces block. Preserve `bulk=None`
for no repeated full block and `tail=None` for no remainder.

- [ ] **Step 4: Generalize `_plan_column` to a site range**

Change its local input to:

```python
local_slots: tuple[tuple[TensorSlot, int], ...]
```

where the integer is the offset from the first site of the block. Build
`SpatialColumnSlot` with:

```python
SpatialColumnSlot(
    slot.kind,
    slot.layer,
    site_offset,
    slot.shape,
)
```

Include `site_offset` in the canonical signature so a path cannot be reused
against a different blocked topology.

- [ ] **Step 5: Partition first, repeated block, tail, and last**

Use:

```python
interior_count = spec.nqubits - 2
bulk_block_count, tail_width = divmod(
    interior_count,
    block_width,
)
```

Plan ranges:

```python
first = [0, 1)
bulk = [1, 1 + block_width) if bulk_block_count else None
tail_start = 1 + bulk_block_count * block_width
tail = [tail_start, tail_start + tail_width) if tail_width else None
last = [nqubits - 1, nqubits)
```

The left boundary is cut `start - 1`; the right boundary is cut `stop - 1`
unless `stop == nqubits`. The expected serialized role order is
`first`, optional `bulk`, optional `tail`, `last`.

- [ ] **Step 6: Validate repeated block topology without rerunning stochastic search**

For every later full block, rebuild its canonical operand/output pattern and
compare it with the representative block signature. Reject a mismatch with:

```python
raise ValueError("bulk block topology is not canonical")
```

- [ ] **Step 7: Run planner tests**

Run:

```bash
pytest tests/test_spatial_plan.py -q
```

Expected: all tests pass, including all pre-existing one-site tests.

- [ ] **Step 8: Commit**

```bash
git add src/vqetape/spatial_plan.py tests/test_spatial_plan.py
git commit -m "feat: plan exact multi-site spatial blocks"
```

---

### Task 3: Execute blocked scans and tails exactly

**Files:**
- Modify: `src/vqetape/spatial_programs.py`
- Modify: `tests/test_spatial_programs.py`

**Interfaces:**
- Consumes: `SpatialTransferProgram` from Task 2 and packed site parameters
  with shape `(interior_count, 3, depth)`.
- Produces:

```python
def bind_spatial_block(
    program: SpatialColumnProgram,
    packed_sites: Array,
    spec: TFIMVQESpec,
) -> tuple[Array, ...]

def _bulk_block_transition(
    carry: Array,
    packed_block: Array,
    *,
    spec: TFIMVQESpec,
    program: SpatialColumnProgram,
) -> Array
```

- [ ] **Step 1: Write failing energy/gradient and tail tests**

Add:

```python
@pytest.mark.parametrize("nqubits", [4, 5, 6, 8])
@pytest.mark.parametrize("block_width", [1, 2, 3, 4])
@pytest.mark.parametrize("adjoint", ["default", "remat"])
def test_blocked_spatial_gradient_matches_width_one(
    nqubits,
    block_width,
    adjoint,
):
    if block_width > nqubits - 2:
        pytest.skip("block wider than interior")
    spec = TFIMVQESpec(nqubits=nqubits, depth=1)
    theta = jnp.linspace(
        -0.2,
        0.2,
        np.prod(spec.parameter_shape),
        dtype=jnp.float32,
    ).reshape(spec.parameter_shape)
    reference = build_spatial_energy(
        spec,
        SpatialProgramConfig(
            "greedy",
            "default",
            block_width=1,
        ),
    )
    blocked = build_spatial_energy(
        spec,
        SpatialProgramConfig(
            "greedy",
            adjoint,
            block_width=block_width,
        ),
    )
    expected = jax.value_and_grad(reference)(theta)
    actual = jax.value_and_grad(blocked)(theta)
    np.testing.assert_allclose(actual[0], expected[0], atol=1e-5)
    np.testing.assert_allclose(
        actual[1],
        expected[1],
        rtol=1e-4,
        atol=1e-5,
    )


def test_blocked_spatial_tail_is_differentiated():
    spec = TFIMVQESpec(nqubits=8, depth=1)
    theta = jnp.linspace(
        -0.3,
        0.3,
        np.prod(spec.parameter_shape),
        dtype=jnp.float32,
    ).reshape(spec.parameter_shape)
    one = build_spatial_energy(
        spec,
        SpatialProgramConfig("greedy", "default", block_width=1),
    )
    four = build_spatial_energy(
        spec,
        SpatialProgramConfig("greedy", "default", block_width=4),
    )
    np.testing.assert_allclose(
        jax.value_and_grad(four)(theta)[1],
        jax.value_and_grad(one)(theta)[1],
        rtol=1e-4,
        atol=1e-5,
    )
```

- [ ] **Step 2: Run focused runtime tests and verify failure**

Run:

```bash
pytest tests/test_spatial_programs.py -q
```

Expected: failures because `block_width` is ignored by planning/runtime.

- [ ] **Step 3: Implement `bind_spatial_block`**

Validate:

```python
expected = (program.width, 3, spec.depth)
if tuple(packed_sites.shape) != expected:
    raise ValueError(
        f"packed block shape must be {expected}, "
        f"got {tuple(packed_sites.shape)}"
    )
```

For every slot, construct:

```python
site_values = packed_sites[slot.site_offset]
parameters = SpatialSiteParameters(
    left_rzz=site_values[0],
    right_rzz=site_values[1],
    rx=site_values[2],
)
```

Then apply the existing tensor binding rules using that site's parameters.
Retain `bind_spatial_column` as a width-one compatibility wrapper.

- [ ] **Step 4: Pack and scan full blocks**

Compute:

```python
packed_bulk = _bulk_parameters(theta)
full_site_count = (
    transfer.bulk_block_count * transfer.block_width
)
full_blocks = packed_bulk[:full_site_count].reshape(
    transfer.bulk_block_count,
    transfer.block_width,
    3,
    spec.depth,
)
tail_sites = packed_bulk[full_site_count:]
```

Scan `full_blocks` when `bulk_block_count > 0`. Wrap the whole block
transition in `jax.checkpoint` for remat. Execute `transfer.tail` once after
the scan when present.

- [ ] **Step 5: Preserve rolled control flow**

Add:

```python
def test_blocked_spatial_scan_lowers_to_while():
    spec = TFIMVQESpec(nqubits=10, depth=1)
    theta = jnp.zeros(spec.parameter_shape, dtype=jnp.float32)
    executable = build_spatial_value_and_grad(
        spec,
        SpatialProgramConfig(
            "greedy",
            "default",
            block_width=2,
            unroll=1,
        ),
    )
    assert "while" in executable.lower(theta).as_text().lower()
```

- [ ] **Step 6: Run runtime tests**

Run:

```bash
pytest tests/test_spatial_programs.py -q
```

Expected: all spatial runtime tests pass.

- [ ] **Step 7: Commit**

```bash
git add src/vqetape/spatial_programs.py tests/test_spatial_programs.py
git commit -m "feat: execute exact blocked spatial VQE scans"
```

---

### Task 4: Generalize segmented checkpoint accounting to block units

**Files:**
- Modify: `src/vqetape/spatial_programs.py`
- Modify: `tests/test_spatial_programs.py`

**Interfaces:**
- Consumes: packed full blocks from Task 3.
- Produces: segmented custom VJP over full block units; tail remains one
  ordinary differentiable transition.

- [ ] **Step 1: Write failing blocked segmented tests**

Add:

```python
@pytest.mark.parametrize(
    ("nqubits", "block_width", "segment_length"),
    [(10, 2, 2), (14, 3, 2), (15, 4, 2)],
)
def test_blocked_segmented_matches_blocked_default(
    nqubits,
    block_width,
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
        SpatialProgramConfig(
            "greedy",
            "default",
            block_width=block_width,
        ),
    )
    segmented = build_spatial_energy(
        spec,
        SpatialProgramConfig(
            "greedy",
            "segmented",
            block_width=block_width,
            segment_length=segment_length,
        ),
    )
    expected = jax.value_and_grad(default)(theta)
    actual = jax.value_and_grad(segmented)(theta)
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
pytest tests/test_spatial_programs.py -q
```

Expected: segmented builder expects site-shaped units.

- [ ] **Step 3: Parameterize `_build_segmented_bulk` by full block count**

Use:

```python
unit_count = transfer.bulk_block_count
unit_width = transfer.block_width
expected = (unit_count, unit_width, 3, spec.depth)
```

Pad only the leading unit axis. `run_segment` applies
`_bulk_block_transition`. Tail parameters are not included in the segmented
custom VJP and are executed after its result.

- [ ] **Step 4: Update checkpoint count**

Use:

```python
unit_count = (spec.nqubits - 2) // config.block_width
if config.adjoint == "segmented":
    return (
        ceil(unit_count / config.segment_length)
        + config.segment_length
    )
return unit_count
```

When `unit_count == 0`, reject segmented execution with the existing
bulk-required error.

- [ ] **Step 5: Run spatial runtime tests**

Run:

```bash
pytest tests/test_spatial_programs.py -q
```

Expected: all pass.

- [ ] **Step 6: Commit**

```bash
git add src/vqetape/spatial_programs.py tests/test_spatial_programs.py
git commit -m "feat: checkpoint blocked spatial recurrences"
```

---

### Task 5: Search block width, unroll, and AD policy fairly

**Files:**
- Modify: `src/vqetape/spatial_candidates.py`
- Modify: `tests/test_spatial_candidates.py`

**Interfaces:**
- Consumes: block-aware planner/configuration.
- Produces: deterministic candidates over widths
  `1..min(4, interior_count)` and unroll values from `{1,2,4}` capped by the
  number of full blocks.

- [ ] **Step 1: Replace the candidate-axis test**

Assert:

```python
assert {item.block_width for item in candidates} == {1, 2, 3, 4}
for strategy in {"greedy", "random-greedy", "auto-hq"}:
    for block_width in {1, 2, 3, 4}:
        matching = [
            item
            for item in candidates
            if item.path_strategy == strategy
            and item.block_width == block_width
        ]
        assert len({item.column_paths for item in matching}) == 1
```

For every non-segmented candidate verify:

```python
full_blocks = (request.spec.nqubits - 2) // item.block_width
assert item.unroll in {
    min(value, full_blocks)
    for value in (1, 2, 4)
    if full_blocks
}
```

Segmented candidates remain width one in the default search because the
current measured phase found them dominated; explicit blocked segmented
configs remain supported by Task 4.

- [ ] **Step 2: Run and verify failure**

Run:

```bash
pytest tests/test_spatial_candidates.py -q
```

Expected: current enumeration only yields width one and unroll one/two.

- [ ] **Step 3: Enumerate block-aware candidates**

For each strategy and width:

```python
transfer = plan_spatial_transfer(
    request.spec,
    strategy,
    block_width=block_width,
)
column_paths = tuple(
    program.path
    for program in (
        transfer.first,
        transfer.bulk,
        transfer.tail,
        transfer.last,
    )
    if program is not None
)
```

If there are no full blocks, emit one default candidate with unroll one.
Otherwise emit default/remat for unique capped values from `{1,2,4}`.
Emit the existing segmented width-one candidate with
`round(sqrt(full_blocks))`.

- [ ] **Step 4: Replan every stored path in the fairness test**

Call:

```python
planned = plan_spatial_transfer(
    request.spec,
    item.path_strategy,
    explicit_paths=item.column_paths,
    block_width=item.block_width,
)
```

Compare first, optional bulk, optional tail, and last FLOP tuples for all AD
policies that share a strategy and width.

- [ ] **Step 5: Run candidate tests**

Run:

```bash
pytest tests/test_spatial_candidates.py -q
```

Expected: all pass.

- [ ] **Step 6: Commit**

```bash
git add src/vqetape/spatial_candidates.py tests/test_spatial_candidates.py
git commit -m "feat: autotune blocked spatial VQE programs"
```

---

### Task 6: Report blocked static and executable metrics

**Files:**
- Modify: `src/vqetape/worker.py`
- Modify: `tests/test_benchmark.py`

**Interfaces:**
- Consumes: block-aware fresh-worker configuration.
- Produces static report keys:

```text
block_width
bulk_blocks
tail_width
bulk_block_path_flops
tail_path_flops
estimated_energy_flops
```

- [ ] **Step 1: Extend the spatial benchmark test**

For a width-two candidate assert:

```python
assert result.static_estimate["block_width"] == 2
assert result.static_estimate["bulk_blocks"] == 2
assert result.static_estimate["tail_width"] == 0
assert result.static_estimate["bulk_block_path_flops"] > 0
assert result.static_estimate["estimated_energy_flops"] > 0
```

Use `nqubits=6`, `depth=1`, `warm_repeats=1`.

- [ ] **Step 2: Run and verify failure**

Run:

```bash
pytest tests/test_benchmark.py -q
```

Expected: missing report keys or planner receives no block width.

- [ ] **Step 3: Pass `block_width` through the worker**

Plan with:

```python
transfer = plan_spatial_transfer(
    spec,
    config.path_strategy,
    explicit_paths=config.column_paths,
    block_width=config.block_width,
)
```

Calculate:

```python
bulk_flops = transfer.bulk.flops if transfer.bulk else 0
tail_flops = transfer.tail.flops if transfer.tail else 0
estimated_energy_flops = (
    transfer.first.flops
    + transfer.bulk_block_count * bulk_flops
    + tail_flops
    + transfer.last.flops
)
```

Retain the old `bulk_path_flops` and `bulk_columns` fields for report
compatibility; add the new unambiguous block fields.

- [ ] **Step 4: Run benchmark tests**

Run:

```bash
pytest tests/test_benchmark.py -q
```

Expected: all pass.

- [ ] **Step 5: Run the complete regression suite**

Run:

```bash
pytest -q
```

Expected: all existing and new tests pass.

- [ ] **Step 6: Commit**

```bash
git add src/vqetape/worker.py tests/test_benchmark.py
git commit -m "test: report blocked spatial VQE metrics"
```

---

### Task 7: Produce decision-gate evidence

**Files:**
- Modify: `README.md`
- Create: `outputs/vqetape-blocked-spatial-report-n8-d2.json`
- Create: `outputs/vqetape-blocked-spatial-report-n12-d2.json`
- Create: `outputs/vqetape-blocked-spatial-findings.md`

**Interfaces:**
- Consumes: complete blocked candidate search.
- Produces: reproducible reports and an explicit promote/reject decision.

- [ ] **Step 1: Run the eight-qubit fresh-process benchmark**

Run:

```bash
vqetape \
  --mode spatial-transfer \
  --nqubits 8 \
  --depth 2 \
  --memory-budget-gib 2 \
  --expected-steps 100 \
  --warm-repeats 5 \
  --timeout-seconds 300 \
  --output outputs/vqetape-blocked-spatial-report-n8-d2.json
```

Expected: every valid candidate includes `block_width`; at least widths one
through four are represented.

- [ ] **Step 2: Run the twelve-qubit benchmark**

Run:

```bash
vqetape \
  --mode spatial-transfer \
  --nqubits 12 \
  --depth 2 \
  --memory-budget-gib 2 \
  --expected-steps 100 \
  --warm-repeats 5 \
  --timeout-seconds 300 \
  --output outputs/vqetape-blocked-spatial-report-n12-d2.json
```

Expected: a complete fresh-process report or explicit per-candidate failure
reasons.

- [ ] **Step 3: Write findings from measured JSON**

The findings document must include:

- the exact workload contract;
- candidate counts and correctness errors;
- selected candidate versus the best global-MPO control;
- best spatial warm/compile/compiler-temp values by block width;
- fixed-path comparisons where available;
- whether warm improved by at least 20% from 594.33 microseconds at
  \(n=12,L=2\);
- whether compile or temporary memory still beats global MPO;
- a promote/reject decision for blocked execution;
- limitations and CPU-only wording.

- [ ] **Step 4: Update README**

Document `block_width`, optional tail execution, and the expanded autotuning
axes. Link the blocked findings after the previous spatial findings.

- [ ] **Step 5: Validate JSON and full tests**

Run:

```bash
python -m json.tool \
  outputs/vqetape-blocked-spatial-report-n8-d2.json >/dev/null
python -m json.tool \
  outputs/vqetape-blocked-spatial-report-n12-d2.json >/dev/null
pytest -q
git diff --check
```

Expected: JSON parses, all tests pass, and no whitespace errors remain.

- [ ] **Step 6: Commit**

```bash
git add \
  README.md \
  outputs/vqetape-blocked-spatial-report-n8-d2.json \
  outputs/vqetape-blocked-spatial-report-n12-d2.json \
  outputs/vqetape-blocked-spatial-findings.md
git commit -m "docs: report blocked spatial VQETape results"
```

## Self-review

- Spec coverage: configuration, planning, execution, tails, AD policies,
  candidate fairness, fresh-worker reporting, correctness, performance, and
  documentation each have a task.
- Placeholder scan: every implementation and verification action names exact
  files, interfaces, commands, and expected results.
- Type consistency: `block_width` is carried by `SpatialProgramConfig`;
  `SpatialTransferProgram` exposes `bulk_block_count` and `tail_width`;
  runtime and worker use those exact names.
