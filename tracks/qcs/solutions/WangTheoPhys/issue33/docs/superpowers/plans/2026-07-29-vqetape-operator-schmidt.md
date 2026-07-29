# VQETape Operator-Schmidt Representation Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add an exact operator-Schmidt RZZ lowering and jointly search tensor representation, contraction path, and reverse-mode tape for TFIM VQE value-and-full-gradient programs.

**Architecture:** `TensorProgramConfig` selects either the existing dense rank-4 RZZ tensor or two rank-3 operator-Schmidt factors joined by a dimension-2 bond. Both representations flow through the same template binding, explicit path planning, named residual profiling, fresh-process benchmarking, correctness oracle, and Pareto selection pipeline.

**Tech Stack:** Python 3.12, JAX 0.11, NumPy 2.x, opt_einsum 3.4, pytest 9

## Global Constraints

- Every representation computes exact energy and the complete padded gradient.
- Dense and operator-Schmidt comparisons use identical VQE semantics, seeds, path strategies, path-search budgets, and fresh-process measurement.
- Tape policies for one representation/path pair reuse one serialized explicit path.
- The Schmidt bond dimension is exactly 2.
- The asymmetric factors use no complex square roots.
- Compiler memory, logical residual bytes, and process RSS remain separate metrics.
- No Hamiltonian MPO, shared Pauli environments, slicing, mixed precision, truncation, ansatz search, or classical optimizer is introduced in this phase.
- Existing dense behavior and serialized reports remain backward-compatible by defaulting to `dense`.

---

### Task 1: Representation Configuration

**Files:**
- Modify: `src/vqetape/spec.py`
- Modify: `tests/test_spec.py`

**Interfaces:**
- Consumes: existing `TensorProgramConfig`
- Produces: `GateRepresentation = Literal["dense", "operator_schmidt"]` and `TensorProgramConfig.gate_representation`

- [x] **Step 1: Write failing configuration tests**

```python
def test_tensor_program_representation_round_trip():
    config = TensorProgramConfig(
        "greedy",
        "none",
        gate_representation="operator_schmidt",
    )
    assert TensorProgramConfig.from_dict(config.to_dict()) == config
    assert "operator-schmidt" in config.label


def test_tensor_program_rejects_unknown_representation():
    with pytest.raises(ValueError, match="gate_representation"):
        TensorProgramConfig(
            "greedy",
            "none",
            gate_representation="sparse",
        )
```

- [x] **Step 2: Run the tests and verify failure**

Run:

```bash
.venv/bin/pytest -q tests/test_spec.py
```

Expected: failure because `gate_representation` is not accepted.

- [x] **Step 3: Add the validated field**

```python
GateRepresentation = Literal["dense", "operator_schmidt"]


@dataclass(frozen=True)
class TensorProgramConfig:
    path_strategy: Literal["greedy", "random-greedy", "auto-hq"]
    remat_policy: Literal[
        "none",
        "all",
        "output-ge-threshold",
        "term",
        "objective",
        "subtree",
        "named",
    ]
    threshold_bytes: int | None = None
    path: tuple[tuple[int, ...], ...] | None = None
    subtree_depth: int | None = None
    save_names: tuple[str, ...] | None = None
    gate_representation: GateRepresentation = "dense"
    representation: Literal["direct_tn"] = "direct_tn"
```

Validate membership in `("dense", "operator_schmidt")`. Add
`dense` or `operator-schmidt` to `label` before the path strategy so that
labels remain unique across representations.

- [x] **Step 4: Run configuration tests**

Run:

```bash
.venv/bin/pytest -q tests/test_spec.py
```

Expected: all pass.

- [x] **Step 5: Commit**

```bash
git add src/vqetape/spec.py tests/test_spec.py
git commit -m "feat: configure RZZ tensor representations"
```

---

### Task 2: Exact Operator-Schmidt RZZ Factors

**Files:**
- Modify: `src/vqetape/kernels.py`
- Modify: `tests/test_kernels.py`

