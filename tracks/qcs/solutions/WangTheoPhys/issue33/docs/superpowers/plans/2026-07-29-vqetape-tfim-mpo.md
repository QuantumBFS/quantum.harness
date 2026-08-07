# VQETape Exact TFIM MPO Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use completed Markdown checkboxes for tracking.

**Goal:** Add an exact bond-dimension-3 TFIM MPO and jointly compare Pauli-sum and one-shot bra–MPO–ket VQE value-and-full-gradient programs.

**Architecture:** A new `tfim_mpo` module constructs exact first, bulk, and last MPO tensors. A representation-aware template and binder feed the existing explicit contraction-path, residual-profile, named-tape, fresh-worker, and Pareto pipeline without imposing spatial-transfer control flow.

**Tech Stack:** Python 3.12, JAX 0.11, NumPy 2.x, opt_einsum 3.4, pytest 9

## Global Constraints

- The Hamiltonian convention is exactly `-J sum(ZZ) - g sum(X)` with open boundaries.
- The MPO internal bond dimension is exactly 3.
- Every candidate computes exact energy and the complete padded gradient.
- Pauli-sum and MPO candidates use identical VQE semantics, seeds, path strategies, tape-budget rules, and fresh-process measurement.
- Tape policies within one Hamiltonian-representation/path pair reuse one serialized explicit path.
- Logical residual bytes, compiler temporary bytes, process RSS, and device peak memory remain distinct metrics.
- The default MPO experiment fixes `gate_representation="dense"`.
- No spatial-transfer scan, custom carry adjoint, general Pauli-to-MPO compression, slicing, mixed precision, truncation, ansatz search, or classical optimizer is added in this phase.
- Existing APIs remain backward-compatible by defaulting to `hamiltonian_representation="pauli_sum"`.

---

### Task 1: Hamiltonian Representation Configuration

**Files:**
- Modify: `src/vqetape/spec.py`
- Modify: `tests/test_spec.py`

**Interfaces:**
- Produces: `HamiltonianRepresentation = Literal["pauli_sum", "mpo"]`
- Produces: `TensorProgramConfig.hamiltonian_representation`

- [x] **Step 1: Write failing round-trip and validation tests**

```python
def test_tensor_program_hamiltonian_representation_round_trip():
    config = TensorProgramConfig(
        "greedy",
        "none",
        hamiltonian_representation="mpo",
    )
    assert TensorProgramConfig.from_dict(config.to_dict()) == config
    assert "-mpo-" in config.label


def test_tensor_program_rejects_unknown_hamiltonian_representation():
    with pytest.raises(ValueError, match="hamiltonian_representation"):
        TensorProgramConfig(
            "greedy",
            "none",
            hamiltonian_representation="dense_matrix",
        )
```

- [x] **Step 2: Run tests and verify failure**

Run:

```bash
.venv/bin/pytest -q tests/test_spec.py
```

Expected: unexpected keyword argument.

- [x] **Step 3: Add the type and field**

```python
HamiltonianRepresentation = Literal["pauli_sum", "mpo"]


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
    hamiltonian_representation: HamiltonianRepresentation = "pauli_sum"
    representation: Literal["direct_tn"] = "direct_tn"
```

Validate membership in `("pauli_sum", "mpo")`. Include the normalized label
(`pauli-sum` or `mpo`) between the gate representation and path strategy.

- [x] **Step 4: Run configuration tests**

Run:

```bash
.venv/bin/pytest -q tests/test_spec.py
```

Expected: all pass.

- [x] **Step 5: Commit**

```bash
git add src/vqetape/spec.py tests/test_spec.py
git commit -m "feat: configure VQE Hamiltonian representations"
```

---

### Task 2: Exact TFIM MPO Algebra

**Files:**
- Create: `src/vqetape/tfim_mpo.py`
- Create: `tests/test_tfim_mpo.py`