**Interfaces:**
- Consumes: `angle: Array`, JAX complex dtype
- Produces: `rzz_schmidt_factors(angle, dtype) -> tuple[Array, Array]`

- [x] **Step 1: Write algebraic reconstruction tests**

```python
@pytest.mark.parametrize("angle", [0.0, 1e-6, -0.7, np.pi - 1e-5])
def test_rzz_schmidt_factors_reconstruct_dense_gate(angle):
    left, right = rzz_schmidt_factors(
        jnp.asarray(angle, dtype=jnp.float32),
        jnp.complex64,
    )
    reconstructed = jnp.einsum("oia,pja->opij", left, right)
    expected = rzz_matrix(
        jnp.asarray(angle, dtype=jnp.float32),
        jnp.complex64,
    ).reshape(2, 2, 2, 2)
    np.testing.assert_allclose(
        np.asarray(reconstructed),
        np.asarray(expected),
        rtol=1e-6,
        atol=1e-6,
    )
    assert left.shape == (2, 2, 2)
    assert right.shape == (2, 2, 2)
```

Add a local `with jax.enable_x64():` test for `complex128`.

- [x] **Step 2: Verify the tests fail**

Run:

```bash
.venv/bin/pytest -q tests/test_kernels.py -k schmidt
```

Expected: import failure for `rzz_schmidt_factors`.

- [x] **Step 3: Implement the asymmetric factors**

```python
def rzz_schmidt_factors(angle: Array, dtype) -> tuple[Array, Array]:
    half = angle / 2
    identity = jnp.eye(2, dtype=dtype)
    pauli_z = jnp.asarray([[1, 0], [0, -1]], dtype=dtype)
    left = jnp.stack(
        (
            jnp.cos(half) * identity,
            (-1j * jnp.sin(half)) * pauli_z,
        ),
        axis=-1,
    )
    right = jnp.stack((identity, pauli_z), axis=-1)
    return left, right
```

- [x] **Step 4: Run kernel tests**

Run:

```bash
.venv/bin/pytest -q tests/test_kernels.py
```

Expected: all pass.

- [x] **Step 5: Commit**

```bash
git add src/vqetape/kernels.py tests/test_kernels.py
git commit -m "feat: factor RZZ gates by operator Schmidt rank"
```

---

### Task 3: Representation-Aware Tensor Templates

**Files:**
- Modify: `src/vqetape/tn_template.py`
- Modify: `tests/test_tn_template.py`

**Interfaces:**
- Consumes: `build_expectation_template(spec, gate_representation=...)`
- Produces: dense slots or paired `ket_rzz_left`, `ket_rzz_right`,
  `bra_rzz_left`, `bra_rzz_right` slots

- [x] **Step 1: Write topology tests**

```python
def test_operator_schmidt_template_has_rank_three_factor_slots():
    spec = TFIMVQESpec(nqubits=3, depth=2)
    template = build_expectation_template(
        spec,
        gate_representation="operator_schmidt",
    )
    left = [slot for slot in template.slots if slot.kind == "ket_rzz_left"]
    right = [slot for slot in template.slots if slot.kind == "ket_rzz_right"]
    expected_gate_count = spec.depth * (spec.nqubits - 1)
    assert len(left) == expected_gate_count
    assert len(right) == expected_gate_count
    assert all(slot.shape == (2, 2, 2) for slot in left + right)
    assert all(
        extent == 2
        for slot in left + right
        for extent in slot.shape
    )


def test_dense_template_remains_default():
    spec = TFIMVQESpec(nqubits=3, depth=1)
    implicit = build_expectation_template(spec)
    explicit = build_expectation_template(spec, gate_representation="dense")
    assert implicit == explicit
```

- [x] **Step 2: Run the tests and verify failure**

Run:

```bash
.venv/bin/pytest -q tests/test_tn_template.py
```

Expected: failure because the builder lacks the new keyword and slot kinds.

- [x] **Step 3: Extend slot kinds and circuit construction**

Extend `SlotKind` with the four factor kinds. Change `_append_circuit` to accept
`gate_representation`. For each Schmidt RZZ gate:

```python
schmidt = allocator.take()
output0 = allocator.take()
output1 = allocator.take()
slots.append(
    TensorSlot(
        kind=left_kind,
        indices=(output0, frontier[wire], schmidt),
        shape=(2, 2, 2),
        layer=layer,
        wire=wire,
    )
)
slots.append(
    TensorSlot(
        kind=right_kind,
        indices=(output1, frontier[wire + 1], schmidt),
        shape=(2, 2, 2),
        layer=layer,
        wire=wire,
    )
)
```

Dense construction remains unchanged.

- [x] **Step 4: Run template tests**

Run:

```bash
.venv/bin/pytest -q tests/test_tn_template.py
```

Expected: all pass, including the closed-network invariant.

- [x] **Step 5: Commit**

```bash
git add src/vqetape/tn_template.py tests/test_tn_template.py
git commit -m "feat: build operator-Schmidt VQE networks"
```

---

### Task 4: Bind Dense and Schmidt Gate Tensors

**Files:**
- Modify: `src/vqetape/tn_template.py`
- Modify: `tests/test_tn_template.py`

**Interfaces:**
- Consumes: a representation-aware `TensorNetworkTemplate`
- Produces: `bind_term_tensors` values matching every slot shape

- [x] **Step 1: Write dense-versus-Schmidt contraction tests**

```python
@pytest.mark.parametrize("operators", [("Z", "Z", "I"), ("I", "X", "I")])
def test_dense_and_schmidt_term_contractions_match(operators):
    spec = TFIMVQESpec(nqubits=3, depth=2)
    theta = jnp.linspace(-0.2, 0.3, np.prod(spec.parameter_shape)).reshape(
        spec.parameter_shape
    )
    term = ProductPauliTerm(-1.0, operators)
    values = []
    for representation in ("dense", "operator_schmidt"):
        template = build_expectation_template(
            spec,
            gate_representation=representation,
        )
        tensors = bind_term_tensors(template, theta, term)
        assert tuple(tensor.shape for tensor in tensors) == template.shapes
        values.append(
            oe.contract(
                template.equation,
                *tensors,
                optimize="greedy",
                backend="jax",
            )
        )
    np.testing.assert_allclose(
        np.asarray(values[0]),
        np.asarray(values[1]),
        rtol=1e-5,
        atol=1e-5,
    )
```

- [x] **Step 2: Verify failure**

Run:

```bash
.venv/bin/pytest -q tests/test_tn_template.py -k schmidt
```

Expected: failure because factor slots are not bound.

- [x] **Step 3: Bind factor tensors**

Call `rzz_schmidt_factors` once per slot's layer and wire. Select `left` or
`right`, and conjugate the selected factor for bra slots:

```python
left, right = rzz_schmidt_factors(
    theta[slot.layer, 0, slot.wire],
    dtype,
)
tensor = left if slot.kind.endswith("_left") else right
if slot.kind.startswith("bra_"):
    tensor = jnp.conj(tensor)
```

Keep residual names representation-specific through the existing slot-kind
component of the name.

- [x] **Step 4: Run template and kernel tests**

Run:

```bash
.venv/bin/pytest -q tests/test_kernels.py tests/test_tn_template.py
```

Expected: all pass.

- [x] **Step 5: Commit**

```bash
git add src/vqetape/tn_template.py tests/test_tn_template.py
git commit -m "feat: bind operator-Schmidt VQE tensors"
```

---

### Task 5: Representation Metrics and Path Isolation

**Files:**
- Modify: `src/vqetape/tn_program.py`
- Modify: `tests/test_tn_program.py`

**Interfaces:**
- Consumes: any representation-aware `TensorNetworkTemplate`
- Produces: `ContractionProgram.input_tensor_elements`,
  `ContractionProgram.tensor_count`, and topology-bound explicit paths

- [x] **Step 1: Write metric and cross-topology rejection tests**

```python
def test_contraction_program_reports_representation_size():
    spec = TFIMVQESpec(nqubits=3, depth=2)
    dense = plan_contraction(
        build_expectation_template(spec, gate_representation="dense"),
        "greedy",
    )
    schmidt = plan_contraction(
        build_expectation_template(
            spec,
            gate_representation="operator_schmidt",
        ),
        "greedy",
    )
    assert dense.tensor_count == len(dense.template.slots)
    assert schmidt.tensor_count == len(schmidt.template.slots)
    assert dense.input_tensor_elements == sum(
        np.prod(shape) for shape in dense.template.shapes
    )
    assert schmidt.input_tensor_elements == sum(
        np.prod(shape) for shape in schmidt.template.shapes
    )


def test_dense_path_cannot_be_reused_for_schmidt_topology():
    spec = TFIMVQESpec(nqubits=3, depth=1)
    dense = plan_contraction(
        build_expectation_template(spec, gate_representation="dense"),
        "greedy",
    )
    with pytest.raises((ValueError, IndexError)):
        plan_contraction(
            build_expectation_template(
                spec,
                gate_representation="operator_schmidt",
            ),
            "greedy",
            explicit_path=dense.path,
        )
```

- [x] **Step 2: Verify metric tests fail**

Run:

```bash
.venv/bin/pytest -q tests/test_tn_program.py -k representation
```

Expected: missing metric attributes.

- [x] **Step 3: Add metrics and explicit path validation**

Add fields:

```python
tensor_count: int
input_tensor_elements: int
```

Populate them from `template.slots` and `template.shapes`. Wrap opt_einsum
explicit-path errors with a `ValueError` that states the path is incompatible
with the selected topology.

- [x] **Step 4: Run contraction-program tests**

Run:

```bash
.venv/bin/pytest -q tests/test_tn_program.py
```

Expected: all pass.

- [x] **Step 5: Commit**

```bash
git add src/vqetape/tn_program.py tests/test_tn_program.py
git commit -m "feat: measure representation contraction programs"
```

---

### Task 6: Propagate Representation Through VQE Builders

**Files:**
- Modify: `src/vqetape/tn_vqe.py`
- Modify: `tests/test_tn_vqe.py`

**Interfaces:**
- Consumes: `gate_representation: GateRepresentation`
- Produces: representation-aware `build_tn_energy` and
  `build_tn_value_and_grad`

- [x] **Step 1: Write full-gradient equivalence tests**

```python
@pytest.mark.parametrize("representation", ["dense", "operator_schmidt"])
@pytest.mark.parametrize("policy", ["none", "named"])
def test_representations_match_statevector_full_gradient(representation, policy):
    spec = TFIMVQESpec(nqubits=3, depth=2, coupling=0.8, field=1.1)
    theta = jnp.linspace(-0.2, 0.3, np.prod(spec.parameter_shape)).reshape(
        spec.parameter_shape
    )
    reference = build_value_and_grad(
        spec,
        ProgramConfig("unrolled", "default"),
    )
    candidate = build_tn_value_and_grad(
        spec,
        path_strategy="greedy",
        remat_policy=policy,
        save_names=() if policy == "named" else None,
        gate_representation=representation,
    )
    expected_energy, expected_gradient = reference(theta)
    energy, gradient = candidate(theta)
    np.testing.assert_allclose(energy, expected_energy, atol=1e-5)
    np.testing.assert_allclose(
        gradient,
        expected_gradient,
        rtol=1e-4,
        atol=1e-5,
    )
    np.testing.assert_array_equal(
        np.asarray(gradient[:, 0, -1]),
        np.zeros(spec.depth),
    )
```

- [x] **Step 2: Verify failure**

Run:

```bash
.venv/bin/pytest -q tests/test_tn_vqe.py -k representations
```

Expected: unexpected keyword argument.

- [x] **Step 3: Thread representation into template construction**

Add the keyword to both builders and call:

```python
template = build_expectation_template(
    spec,
    gate_representation=gate_representation,
)
```

No other energy or AD semantics change.

- [x] **Step 4: Run VQE correctness tests**

Run:

```bash
.venv/bin/pytest -q tests/test_tn_vqe.py
```

Expected: all pass.

- [x] **Step 5: Commit**

```bash
git add src/vqetape/tn_vqe.py tests/test_tn_vqe.py
git commit -m "feat: execute Schmidt-lowered VQE gradients"
```

---

### Task 7: Joint Representation–Path–Tape Candidate Search

**Files:**
- Modify: `src/vqetape/tn_candidates.py`
- Modify: `src/vqetape/worker.py`
- Modify: `tests/test_tn_candidates.py`

**Interfaces:**
- Consumes: representations, path strategies, named tape budgets
- Produces: one candidate set and Pareto frontier across all dimensions

- [x] **Step 1: Write candidate-isolation tests**

```python
def test_joint_candidates_cover_representations_and_reuse_paths():
    request = CompileRequest(
        TFIMVQESpec(nqubits=3, depth=1),
        memory_budget_bytes=1024**3,
        expected_vqe_steps=10,
    )
    candidates = enumerate_tn_candidates(
        request,
        strategies=("greedy",),
    )
    assert {item.gate_representation for item in candidates} == {
        "dense",
        "operator_schmidt",
    }
    for representation in ("dense", "operator_schmidt"):
        paths = {
            item.path
            for item in candidates
            if item.gate_representation == representation
        }
        assert len(paths) == 1
        assert next(iter(paths))
```

Add a fresh-worker test for one Schmidt named candidate and assert the
round-tripped config retains `operator_schmidt`.

- [x] **Step 2: Verify failure**

Run:

```bash
.venv/bin/pytest -q tests/test_tn_candidates.py
```

Expected: candidate set contains only dense programs.

- [x] **Step 3: Enumerate both representations**

Add:

```python
representations: tuple[GateRepresentation, ...] = (
    "dense",
    "operator_schmidt",
)
```

Nest representation outside path strategy. Build and search each topology
once, then attach that explicit path to all tape policies for the pair.

- [x] **Step 4: Thread representation through the worker**

Pass `config.gate_representation` to `build_tn_energy`. Add to
`static_estimate`:

```python
"gate_representation": config.gate_representation,
"tensor_count": path_program.tensor_count,
"input_tensor_elements": path_program.input_tensor_elements,
```

- [x] **Step 5: Run candidate and worker tests**

Run:

```bash
.venv/bin/pytest -q tests/test_tn_candidates.py tests/test_benchmark.py
```

Expected: all pass.

- [x] **Step 6: Commit**

```bash
git add src/vqetape/tn_candidates.py src/vqetape/worker.py tests/test_tn_candidates.py
git commit -m "feat: jointly search VQE representations and tapes"
```

---

### Task 8: Residual Attribution and Decision-Gate Tests

**Files:**
- Modify: `tests/test_tape.py`
- Modify: `tests/test_tn_vqe.py`

**Interfaces:**
- Consumes: dense and Schmidt named energy functions
- Produces: evidence that `_diag` is eliminated and tape control works for both

- [x] **Step 1: Add residual-source tests**

```python
def test_schmidt_lowering_eliminates_dense_diag_residuals():
    spec = TFIMVQESpec(nqubits=3, depth=2)
    theta = jnp.zeros(spec.parameter_shape)
    profiles = {}
    for representation in ("dense", "operator_schmidt"):
        energy, _, _ = build_tn_energy(
            spec,
            path_strategy="greedy",
            remat_policy="none",
            gate_representation=representation,
        )
        profiles[representation] = profile_saved_residuals(energy, theta)
    assert profiles["dense"].bytes_by_category().get("jitted:_diag", 0) > 0
    assert (
        profiles["operator_schmidt"]
        .bytes_by_category()
        .get("jitted:_diag", 0)
        == 0
    )
```

Parameterize the existing named-tape budget-ordering test over both
representations.

- [x] **Step 2: Run tests and inspect the actual residual categories**

Run:

```bash
.venv/bin/pytest -q tests/test_tape.py
```

Expected: pass after representation propagation; if JAX emits another
primitive name, record the exact structured category rather than parsing
printed text.