**Interfaces:**
- Produces: `tfim_mpo_tensors(spec: TFIMVQESpec) -> tuple[Array, ...]`
- Produces: `dense_tfim_hamiltonian(spec: TFIMVQESpec) -> Array`

- [x] **Step 1: Write MPO shape and dense reconstruction tests**

```python
@pytest.mark.parametrize("nqubits", [2, 3, 4])
@pytest.mark.parametrize(
    ("coupling", "field"),
    [(1.0, 1.0), (0.7, 1.3), (0.0, 0.8), (1.1, 0.0)],
)
def test_tfim_mpo_reconstructs_dense_hamiltonian(
    nqubits,
    coupling,
    field,
):
    spec = TFIMVQESpec(
        nqubits=nqubits,
        depth=1,
        coupling=coupling,
        field=field,
    )
    tensors = tfim_mpo_tensors(spec)
    actual = contract_mpo_to_dense(tensors)
    expected = dense_tfim_hamiltonian(spec)
    np.testing.assert_allclose(
        np.asarray(actual),
        np.asarray(expected),
        rtol=1e-6,
        atol=1e-6,
    )
    assert len(tensors) == nqubits
    assert tensors[0].shape == (3, 2, 2)
    assert tensors[-1].shape == (3, 2, 2)
    assert all(tensor.shape == (3, 3, 2, 2) for tensor in tensors[1:-1])
```

In the test file, implement `contract_mpo_to_dense` with an opt_einsum
equation generated from one internal symbol per MPO bond and two output
symbols per site.

- [x] **Step 2: Verify the module is missing**

Run:

```bash
.venv/bin/pytest -q tests/test_tfim_mpo.py
```

Expected: import failure for `vqetape.tfim_mpo`.

- [x] **Step 3: Implement MPO tensors**

```python
def tfim_mpo_tensors(spec: TFIMVQESpec) -> tuple[Array, ...]:
    dtype = jnp.complex64 if spec.dtype == "complex64" else jnp.complex128
    identity = jnp.eye(2, dtype=dtype)
    pauli_x = jnp.asarray([[0, 1], [1, 0]], dtype=dtype)
    pauli_z = jnp.asarray([[1, 0], [0, -1]], dtype=dtype)
    first = jnp.stack(
        (-spec.field * pauli_x, -spec.coupling * pauli_z, identity),
        axis=0,
    )
    bulk = jnp.zeros((3, 3, 2, 2), dtype=dtype)
    bulk = bulk.at[0, 0].set(identity)
    bulk = bulk.at[1, 0].set(pauli_z)
    bulk = bulk.at[2, 0].set(-spec.field * pauli_x)
    bulk = bulk.at[2, 1].set(-spec.coupling * pauli_z)
    bulk = bulk.at[2, 2].set(identity)
    last = jnp.stack(
        (identity, pauli_z, -spec.field * pauli_x),
        axis=0,
    )
    return (first,) + (bulk,) * (spec.nqubits - 2) + (last,)
```

Implement the dense oracle by summing explicit Kronecker products of Pauli
matrices with the same signs and coefficients.

- [x] **Step 4: Add local `complex128` reconstruction**

```python
def test_tfim_mpo_complex128():
    with jax.enable_x64():
        spec = TFIMVQESpec(
            nqubits=3,
            depth=1,
            coupling=0.7,
            field=1.3,
            dtype="complex128",
        )
        np.testing.assert_allclose(
            contract_mpo_to_dense(tfim_mpo_tensors(spec)),
            dense_tfim_hamiltonian(spec),
            rtol=1e-12,
            atol=1e-12,
        )
```

- [x] **Step 5: Run algebra tests**

Run:

```bash
.venv/bin/pytest -q tests/test_tfim_mpo.py
```

Expected: all pass.

- [x] **Step 6: Commit**

```bash
git add src/vqetape/tfim_mpo.py tests/test_tfim_mpo.py
git commit -m "feat: construct exact TFIM MPO tensors"
```