- [x] **Step 3: Add workload-matrix equivalence**

Parameterize the existing workload matrix over both representations and retain
the zero/plus initial states and two distinct \(J,g\) pairs.

- [x] **Step 4: Run correctness and residual suites**

Run:

```bash
.venv/bin/pytest -q tests/test_tape.py tests/test_tn_vqe.py
```

Expected: all pass.

- [x] **Step 5: Commit**

```bash
git add tests/test_tape.py tests/test_tn_vqe.py
git commit -m "test: validate Schmidt VQE residual behavior"
```

---

### Task 9: Reproducible Representation Experiment

**Files:**
- Modify: `README.md`
- Create: `outputs/vqetape-operator-schmidt-findings.md`
- Create through CLI: `outputs/vqetape-operator-schmidt-report.json`

**Interfaces:**
- Consumes: complete joint candidate search
- Produces: fixed experimental report and honest decision-gate audit

- [x] **Step 1: Run a smoke comparison**

Run:

```bash
.venv/bin/vqetape \
  --mode direct-tn \
  --nqubits 3 \
  --depth 2 \
  --memory-budget-gib 2 \
  --expected-steps 100 \
  --warm-repeats 3 \
  --output outputs/vqetape-operator-schmidt-report.json
```

Expected: valid dense and operator-Schmidt candidates with energy and gradient
errors within `complex64` tolerances.

- [x] **Step 2: Audit report invariants**

Run:

```bash
.venv/bin/python -c "import json; p=json.load(open('outputs/vqetape-operator-schmidt-report.json')); assert {x['config']['gate_representation'] for x in p['candidates']} == {'dense','operator_schmidt'}; assert all(x['valid'] for x in p['candidates'])"
```

Expected: no output and exit zero.

- [x] **Step 3: Write the findings report**

The report must include one table per representation with:

- input tensor elements;
- tensor count;
- path FLOPs;
- largest intermediate;
- default logical residual bytes;
- named-full residual bytes;
- compiler temp;
- compile time;
- warm median.

It must explicitly mark every design decision gate PASS or FAIL and must not
claim device peak-memory improvement from CPU RSS or logical tape bytes.

- [x] **Step 4: Update README**

Document `gate_representation`, the new joint search dimension, the exact
factorization, and a link to the findings report.

- [x] **Step 5: Run the full suite**

Run:

```bash
.venv/bin/pytest -q
```

Expected: all tests pass.

- [x] **Step 6: Commit**

```bash
git add README.md outputs/vqetape-operator-schmidt-findings.md outputs/vqetape-operator-schmidt-report.json
git commit -m "test: report operator-Schmidt VQETape evidence"
```

---

### Task 10: Completion Audit

**Files:**
- Modify: `docs/superpowers/plans/2026-07-29-vqetape-operator-schmidt.md`

**Interfaces:**
- Consumes: implementation commits, test output, experiment report
- Produces: checked plan and requirement-by-requirement completion evidence

- [x] **Step 1: Check every plan item against current files**

Confirm:

```text
configuration        -> spec.py and round-trip tests
factor algebra       -> kernels.py reconstruction tests
network topology     -> tn_template.py closed-network tests
path isolation       -> tn_candidates.py explicit-path tests
full gradient        -> tn_vqe.py oracle matrix
residual attribution -> test_tape.py structured profiles
fresh benchmark      -> worker result and JSON report
decision gates       -> findings markdown
```

- [x] **Step 2: Verify the repository is clean**

Run:

```bash
git status --short
```

Expected: no output.

- [x] **Step 3: Record the final test count**

Run:

```bash
.venv/bin/pytest -q
```

Expected: all tests pass; record the exact count and elapsed time in the
findings report.

- [x] **Step 4: Mark completed checkboxes and commit**

```bash
git add docs/superpowers/plans/2026-07-29-vqetape-operator-schmidt.md outputs/vqetape-operator-schmidt-findings.md
git commit -m "docs: complete operator-Schmidt VQETape phase"
```