---

### Task 3: MPO Expectation Template

**Files:**
- Modify: `src/vqetape/tn_template.py`
- Modify: `tests/test_tn_template.py`

**Interfaces:**
- Consumes: `HamiltonianRepresentation`
- Produces: `TensorNetworkTemplate.hamiltonian_representation`
- Produces: `build_mpo_expectation_template(...)`

- [x] **Step 1: Write topology tests**

```python
def test_mpo_expectation_template_is_closed():
    spec = TFIMVQESpec(nqubits=4, depth=2)
    template = build_mpo_expectation_template(spec)
    assert template.hamiltonian_representation == "mpo"
    mpo_slots = [
        slot for slot in template.slots
        if slot.kind.startswith("hamiltonian_mpo_")
    ]
    assert [slot.kind for slot in mpo_slots] == [
        "hamiltonian_mpo_first",
        "hamiltonian_mpo_bulk",
        "hamiltonian_mpo_bulk",
        "hamiltonian_mpo_last",
    ]
    assert [slot.shape for slot in mpo_slots] == [
        (3, 2, 2),
        (3, 3, 2, 2),
        (3, 3, 2, 2),
        (3, 2, 2),
    ]
    counts = Counter(
        index for slot in template.slots for index in slot.indices
    )
    assert set(counts.values()) == {2}
```

Update the dense-template default test to assert
`hamiltonian_representation == "pauli_sum"`.

- [x] **Step 2: Run tests and verify failure**

Run:

```bash
.venv/bin/pytest -q tests/test_tn_template.py -k mpo
```

Expected: import or attribute failure.

- [x] **Step 3: Refactor shared circuit construction**

Introduce:

```python
def _build_circuit_slots(
    spec: TFIMVQESpec,
    gate_representation: GateRepresentation,
) -> tuple[_IndexAllocator, list[TensorSlot], list[int], list[int]]:
```

It creates initial ket/bra slots, appends both circuit copies, and returns the
final ket and bra frontiers. Reuse it from both expectation-template builders.

- [x] **Step 4: Build MPO operator slots**

Allocate `nqubits - 1` MPO bond indices. Attach:

```python
TensorSlot(
    "hamiltonian_mpo_first",
    (mpo_bonds[0], bra_frontier[0], ket_frontier[0]),
    (3, 2, 2),
    wire=0,
)
```

bulk slots with indices
`(mpo_bonds[wire - 1], mpo_bonds[wire], bra, ket)`, and the final slot with
`(mpo_bonds[-1], bra, ket)`.

- [x] **Step 5: Run template tests**

Run:

```bash
.venv/bin/pytest -q tests/test_tn_template.py
```

Expected: all pass.

- [x] **Step 6: Commit**

```bash
git add src/vqetape/tn_template.py tests/test_tn_template.py
git commit -m "feat: build closed bra-MPO-ket templates"
```

---

### Task 4: Bind MPO Circuit Networks

**Files:**
- Modify: `src/vqetape/tn_template.py`
- Modify: `tests/test_tn_template.py`

**Interfaces:**
- Consumes: MPO-aware `TensorNetworkTemplate`, `theta`
- Produces: `bind_mpo_tensors(template, theta) -> tuple[Array, ...]`

- [x] **Step 1: Write binding and scalar equivalence tests**

```python
def test_bound_mpo_tensors_match_template_shapes():
    spec = TFIMVQESpec(nqubits=3, depth=2)
    template = build_mpo_expectation_template(spec)
    theta = jnp.zeros(spec.parameter_shape)
    tensors = bind_mpo_tensors(template, theta)
    assert tuple(tensor.shape for tensor in tensors) == template.shapes


def test_mpo_and_pauli_sum_scalar_contractions_match():
    spec = TFIMVQESpec(nqubits=3, depth=2, coupling=0.7, field=1.3)
    theta = jnp.linspace(-0.2, 0.3, np.prod(spec.parameter_shape)).reshape(
        spec.parameter_shape
    )
    mpo_template = build_mpo_expectation_template(spec)
    mpo_value = oe.contract(
        mpo_template.equation,
        *bind_mpo_tensors(mpo_template, theta),
        optimize="greedy",
        backend="jax",
    )
    term_template = build_expectation_template(spec)
    term_value = sum(
        term.coefficient * oe.contract(
            term_template.equation,
            *bind_term_tensors(term_template, theta, term),
            optimize="greedy",
            backend="jax",
        )
        for term in tfim_product_terms(spec)
    )
    np.testing.assert_allclose(mpo_value, term_value, atol=1e-5)
```

- [x] **Step 2: Verify the binder is missing**

Run:

```bash
.venv/bin/pytest -q tests/test_tn_template.py -k bound_mpo
```

Expected: import failure.

- [x] **Step 3: Extract common circuit-slot binding**

Implement:

```python
def _bind_non_hamiltonian_slot(
    template: TensorNetworkTemplate,
    slot: TensorSlot,
    theta: Array,
) -> Array:
```

Move initial-state, RX, dense RZZ, and Schmidt-factor binding into this helper.
Keep operator binding in the public Pauli and MPO binders.

- [x] **Step 4: Bind MPO slots**

Call `tfim_mpo_tensors(template.spec)` once. For an MPO slot, select the tensor
at `slot.wire`. Apply existing residual naming after binding every slot.

- [x] **Step 5: Run binding tests**

Run:

```bash
.venv/bin/pytest -q tests/test_tn_template.py
```

Expected: all pass.

- [x] **Step 6: Commit**

```bash
git add src/vqetape/tn_template.py tests/test_tn_template.py
git commit -m "feat: bind exact MPO VQE networks"
```

---

### Task 5: One-Shot MPO Energy and Full Gradient

**Files:**
- Modify: `src/vqetape/tn_vqe.py`
- Modify: `tests/test_tn_vqe.py`

**Interfaces:**
- Consumes: `hamiltonian_representation: HamiltonianRepresentation`
- Produces: representation-aware `build_tn_energy` and
  `build_tn_value_and_grad`

- [x] **Step 1: Write value-and-gradient oracle tests**

```python
@pytest.mark.parametrize(
    "hamiltonian_representation",
    ["pauli_sum", "mpo"],
)
@pytest.mark.parametrize("policy", ["none", "named"])
def test_hamiltonian_representations_match_statevector_full_gradient(
    hamiltonian_representation,
    policy,
):
    spec = TFIMVQESpec(
        nqubits=3,
        depth=2,
        coupling=0.7,
        field=1.3,
    )
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
        hamiltonian_representation=hamiltonian_representation,
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
```

- [x] **Step 2: Verify unexpected keyword failure**

Run:

```bash
.venv/bin/pytest -q tests/test_tn_vqe.py -k hamiltonian_representations
```

Expected: unexpected keyword argument.

- [x] **Step 3: Add the representation branch**

For `pauli_sum`, retain the existing loop. For `mpo`, build one MPO template,
plan one contraction, bind once, contract once, and return the real scalar:

```python
def raw_energy(theta: Array) -> Array:
    tensors = bind_mpo_tensors(
        template,
        theta,
        name_residuals=name_residuals,
    )
    expectation = execute_contraction(
        program,
        tensors,
        remat_steps=remat_steps,
        name_residuals=name_residuals,
    )
    return jnp.real(expectation)
```

Apply `term`, `objective`, `subtree`, and named policies with the same
validation semantics as Pauli sum.

- [x] **Step 4: Verify padding gradient and multiple workloads**

Parameterize the existing workload matrix over both Hamiltonian
representations and retain exact zero checks for `gradient[:, 0, -1]`.

- [x] **Step 5: Run VQE tests**

Run:

```bash
.venv/bin/pytest -q tests/test_tn_vqe.py
```

Expected: all pass.

- [x] **Step 6: Commit**

```bash
git add src/vqetape/tn_vqe.py tests/test_tn_vqe.py
git commit -m "feat: differentiate one-shot TFIM MPO contractions"
```

---

### Task 6: Energy-Level Cost Metrics

**Files:**
- Modify: `src/vqetape/worker.py`
- Modify: `tests/test_tn_candidates.py`

**Interfaces:**
- Consumes: path program and Hamiltonian representation
- Produces: fair energy-level static metrics

- [x] **Step 1: Write fresh-worker metric tests**

```python
@pytest.mark.parametrize(
    ("hamiltonian_representation", "expected_contractions"),
    [("pauli_sum", 5), ("mpo", 1)],
)
def test_worker_reports_energy_level_costs(
    hamiltonian_representation,
    expected_contractions,
):
    spec = TFIMVQESpec(nqubits=3, depth=1)
    result = benchmark_tn_candidate(
        spec=spec,
        config=TensorProgramConfig(
            "greedy",
            "none",
            hamiltonian_representation=hamiltonian_representation,
        ),
        seed=1,
        warm_repeats=1,
        timeout_seconds=180,
    )
    estimate = result.static_estimate
    assert estimate["contractions_per_energy"] == expected_contractions
    assert estimate["estimated_energy_flops"] == (
        estimate["path_flops"] * expected_contractions
    )
    assert estimate["estimated_energy_tensor_bindings"] == (
        estimate["tensor_count"] * expected_contractions
    )
```

- [x] **Step 2: Run and verify missing keys**

Run:

```bash
.venv/bin/pytest -q tests/test_tn_candidates.py -k energy_level_costs
```

Expected: key failure or MPO construction failure.

- [x] **Step 3: Add fair metrics**

Pass `config.hamiltonian_representation` into `build_tn_energy`. Compute:

```python
contractions_per_energy = (
    2 * spec.nqubits - 1
    if config.hamiltonian_representation == "pauli_sum"
    else 1
)
```

Add:

```python
"hamiltonian_representation": config.hamiltonian_representation,
"contractions_per_energy": contractions_per_energy,
"estimated_energy_flops": (
    path_program.flops * contractions_per_energy
),
"estimated_energy_tensor_bindings": (
    path_program.tensor_count * contractions_per_energy
),
```

- [x] **Step 4: Run worker tests**

Run:

```bash
.venv/bin/pytest -q tests/test_tn_candidates.py
```

Expected: all pass.

- [x] **Step 5: Commit**

```bash
git add src/vqetape/worker.py tests/test_tn_candidates.py
git commit -m "feat: report VQE energy-level contraction costs"
```

---

### Task 7: Joint Hamiltonian–Path–Tape Search

**Files:**
- Modify: `src/vqetape/tn_candidates.py`
- Modify: `tests/test_tn_candidates.py`

**Interfaces:**
- Consumes: `HamiltonianRepresentation`
- Produces: 24 default candidates with dense gates

- [x] **Step 1: Write candidate-isolation tests**

```python
def test_joint_candidates_cover_hamiltonian_representations():
    request = CompileRequest(
        TFIMVQESpec(nqubits=3, depth=1),
        memory_budget_bytes=1024**3,
        expected_vqe_steps=10,
    )
    candidates = enumerate_tn_candidates(
        request,
        strategies=("greedy",),
    )
    assert {item.gate_representation for item in candidates} == {"dense"}
    assert {item.hamiltonian_representation for item in candidates} == {
        "pauli_sum",
        "mpo",
    }
    assert len(candidates) == 8
    for representation in ("pauli_sum", "mpo"):
        matching = [
            item for item in candidates
            if item.hamiltonian_representation == representation
        ]
        assert len({item.path for item in matching}) == 1
        assert {item.remat_policy for item in matching} == {"none", "named"}
```

- [x] **Step 2: Verify old gate-representation search fails expectations**

Run:

```bash
.venv/bin/pytest -q tests/test_tn_candidates.py -k joint_candidates
```

Expected: only `pauli_sum` and both gate representations appear.

- [x] **Step 3: Change search axes**

Use:

```python
gate_representations: tuple[GateRepresentation, ...] = ("dense",)
hamiltonian_representations: tuple[HamiltonianRepresentation, ...] = (
    "pauli_sum",
    "mpo",
)
```

Build the appropriate template for each pair, search each path once, and
attach it to one default and three named tape candidates.

- [x] **Step 4: Preserve diagnostic gate search**

Keep both keyword parameters public so the previous operator-Schmidt
experiment can be reproduced with:

```python
enumerate_tn_candidates(
    request,
    gate_representations=("dense", "operator_schmidt"),
    hamiltonian_representations=("pauli_sum",),
)
```

- [x] **Step 5: Run candidate tests**

Run:

```bash
.venv/bin/pytest -q tests/test_tn_candidates.py
```

Expected: all pass.

- [x] **Step 6: Commit**

```bash
git add src/vqetape/tn_candidates.py tests/test_tn_candidates.py
git commit -m "feat: jointly search Pauli-sum and MPO VQE programs"
```

---

### Task 8: Residual and Cross-Topology Validation

**Files:**
- Modify: `tests/test_tape.py`
- Modify: `tests/test_tn_program.py`

**Interfaces:**
- Consumes: complete Pauli-sum and MPO energy functions
- Produces: structured residual and path-isolation evidence

- [x] **Step 1: Add logical tape comparison**

```python
def test_mpo_removes_repeated_circuit_gate_residuals():
    spec = TFIMVQESpec(nqubits=3, depth=2)
    theta = jnp.zeros(spec.parameter_shape)
    profiles = {}
    for representation in ("pauli_sum", "mpo"):
        energy, _, _ = build_tn_energy(
            spec,
            path_strategy="greedy",
            remat_policy="none",
            hamiltonian_representation=representation,
        )
        profiles[representation] = profile_saved_residuals(energy, theta)
    assert profiles["mpo"].total_bytes < profiles["pauli_sum"].total_bytes
    assert (
        profiles["mpo"].bytes_by_category().get("jitted:_diag", 0)
        <
        profiles["pauli_sum"].bytes_by_category().get("jitted:_diag", 0)
    )
```

Parameterize named tape ordering over both Hamiltonian representations.

- [x] **Step 2: Add cross-topology path replanning**

```python
def test_explicit_path_is_revalidated_against_mpo_topology():
    spec = TFIMVQESpec(nqubits=3, depth=1)
    pauli = plan_contraction(build_expectation_template(spec), "greedy")
    mpo = plan_contraction(
        build_mpo_expectation_template(spec),
        "greedy",
        explicit_path=pauli.path,
    )
    assert mpo.path == pauli.path
    assert mpo.template.hamiltonian_representation == "mpo"
    assert mpo.template.equation != pauli.template.equation
    assert mpo.flops != pauli.flops
```

A positional schedule may remain valid when two different networks happen to
have the same operand count. In that case it is safe to reuse the schedule,
but the contraction equations, intermediate sizes, and FLOP cost must be
rebuilt for the selected topology. Invalid positional schedules are rejected.

- [x] **Step 3: Run residual and path tests**

Run:

```bash
.venv/bin/pytest -q tests/test_tape.py tests/test_tn_program.py
```

Expected: all pass.

- [x] **Step 4: Commit**

```bash
git add tests/test_tape.py tests/test_tn_program.py
git commit -m "test: validate MPO tape sharing and topology isolation"
```

---

### Task 9: Reproducible MPO Experiments

**Files:**
- Modify: `README.md`
- Create through CLI: `outputs/vqetape-tfim-mpo-report.json`
- Create through CLI: `outputs/vqetape-tfim-mpo-report-holdout.json`
- Create: `outputs/vqetape-tfim-mpo-findings.md`

**Interfaces:**
- Consumes: the complete Hamiltonian/path/tape search
- Produces: two fixed reports and a decision-gate audit

- [x] **Step 1: Run the primary experiment**

```bash
.venv/bin/vqetape \
  --mode direct-tn \
  --nqubits 3 \
  --depth 2 \
  --memory-budget-gib 2 \
  --expected-steps 100 \
  --warm-repeats 3 \
  --timeout-seconds 240 \
  --output outputs/vqetape-tfim-mpo-report.json
```

- [x] **Step 2: Run the holdout experiment**

```bash
.venv/bin/vqetape \
  --mode direct-tn \
  --nqubits 3 \
  --depth 1 \
  --coupling 0.7 \
  --field 0.3 \
  --initial-state zero \
  --memory-budget-gib 2 \
  --expected-steps 100 \
  --warm-repeats 3 \
  --timeout-seconds 180 \
  --output outputs/vqetape-tfim-mpo-report-holdout.json
```

- [x] **Step 3: Audit JSON invariants**

```bash
.venv/bin/python -c "import json; p=json.load(open('outputs/vqetape-tfim-mpo-report.json')); assert len(p['candidates']) == 24; assert {x['config']['hamiltonian_representation'] for x in p['candidates']} == {'pauli_sum','mpo'}; assert all(x['valid'] for x in p['candidates'])"
```

Expected: exit zero.

- [x] **Step 4: Write findings**

Include:

- all default path rows for both Hamiltonian representations;
- contractions per energy;
- path and estimated energy FLOPs;
- logical residual bytes and `_diag` bytes;
- compiler temp;
- compile and warm time;
- maximum oracle errors;
- two-dimensional temp/warm dominance;
- a PASS/FAIL row for every design decision gate.

- [x] **Step 5: Update README**

Document the exact \(\chi_H=3\) MPO, the new configuration dimension, fair
energy-level metrics, and a link to the findings.

- [x] **Step 6: Run the full suite**

```bash
.venv/bin/pytest -q
```

Expected: all tests pass.

- [x] **Step 7: Commit**

```bash
git add README.md outputs/vqetape-tfim-mpo-report.json outputs/vqetape-tfim-mpo-report-holdout.json outputs/vqetape-tfim-mpo-findings.md
git commit -m "test: report exact MPO VQETape evidence"
```

---

### Task 10: Completion Audit

**Files:**
- Modify: `docs/superpowers/plans/2026-07-29-vqetape-tfim-mpo.md`
- Modify: `outputs/vqetape-tfim-mpo-findings.md`

**Interfaces:**
- Consumes: source, tests, reports, git state
- Produces: checked plan and exact completion evidence

- [x] **Step 1: Match requirements to evidence**

```text
configuration       -> spec round-trip and validation tests
MPO algebra         -> n=2,3,4 dense reconstruction tests
closed topology     -> first/bulk/last slot and index tests
one-shot energy     -> full-gradient oracle tests
fair cost model     -> contractions_per_energy worker tests
path/tape isolation -> candidate, named-tape, and topology-replanning tests
residual sharing    -> structured VJP profile tests
fresh benchmarks    -> two JSON reports
decision gates      -> findings audit
```

- [x] **Step 2: Run the final regression**

```bash
.venv/bin/pytest -q
```

Record the exact count and elapsed time in the findings.

- [x] **Step 3: Verify clean state before the checklist commit**

```bash
git status --short
```

Expected: only the plan and findings updates are present.

- [x] **Step 4: Mark every completed checkbox and commit**

```bash
git add docs/superpowers/plans/2026-07-29-vqetape-tfim-mpo.md outputs/vqetape-tfim-mpo-findings.md
git commit -m "docs: complete exact TFIM MPO VQETape phase"
```
