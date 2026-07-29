# R01 Overlapping Klein Cone Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build an exact and numerical six-mode oracle that either exhibits a certified cross-cluster quadratic Klein/Fock Metzler cone with two noncommuting rays or proves that every designated cross-cluster coefficient vanishes by exact dual certificates.

**Architecture:** Separate exact occupation-basis algebra, fixed Klein circuit construction, Metzler inequality compilation, and LP/certificate logic into focused modules. Compile one fixed algebraic inequality system per geometry/family, use SciPy HiGHS only to discover sparse primal or dual supports, and replay every scientific conclusion with SymPy exact arithmetic before recording it.

**Tech Stack:** Python 3.11+, NumPy, SciPy (`optimize.linprog`), SymPy exact sparse matrices, pytest, JSON protocol fixtures, Git/GitHub shared topic branch, WSL and a plain-SSH CPU worker.

## Global Constraints

- Work only in `work/zibo/representation-cones`; merge through internal PR #3.
- Do not update the organizer-facing branch or PR #178.
- Use one fixed, field-independent Fock transform for every layer in a candidate.
- Treat actual even/odd parity traces as the physical branches; never infer their signs from an arbitrary square root of a determinant.
- Numerical feasibility is discovery evidence only. A survivor needs an exact algebraic primal certificate; a no-go needs exact positive dual identities.
- A negative floating-point weight is not a counterexample until high-precision or exact replay succeeds.
- Run tests from `tracks/qmc/solutions/no-negative-vibes` with `PYTHONPATH=.`.
- Set `OMP_NUM_THREADS=1`, `MKL_NUM_THREADS=1`, and `OPENBLAS_NUM_THREADS=1`.
- Use `workers=max(1, logical_cpus-2)` only after a deterministic one-worker smoke run.
- Append every completed experiment, including failures, to `docs/EXPERIMENT_LOG.md`, and append reusable mechanical lessons to `docs/RESEARCH_OPERATIONS.md`.
- Commit and push each interpreted experiment before starting the next one.
- Commit no hostnames, usernames, passwords, private-key paths, or private handoff content.

---

## File map

Create these focused modules:

- `oracle/fock_basis.py`: exact Jordan–Wigner occupation operators, parity indices, and quadratic Fock basis elements.
- `oracle/klein_hodge.py`: exact four-mode Klein–Hodge transform, contiguous even-gate embedding, overlap circuit, Plücker diagnostic, and four-mode seed.
- `oracle/metzler_system.py`: exact transformed off-diagonal inequality compiler and exact Metzler predicates.
- `oracle/overlap_klein.py`: six-mode geometry, support masks, anchored LPs, exact primal/dual certificates, protocol runner, and CLI.
- `tests/test_fock_basis.py`: CAR, signs, parity, and one-body second-quantization tests.
- `tests/test_klein_hodge.py`: exact transform, non-inducedness, embedding, and four-mode seed tests.
- `tests/test_metzler_system.py`: compiler row provenance and exact/numeric consistency tests.
- `tests/test_overlap_klein.py`: geometry, anchor feasibility, certificate replay, deterministic multiprocessing, and payload-schema tests.
- `protocols/overlap-klein-v1/{README.md,settings.json,axes.json,provenance.json}`: preregistered six-mode experiment.
- `fixtures/overlap_klein_r01.json`: compact terminal R01 result and exact certificate strings.
- `docs/OVERLAPPING_KLEIN_RESULTS.md`: human-readable theorem/survivor/no-go conclusion.

Modify:

- `docs/EXPERIMENT_LOG.md`: one entry per completed run.
- `docs/PROPOSAL_LEDGER.md`: R01 state transitions with evidence links.
- `docs/RESEARCH_OPERATIONS.md`: new reusable environment or transfer lessons.
- `docs/README.md`: link the terminal R01 result.

---

### Task 1: Exact occupation-basis quadratic algebra

**Files:**

- Create: `tracks/qmc/solutions/no-negative-vibes/oracle/fock_basis.py`
- Create: `tracks/qmc/solutions/no-negative-vibes/tests/test_fock_basis.py`

**Interfaces:**

- Produces:
  - `annihilation_operator(modes: int, index: int) -> sympy.ImmutableSparseMatrix`
  - `creation_operator(modes: int, index: int) -> sympy.ImmutableSparseMatrix`
  - `parity_indices(modes: int) -> tuple[tuple[int, ...], tuple[int, ...]]`
  - `one_body_operator(matrix: sympy.MatrixBase) -> sympy.ImmutableSparseMatrix`
  - `quadratic_term(modes: int, kind: str, i: int, j: int) -> sympy.ImmutableSparseMatrix`
  - `exact_to_numpy(matrix: sympy.MatrixBase) -> numpy.ndarray`
  - immutable `QuadraticBasisElement(label, kind, i, j, fock)`
- Consumers: Tasks 2–9.

- [ ] **Step 1: Write failing CAR and occupation-sign tests**

```python
from __future__ import annotations

import numpy as np
import pytest
import sympy as sp

from oracle.fock_basis import (
    annihilation_operator,
    creation_operator,
    exact_to_numpy,
    one_body_operator,
    parity_indices,
    quadratic_term,
)


def test_exact_creation_annihilation_operators_satisfy_car() -> None:
    modes = 3
    identity = sp.eye(1 << modes)
    annihilation = [annihilation_operator(modes, i) for i in range(modes)]
    creation = [creation_operator(modes, i) for i in range(modes)]

    for i in range(modes):
        for j in range(modes):
            expected = identity if i == j else sp.zeros(1 << modes)
            assert annihilation[i] * creation[j] + creation[j] * annihilation[i] == expected
            assert annihilation[i] * annihilation[j] + annihilation[j] * annihilation[i] == sp.zeros(1 << modes)


def test_jordan_wigner_sign_uses_lower_occupied_modes() -> None:
    operator = creation_operator(3, 2)
    source = 0b011
    target = 0b111
    assert operator[target, source] == 1

    operator = creation_operator(3, 1)
    source = 0b001
    target = 0b011
    assert operator[target, source] == -1


def test_quadratic_terms_preserve_parity() -> None:
    even, odd = parity_indices(4)
    for kind in ("hop", "pair_create", "pair_annihilate"):
        matrix = quadratic_term(4, kind, 0, 2)
        assert matrix.extract(even, odd) == sp.zeros(len(even), len(odd))
        assert matrix.extract(odd, even) == sp.zeros(len(odd), len(even))


def test_one_body_operator_matches_direct_sum_over_hops() -> None:
    matrix = sp.Matrix([[2, 3], [5, 7]])
    expected = (
        2 * quadratic_term(2, "hop", 0, 0)
        + 3 * quadratic_term(2, "hop", 0, 1)
        + 5 * quadratic_term(2, "hop", 1, 0)
        + 7 * quadratic_term(2, "hop", 1, 1)
    )
    assert one_body_operator(matrix) == expected
    assert exact_to_numpy(expected).dtype == np.float64


@pytest.mark.parametrize(("modes", "index"), [(0, 0), (2, -1), (2, 2)])
def test_invalid_mode_indices_are_rejected(modes: int, index: int) -> None:
    with pytest.raises(ValueError):
        annihilation_operator(modes, index)
```

- [ ] **Step 2: Run the new tests and verify import failure**

Run:

```bash
cd tracks/qmc/solutions/no-negative-vibes
PYTHONPATH=. python -m pytest tests/test_fock_basis.py -q
```

Expected: collection fails with `ModuleNotFoundError: No module named 'oracle.fock_basis'`.

- [ ] **Step 3: Implement exact state-transition operators**

Use occupation states `0..2**modes-1` and the sign
`(-1)**((state & ((1 << index) - 1)).bit_count())`. Define:

```python
@dataclass(frozen=True)
class QuadraticBasisElement:
    label: str
    kind: str
    i: int
    j: int
    fock: sp.ImmutableSparseMatrix
```

Implement `quadratic_term` with these exact conventions:

```python
if kind == "hop":
    result = creation_operator(modes, i) * annihilation_operator(modes, j)
elif kind == "pair_create":
    if not i < j:
        raise ValueError("pair indices must satisfy i < j")
    result = creation_operator(modes, i) * creation_operator(modes, j)
elif kind == "pair_annihilate":
    if not i < j:
        raise ValueError("pair indices must satisfy i < j")
    result = annihilation_operator(modes, j) * annihilation_operator(modes, i)
else:
    raise ValueError(f"unknown quadratic term kind: {kind}")
```

Return immutable sparse matrices and convert to NumPy through
`np.array(matrix.tolist(), dtype=float)`.

- [ ] **Step 4: Run focused and baseline tests**

Run:

```bash
PYTHONPATH=. python -m pytest tests/test_fock_basis.py -q
PYTHONPATH=. python -m pytest tests -q
```

Expected: new tests pass and baseline remains at least `199 passed`.

- [ ] **Step 5: Commit and push**

```bash
git add tracks/qmc/solutions/no-negative-vibes/oracle/fock_basis.py \
        tracks/qmc/solutions/no-negative-vibes/tests/test_fock_basis.py
git commit -m "feat: add exact occupation-basis quadratic algebra"
git push shared work/zibo/representation-cones
```

---

### Task 2: Exact Klein–Hodge transform and four-mode theorem anchor

**Files:**

- Create: `tracks/qmc/solutions/no-negative-vibes/oracle/klein_hodge.py`
- Create: `tracks/qmc/solutions/no-negative-vibes/tests/test_klein_hodge.py`

**Interfaces:**

- Consumes: Task 1 exact Fock operators.
- Produces:
  - `klein_hodge_gate() -> sympy.ImmutableSparseMatrix`
  - `embed_contiguous_even_gate(gate, *, start: int, total_modes: int) -> sympy.ImmutableSparseMatrix`
  - `overlap_klein_circuit() -> sympy.ImmutableSparseMatrix`
  - `klein_seed_one_body() -> sympy.ImmutableMatrix`
  - `plucker_quadric(two_particle_coordinates: sympy.MatrixBase) -> sympy.Expr`
  - `is_orthogonal_exact(matrix: sympy.MatrixBase) -> bool`

- [ ] **Step 1: Write failing exact transform tests**

```python
import sympy as sp

from oracle.fock_basis import one_body_operator, parity_indices
from oracle.klein_hodge import (
    embed_contiguous_even_gate,
    is_orthogonal_exact,
    klein_hodge_gate,
    klein_seed_one_body,
    overlap_klein_circuit,
    plucker_quadric,
)


def _is_metzler(matrix: sp.MatrixBase) -> bool:
    return all(
        sp.simplify(matrix[i, j]) >= 0
        for i in range(matrix.rows)
        for j in range(matrix.cols)
        if i != j
    )


def test_klein_gate_is_exact_orthogonal_and_number_sector_preserving() -> None:
    gate = klein_hodge_gate()
    assert gate.shape == (16, 16)
    assert is_orthogonal_exact(gate)
    for left in range(16):
        for right in range(16):
            if left.bit_count() != right.bit_count():
                assert gate[left, right] == 0


def test_klein_transform_is_not_induced_by_one_particle_basis_change() -> None:
    gate = klein_hodge_gate()
    two_particle = (3, 5, 9, 6, 10, 12)
    transformed_e12 = gate.extract(two_particle, two_particle).T * sp.eye(6)[:, 0]
    assert sp.simplify(plucker_quadric(transformed_e12)) != 0


def test_exact_four_mode_seed_is_metzler_in_both_parities() -> None:
    gate = klein_hodge_gate()
    transformed = sp.simplify(gate * one_body_operator(klein_seed_one_body()) * gate.T)
    even, odd = parity_indices(4)
    assert _is_metzler(transformed.extract(even, even))
    assert _is_metzler(transformed.extract(odd, odd))


def test_overlap_circuit_is_one_fixed_six_mode_orthogonal_gate() -> None:
    gate = overlap_klein_circuit()
    assert gate.shape == (64, 64)
    assert is_orthogonal_exact(gate)

    left = embed_contiguous_even_gate(klein_hodge_gate(), start=0, total_modes=6)
    right = embed_contiguous_even_gate(klein_hodge_gate(), start=2, total_modes=6)
    assert gate == right * left
```

- [ ] **Step 2: Run and verify import failure**

Run:

```bash
PYTHONPATH=. python -m pytest tests/test_klein_hodge.py -q
```

Expected: collection fails because `oracle.klein_hodge` does not exist.

- [ ] **Step 3: Implement the fixed basis convention**

Use two-particle occupation order:

```python
_TWO_PARTICLE_STATES = (0b0011, 0b0101, 0b1001, 0b0110, 0b1010, 0b1100)
```

The rows of the `6 x 6` change-of-coordinates block are:

```text
(e12 + e34)/sqrt(2)
(e12 - e34)/sqrt(2)
(e13 - e24)/sqrt(2)
(e13 + e24)/sqrt(2)
(e14 + e23)/sqrt(2)
(e14 - e23)/sqrt(2)
```

Embed this block into a `16 x 16` identity. Restrict
`embed_contiguous_even_gate` to sorted contiguous mode blocks and reject all
other embeddings; this avoids silently choosing a fermionic tensor convention
for noncontiguous gates.

Use the exact seed:

```python
sp.ImmutableMatrix(
    [
        [3, 1, 0, 1],
        [1, 0, 2, 0],
        [0, 2, 0, 2],
        [1, 0, 2, 0],
    ]
)
```

For bivector coordinates `(p12,p13,p14,p23,p24,p34)`, return
`p12*p34 - p13*p24 + p14*p23`. The gate stores new-basis vectors as
rows, so the test applies its transpose to `e12`. Since induced exterior
transformations are closed under inversion, a non-induced inverse proves the
gate itself is non-induced.

- [ ] **Step 4: Run focused and baseline tests**

```bash
PYTHONPATH=. python -m pytest tests/test_fock_basis.py tests/test_klein_hodge.py -q
PYTHONPATH=. python -m pytest tests -q
```

Expected: all tests pass; the exact seed test establishes the convention before
six-mode work.

- [ ] **Step 5: Commit and push**

```bash
git add tracks/qmc/solutions/no-negative-vibes/oracle/klein_hodge.py \
        tracks/qmc/solutions/no-negative-vibes/tests/test_klein_hodge.py
git commit -m "feat: encode exact Klein-Hodge Fock transform"
git push shared work/zibo/representation-cones
```

---

### Task 3: Six-mode geometry and quadratic support masks

**Files:**

- Create: `tracks/qmc/solutions/no-negative-vibes/oracle/overlap_klein.py`
- Create: `tracks/qmc/solutions/no-negative-vibes/tests/test_overlap_klein.py`

**Interfaces:**

- Consumes: `QuadraticBasisElement`, `quadratic_term`, and the overlap circuit.
- Produces:
  - immutable `OverlapGeometry(modes, blocks, ring_edges, diagonal_edges, bridge_edges)`
  - `overlap_geometry() -> OverlapGeometry`
  - `support_edges(mask: str) -> tuple[tuple[int, int], ...]`
  - `quadratic_basis(family: str, mask: str) -> tuple[QuadraticBasisElement, ...]`
  - `bridge_labels(family: str) -> tuple[str, ...]`
- Later tasks extend the same module; do not add LP code in this task.

- [ ] **Step 1: Write failing geometry and basis tests**

```python
from oracle.overlap_klein import (
    bridge_labels,
    overlap_geometry,
    quadratic_basis,
    support_edges,
)


def test_overlap_geometry_has_two_fixed_plaquettes_and_two_bridges() -> None:
    geometry = overlap_geometry()
    assert geometry.modes == 6
    assert geometry.blocks == ((0, 1, 2, 3), (2, 3, 4, 5))
    assert geometry.bridge_edges == ((0, 4), (1, 5))
    assert set(geometry.ring_edges) == {
        (0, 1), (1, 2), (2, 3), (0, 3),
        (3, 4), (4, 5), (2, 5),
    }


def test_support_masks_are_nested_and_do_not_become_complete_graph() -> None:
    rings = set(support_edges("rings"))
    bridges = set(support_edges("rings-bridges"))
    full = set(support_edges("rings-diagonals-bridges"))
    assert rings < bridges < full
    assert len(full) == 13
    assert (0, 5) not in full
    assert (1, 4) not in full


def test_number_conserving_basis_has_directed_hops_and_onsite_terms() -> None:
    basis = quadratic_basis("number-conserving", "rings-bridges")
    labels = {item.label for item in basis}
    assert {"n0", "h0<-1", "h1<-0", "h0<-4", "h4<-0"} <= labels
    assert all(item.kind == "hop" for item in basis)


def test_bdg_basis_adds_independent_creation_and_annihilation_terms() -> None:
    number = quadratic_basis("number-conserving", "rings-bridges")
    bdg = quadratic_basis("bdg", "rings-bridges")
    labels = {item.label for item in bdg}
    assert len(bdg) == len(number) + 2 * len(support_edges("rings-bridges"))
    assert {"pc0,4", "pa0,4"} <= labels
    assert set(bridge_labels("bdg")) == {
        "h0<-4", "h4<-0", "pc0,4", "pa0,4",
        "h1<-5", "h5<-1", "pc1,5", "pa1,5",
    }
```

- [ ] **Step 2: Run and verify missing interfaces**

```bash
PYTHONPATH=. python -m pytest tests/test_overlap_klein.py -q
```

Expected: import fails for the new geometry functions.

- [ ] **Step 3: Implement exact mask and label conventions**

Use:

```python
ring_edges = ((0, 1), (1, 2), (2, 3), (0, 3), (3, 4), (4, 5), (2, 5))
diagonal_edges = ((0, 2), (1, 3), (2, 4), (3, 5))
bridge_edges = ((0, 4), (1, 5))
```

For every undirected edge `(i,j)`, add directed hopping terms
`c_i^dag c_j` and `c_j^dag c_i`. Add six onsite terms. For `bdg`, also add
`c_i^dag c_j^dag` and `c_j c_i` once per edge. Sort labels and edges
deterministically.

- [ ] **Step 4: Run focused tests**

```bash
PYTHONPATH=. python -m pytest tests/test_overlap_klein.py -q
```

Expected: all geometry/basis tests pass.

- [ ] **Step 5: Commit and push**

```bash
git add tracks/qmc/solutions/no-negative-vibes/oracle/overlap_klein.py \
        tracks/qmc/solutions/no-negative-vibes/tests/test_overlap_klein.py
git commit -m "feat: define six-mode overlap candidate geometry"
git push shared work/zibo/representation-cones
```

---

### Task 4: Exact Metzler inequality compiler

**Files:**

- Create: `tracks/qmc/solutions/no-negative-vibes/oracle/metzler_system.py`
- Create: `tracks/qmc/solutions/no-negative-vibes/tests/test_metzler_system.py`

**Interfaces:**

- Consumes: exact transform and `QuadraticBasisElement`.
- Produces:
  - immutable `MetzlerRow(parity, target_state, source_state)`
  - immutable `ExactMetzlerSystem(labels, rows, coefficients)`
  - `compile_metzler_system(transform, basis, parity_blocks) -> ExactMetzlerSystem`
  - `numeric_coefficients(system) -> numpy.ndarray`
  - `exact_linear_combination(system, coefficients) -> sympy.ImmutableMatrix`
  - `exact_nonnegative(expr: sympy.Expr) -> bool`
  - `verify_exact_metzler(system, coefficients) -> bool`

- [ ] **Step 1: Write failing compiler tests**

```python
import numpy as np
import sympy as sp

from oracle.fock_basis import QuadraticBasisElement, parity_indices, quadratic_term
from oracle.metzler_system import (
    compile_metzler_system,
    numeric_coefficients,
    verify_exact_metzler,
)


def test_identity_compiler_tracks_offdiagonal_rows_and_labels() -> None:
    basis = (
        QuadraticBasisElement("h0<-1", "hop", 0, 1, quadratic_term(2, "hop", 0, 1)),
        QuadraticBasisElement("h1<-0", "hop", 1, 0, quadratic_term(2, "hop", 1, 0)),
    )
    system = compile_metzler_system(sp.eye(4), basis, parity_indices(2))
    assert system.labels == ("h0<-1", "h1<-0")
    assert system.coefficients.cols == 2
    assert all(row.target_state != row.source_state for row in system.rows)
    assert np.allclose(numeric_coefficients(system), np.array(system.coefficients.tolist(), dtype=float))


def test_exact_verifier_accepts_positive_hops_and_rejects_negative_hop() -> None:
    basis = (
        QuadraticBasisElement("h0<-1", "hop", 0, 1, quadratic_term(2, "hop", 0, 1)),
        QuadraticBasisElement("h1<-0", "hop", 1, 0, quadratic_term(2, "hop", 1, 0)),
    )
    system = compile_metzler_system(sp.eye(4), basis, parity_indices(2))
    assert verify_exact_metzler(system, (sp.Integer(1), sp.Integer(2)))
    assert not verify_exact_metzler(system, (sp.Integer(-1), sp.Integer(2)))


def test_compiler_drops_only_identically_zero_constraint_rows() -> None:
    basis = (
        QuadraticBasisElement("n0", "hop", 0, 0, quadratic_term(2, "hop", 0, 0)),
    )
    system = compile_metzler_system(sp.eye(4), basis, parity_indices(2))
    assert system.coefficients.rows == 0
    assert system.rows == ()


def test_exact_sign_decision_handles_q_sqrt_two() -> None:
    from oracle.metzler_system import exact_nonnegative

    assert exact_nonnegative(-1 + sp.sqrt(2))
    assert exact_nonnegative(3 - 2 * sp.sqrt(2))
    assert not exact_nonnegative(1 - sp.sqrt(2))
```

- [ ] **Step 2: Run and verify import failure**

```bash
PYTHONPATH=. python -m pytest tests/test_metzler_system.py -q
```

Expected: `oracle.metzler_system` is missing.

- [ ] **Step 3: Implement sparse exact conjugation**

For each basis element compute `transform * element.fock * transform.T`.
For every ordered off-diagonal pair within even and odd blocks, collect one
row across all basis elements. Drop a row only when every exact coefficient
simplifies to zero. Store row provenance before converting to a SymPy
immutable sparse matrix.

Implement `exact_nonnegative` by expanding every value as
`a + b*sqrt(2)` with rational `a,b`. Decide equal-sign cases immediately. In
the mixed-sign cases compare the exact rationals `a*a` and `2*b*b`, reversing
the answer according to which coefficient is negative. Raise `ValueError`
rather than guessing when the residual after subtracting
`a + b*sqrt(2)` is nonzero or either coefficient is not rational.

- [ ] **Step 4: Cross-check exact and float systems**

Add this test after the minimal implementation:

```python
def test_six_mode_compiler_float_values_match_direct_conjugation() -> None:
    from oracle.klein_hodge import overlap_klein_circuit
    from oracle.overlap_klein import quadratic_basis

    basis = quadratic_basis("number-conserving", "rings-bridges")
    transform = overlap_klein_circuit()
    system = compile_metzler_system(transform, basis, parity_indices(6))
    rng = np.random.default_rng(20260728)
    coefficients = rng.normal(size=len(basis))
    direct = np.array(
        (transform * sum(
            (sp.Float(value) * item.fock for value, item in zip(coefficients, basis)),
            sp.zeros(64),
        ) * transform.T).tolist(),
        dtype=float,
    )
    compiled = numeric_coefficients(system) @ coefficients
    observed = np.array(
        [direct[row.target_state, row.source_state] for row in system.rows]
    )
    assert np.allclose(compiled, observed, atol=1e-12)
```

- [ ] **Step 5: Run focused and baseline tests**

```bash
PYTHONPATH=. python -m pytest tests/test_metzler_system.py -q
PYTHONPATH=. python -m pytest tests -q
```

- [ ] **Step 6: Commit and push**

```bash
git add tracks/qmc/solutions/no-negative-vibes/oracle/metzler_system.py \
        tracks/qmc/solutions/no-negative-vibes/tests/test_metzler_system.py
git commit -m "feat: compile exact parity Metzler systems"
git push shared work/zibo/representation-cones
```

---

### Task 5: Anchored LP and exact primal/dual certificate replay

**Files:**

- Modify: `tracks/qmc/solutions/no-negative-vibes/oracle/overlap_klein.py`
- Modify: `tracks/qmc/solutions/no-negative-vibes/tests/test_overlap_klein.py`

**Interfaces:**

- Consumes: `ExactMetzlerSystem`.
- Produces:
  - immutable `AnchorSolve(label, sign, status, coefficients, min_slack, message)`
  - immutable `ExactPrimalCertificate(anchor_label, anchor_sign, coefficients)`
  - immutable `ExactDualCertificate(anchor_label, plus_weights, minus_weights)`
  - `solve_anchor(system, anchor_label: str, sign: int) -> AnchorSolve`
  - `reconstruct_exact_primal(system, solve, max_denominator=10000) -> ExactPrimalCertificate`
  - `find_zero_dual(system, anchor_label: str) -> ExactDualCertificate`
  - `verify_primal(system, certificate) -> bool`
  - `verify_zero_dual(system, certificate) -> bool`
  - `certificate_to_json(certificate) -> dict[str, object]`
  - `certificate_from_json(payload, system) -> ExactPrimalCertificate | ExactDualCertificate`

- [ ] **Step 1: Write failing synthetic cone tests**

```python
import sympy as sp

from oracle.metzler_system import ExactMetzlerSystem, MetzlerRow
from oracle.overlap_klein import (
    find_zero_dual,
    reconstruct_exact_primal,
    solve_anchor,
    verify_primal,
    verify_zero_dual,
)


def _system(coefficients: list[list[int]]) -> ExactMetzlerSystem:
    rows = tuple(
        MetzlerRow("even", index + 1, 0)
        for index in range(len(coefficients))
    )
    return ExactMetzlerSystem(
        labels=("x", "y"),
        rows=rows,
        coefficients=sp.ImmutableSparseMatrix(coefficients),
    )


def test_anchor_solver_and_exact_primal_replay() -> None:
    system = _system([[1, 0], [0, 1]])
    solve = solve_anchor(system, "x", +1)
    assert solve.status == "feasible"
    certificate = reconstruct_exact_primal(system, solve)
    assert verify_primal(system, certificate)
    assert certificate.coefficients[0] == 1


def test_dual_certificate_proves_anchor_is_identically_zero() -> None:
    system = _system([[1, 0], [-1, 0], [0, 1]])
    assert solve_anchor(system, "x", +1).status == "infeasible"
    assert solve_anchor(system, "x", -1).status == "infeasible"
    certificate = find_zero_dual(system, "x")
    assert verify_zero_dual(system, certificate)
```

- [ ] **Step 2: Run and verify missing interfaces**

```bash
PYTHONPATH=. python -m pytest tests/test_overlap_klein.py -q
```

Expected: import errors for the LP/certificate functions.

- [ ] **Step 3: Implement unbounded anchored feasibility**

Solve:

```text
C x >= 0
e_anchor^T x = sign
```

with `linprog(c=zeros, A_ub=-C, b_ub=0, A_eq=e_anchor,
b_eq=[sign], bounds=[(None,None)]*n, method="highs")`. Do not impose a
coefficient box in the feasibility decision. Record
`min(C @ x)` and reject a nominal success when it is below `-1e-9`.

Reconstruct each coefficient with:

```python
sp.nsimplify(value, [sp.sqrt(2)], tolerance=1e-10, full=True)
```

Force the anchor to exact `+1` or `-1` and verify every exact inequality.
Failure to reconstruct raises `ArithmeticError`; it does not silently downgrade
to an exact certificate.

- [ ] **Step 4: Implement the double-dual zero proof**

To prove `x_anchor == 0` on `{x: Cx>=0}`, find nonnegative vectors `y+` and
`y-` satisfying:

```text
C.T y+ =  e_anchor
C.T y- = -e_anchor.
```

Discover supports with HiGHS and reconstruct positive weights over
`Q(sqrt(2))`. Verify exact equality and exact nonnegativity. Serialize SymPy
numbers with `sp.sstr`; parse only the generated grammar with
`sp.sympify(value, locals={"sqrt": sp.sqrt})`.

- [ ] **Step 5: Add JSON round-trip tests**

```python
def test_exact_certificate_json_round_trip() -> None:
    system = _system([[1, 0], [0, 1]])
    certificate = reconstruct_exact_primal(system, solve_anchor(system, "x", +1))
    payload = certificate_to_json(certificate)
    replayed = certificate_from_json(payload, system)
    assert replayed == certificate
    assert verify_primal(system, replayed)
```

- [ ] **Step 6: Run focused and baseline tests**

```bash
PYTHONPATH=. python -m pytest tests/test_overlap_klein.py -q
PYTHONPATH=. python -m pytest tests -q
```

- [ ] **Step 7: Commit and push**

```bash
git add tracks/qmc/solutions/no-negative-vibes/oracle/overlap_klein.py \
        tracks/qmc/solutions/no-negative-vibes/tests/test_overlap_klein.py
git commit -m "feat: certify anchored Klein cone feasibility"
git push shared work/zibo/representation-cones
```

---

### Task 6: Versioned R01 runner and deterministic protocol

**Files:**

- Modify: `tracks/qmc/solutions/no-negative-vibes/oracle/overlap_klein.py`
- Modify: `tracks/qmc/solutions/no-negative-vibes/tests/test_overlap_klein.py`
- Create: `tracks/qmc/solutions/no-negative-vibes/protocols/overlap-klein-v1/README.md`
- Create: `tracks/qmc/solutions/no-negative-vibes/protocols/overlap-klein-v1/settings.json`
- Create: `tracks/qmc/solutions/no-negative-vibes/protocols/overlap-klein-v1/axes.json`
- Create: `tracks/qmc/solutions/no-negative-vibes/protocols/overlap-klein-v1/provenance.json`

**Interfaces:**

- Produces:
  - `build_system(family: str, mask: str) -> ExactMetzlerSystem`
  - `run_anchor_scan(family, mask, *, workers, source_commit) -> dict[str, object]`
  - `write_result(payload, output: pathlib.Path) -> None`
  - `main() -> None`
- CLI:

```text
python -m oracle.overlap_klein
  --family {number-conserving,bdg}
  --mask {rings-bridges,rings-diagonals-bridges}
  --workers INTEGER
  --source-commit 40_HEX
  --output PATH
```

- [ ] **Step 1: Write failing deterministic runner tests**

```python
def test_anchor_scan_is_deterministic_across_worker_counts() -> None:
    one = run_anchor_scan(
        "number-conserving",
        "rings-bridges",
        workers=1,
        source_commit="a" * 40,
    )
    two = run_anchor_scan(
        "number-conserving",
        "rings-bridges",
        workers=2,
        source_commit="a" * 40,
    )
    assert one == two
    assert one["schema_version"] == 1
    assert one["protocol"] == "overlap-klein-v1"
    assert one["source_commit"] == "a" * 40
    assert one["anchor_count"] == len(bridge_labels("number-conserving"))


def test_result_payload_contains_replayable_terminal_evidence() -> None:
    result = run_anchor_scan(
        "number-conserving",
        "rings-bridges",
        workers=1,
        source_commit="b" * 40,
    )
    for anchor in result["anchors"]:
        assert set(anchor) >= {"label", "positive", "negative", "classification"}
        assert set(anchor["positive"]) >= {"status", "solver_message"}
        assert set(anchor["negative"]) >= {"status", "solver_message"}
        assert anchor["classification"] in {
            "certified-feasible",
            "certified-zero",
            "numerical-only",
        }
```

- [ ] **Step 2: Run and verify missing runner**

```bash
PYTHONPATH=. python -m pytest tests/test_overlap_klein.py -q
```

- [ ] **Step 3: Implement deterministic process-level parallelism**

Compile the system once in the parent. Submit one `(anchor_label, sign)` solve
per process with `ProcessPoolExecutor`. Sort results by the order in
`bridge_labels`, never completion order. For each anchor:

- if either sign has an exact primal, classify `certified-feasible`;
- if both signs are infeasible and the double dual verifies, classify
  `certified-zero`;
- otherwise classify `numerical-only` and retain solver diagnostics without a
  scientific conclusion.

Record system shape, exact coefficient field `Q(sqrt(2))`, transform convention,
geometry, package versions, worker count, wall time, and certificate payloads.
Each sign record contains its own exact primal certificate when reconstructed.
A `certified-zero` anchor instead contains one `zero_certificate` with the two
exact conic dual identities; do not collapse two feasible signs into one
ambiguous certificate field.

- [ ] **Step 4: Write the preregistered protocol files**

`settings.json` must contain:

```json
{
  "schema_version": 1,
  "protocol": "overlap-klein-v1",
  "modes": 6,
  "blocks": [[0, 1, 2, 3], [2, 3, 4, 5]],
  "families": ["number-conserving", "bdg"],
  "masks": ["rings-bridges", "rings-diagonals-bridges"],
  "anchor_signs": [-1, 1],
  "exact_field": "Q(sqrt(2))",
  "blas_threads": 1,
  "worker_policy": "max(1, logical_cpus-2)"
}
```

`axes.json` lists the four family/mask cells in deterministic order.
`provenance.json` cites design commit `b0d40ff`, common baseline `04e72bd`, and
the design/candidate-card paths. `README.md` explains success/failure semantics
and states that `numerical-only` is not a conclusion.

- [ ] **Step 5: Run focused and baseline tests**

```bash
PYTHONPATH=. python -m pytest tests/test_overlap_klein.py -q
PYTHONPATH=. python -m pytest tests -q
```

- [ ] **Step 6: Commit and push before any experiment**

```bash
git add tracks/qmc/solutions/no-negative-vibes/oracle/overlap_klein.py \
        tracks/qmc/solutions/no-negative-vibes/tests/test_overlap_klein.py \
        tracks/qmc/solutions/no-negative-vibes/protocols/overlap-klein-v1
git commit -m "feat: preregister overlapping Klein cone protocol"
git push shared work/zibo/representation-cones
```

---

### Task 7: Experiment R01-E001 — number-conserving six-mode gate

**Files:**

- Modify: `tracks/qmc/solutions/no-negative-vibes/docs/EXPERIMENT_LOG.md`
- Create after run: ignored raw results under
  `tracks/qmc/results/no-negative-vibes/overlap-klein-v1/`
- Create after interpretation: `tracks/qmc/solutions/no-negative-vibes/fixtures/overlap_klein_r01.json`
- Modify: `tracks/qmc/solutions/no-negative-vibes/tests/test_overlap_klein.py`

**Interfaces:**

- Consumes: Task 6 CLI and protocol.
- Produces: first exact number-conserving result, fixture replay, and log entry
  `R01-E001`.

- [ ] **Step 1: Transfer the exact source commit to the WSL worker**

Push the branch first. If worker GitHub access fails twice, create and verify a
Git bundle for the exact branch, transfer it over the authenticated SSH hop,
and fetch it into the isolated worker clone. Verify:

```bash
git rev-parse HEAD
git status --short
```

Expected: the exact pushed commit and an empty status.

- [ ] **Step 2: Run a matching one-worker smoke for each production cell**

From the solution directory:

```bash
SOURCE_COMMIT="$(git rev-parse HEAD)"
OMP_NUM_THREADS=1 MKL_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 PYTHONPATH=. \
python -m oracle.overlap_klein \
  --family number-conserving \
  --mask rings-bridges \
  --workers 1 \
  --source-commit "$SOURCE_COMMIT" \
  --output ../../results/no-negative-vibes/overlap-klein-v1/R01-E001-smoke-rings-bridges-attempt-01.json

OMP_NUM_THREADS=1 MKL_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 PYTHONPATH=. \
python -m oracle.overlap_klein \
  --family number-conserving \
  --mask rings-diagonals-bridges \
  --workers 1 \
  --source-commit "$SOURCE_COMMIT" \
  --output ../../results/no-negative-vibes/overlap-klein-v1/R01-E001-smoke-rings-diagonals-bridges-attempt-01.json
```

Verify that `SOURCE_COMMIT` is the same value already checked before the run;
do not use a branch name as provenance.  A smoke is valid only for the same
family, mask, and source commit as its production cell.  Use a new
`attempt-NN` path for every retry because the atomic writer otherwise replaces
an existing result.

Expected operational result for both smokes: exit code zero, every anchor
classified, no solver branch has `status="error"`, and every embedded exact
certificate replays.  The scientific classification is intentionally
determined by the run.

- [ ] **Step 3: Run the full number-conserving mask pair**

Use 14 WSL workers:

```bash
SOURCE_COMMIT="$(git rev-parse HEAD)"
OMP_NUM_THREADS=1 MKL_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 PYTHONPATH=. \
python -m oracle.overlap_klein \
  --family number-conserving \
  --mask rings-bridges \
  --workers 14 \
  --source-commit "$SOURCE_COMMIT" \
  --output ../../results/no-negative-vibes/overlap-klein-v1/R01-E001-rings-bridges-attempt-01.json

OMP_NUM_THREADS=1 MKL_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 PYTHONPATH=. \
python -m oracle.overlap_klein \
  --family number-conserving \
  --mask rings-diagonals-bridges \
  --workers 14 \
  --source-commit "$SOURCE_COMMIT" \
  --output ../../results/no-negative-vibes/overlap-klein-v1/R01-E001-rings-diagonals-bridges-attempt-01.json
```

The two cells are distinct experiments within `R01-E001`; do not also send
them to the CPU worker.  For each cell, require equality of the complete
scientific payload between its one-worker smoke and production result after
removing only the top-level `execution` object.

- [ ] **Step 4: Add fixture replay before interpretation**

Copy only compact exact certificates, classifications, raw-result hashes, and
reproducibility metadata into `fixtures/overlap_klein_r01.json`.  The compact
fixture schema intentionally renames raw branch field
`exact_primal_certificate` to `certificate`; make that conversion explicit
rather than treating the raw and fixture schemas as identical.  Add coverage
and replay tests:

```python
def test_r01_fixture_covers_both_number_conserving_cells_without_duplicates() -> None:
    payload = json.loads(FIXTURE_PATH.read_text(encoding="utf-8"))
    cells = [
        cell for cell in payload["cells"]
        if cell["family"] == "number-conserving"
    ]
    assert [cell["mask"] for cell in cells] == [
        "rings-bridges",
        "rings-diagonals-bridges",
    ]
    for cell in cells:
        system = build_system(cell["family"], cell["mask"])
        expected_labels = bridge_labels(cell["family"])
        assert cell["system_shape"] == list(system.coefficients.shape)
        assert cell["anchor_count"] == len(expected_labels)
        assert [anchor["label"] for anchor in cell["anchors"]] == expected_labels


def test_r01_fixture_classifications_are_consistent_and_all_certificates_replay() -> None:
    payload = json.loads(FIXTURE_PATH.read_text(encoding="utf-8"))
    cells = [
        cell for cell in payload["cells"]
        if cell["family"] == "number-conserving"
    ]
    assert len(cells) == 2
    for cell in cells:
        system = build_system(cell["family"], cell["mask"])
        for anchor in cell["anchors"]:
            if anchor["classification"] == "certified-feasible":
                replayed = 0
                for sign_name in ("positive", "negative"):
                    branch = anchor[sign_name]
                    if "certificate" in branch:
                        certificate = certificate_from_json(branch["certificate"], system)
                        assert verify_primal(system, certificate)
                        assert certificate.anchor_label == anchor["label"]
                        assert certificate.anchor_sign == (
                            1 if sign_name == "positive" else -1
                        )
                        replayed += 1
                assert replayed >= 1
            elif anchor["classification"] == "certified-zero":
                assert anchor["positive"]["status"] == "infeasible"
                assert anchor["negative"]["status"] == "infeasible"
                certificate = certificate_from_json(anchor["zero_certificate"], system)
                assert verify_zero_dual(system, certificate)
                assert certificate.anchor_label == anchor["label"]
            elif anchor["classification"] == "numerical-only":
                assert "zero_certificate" not in anchor
            else:
                raise AssertionError(anchor["classification"])
```

- [ ] **Step 5: Record the result and transferable lesson**

Append `R01-E001` with source commit, commands, CPU/RAM/workers, system
dimensions, every anchor classification, certificate paths, interpretation,
and next decision.  Record every smoke and production path plus SHA-256,
package versions, and the scientific-payload equality check.  Record failed
attempts even when no JSON was produced.  State explicitly, for every directed
bridge and each anchor sign, whether cross-cluster hopping survives; do not
promote a single feasible anchor into a claim about the full Hermitian
Hamiltonian, an open cone, or a positive-coefficient HS decomposition.

- [ ] **Step 6: Verify, commit, and push the interpreted experiment**

```bash
PYTHONPATH=. python -m pytest tests/test_overlap_klein.py -q
PYTHONPATH=. python -m pytest tests -q
git add tracks/qmc/solutions/no-negative-vibes/fixtures/overlap_klein_r01.json \
        tracks/qmc/solutions/no-negative-vibes/tests/test_overlap_klein.py \
        tracks/qmc/solutions/no-negative-vibes/docs/EXPERIMENT_LOG.md \
        tracks/qmc/solutions/no-negative-vibes/docs/RESEARCH_OPERATIONS.md
git commit -m "research: record six-mode number-conserving Klein result"
git push shared work/zibo/representation-cones
```

---

### Task 8: Experiment R01-E002 — BdG pairing extension and CPU split

**Files:**

- Modify: `tracks/qmc/solutions/no-negative-vibes/fixtures/overlap_klein_r01.json`
- Modify: `tracks/qmc/solutions/no-negative-vibes/tests/test_overlap_klein.py`
- Modify: `tracks/qmc/solutions/no-negative-vibes/docs/EXPERIMENT_LOG.md`
- Modify when needed: `tracks/qmc/solutions/no-negative-vibes/docs/RESEARCH_OPERATIONS.md`

**Interfaces:**

- Consumes: exact number-conserving evidence and BdG system.
- Produces: exact BdG bridge survival/no-go result `R01-E002`.

- [ ] **Step 1: Freeze one source commit and synchronize both workers**

Do not start E002 until the interpreted E001 commit is on the shared branch
and the Task 8 evidence-protocol amendment is also committed and pushed.
Freeze that resulting full 40-hex commit as `TASK8_SOURCE_COMMIT`; do not let
each host independently choose its current branch tip.

Create a complete Git bundle for the pinned branch, verify it, and record its
SHA-256.  Transfer it over the authenticated Windows-to-WSL hop and then the
strict-host-key WSL-to-CPU hop.  Fast-forward both isolated clones and require:

```text
WSL HEAD == CPU HEAD == TASK8_SOURCE_COMMIT
both worktrees clean
```

Probe CPU readiness through WSL without a scientific job.  Record only the
public resource facts in the experiment log:

```text
logical CPU count
available RAM
OS/Python/SciPy/SymPy versions
scheduler = plain SSH or detected scheduler
```

The environment was already bootstrapped in `ENV-0004`; do not reinstall it
when the BatchMode key, pinned clone, and dedicated Python remain healthy.
If key authentication is not configured, stop CPU setup without embedding the
password in a command, file, environment variable, or log. Run R01-E002 on WSL
instead; lack of the second worker does not block this small exact experiment.
In that fallback, WSL must run the larger mask's own workers=1 smoke before its
production cell; the CPU-assigned smoke is not skipped.

- [ ] **Step 2: Run a matching one-worker smoke on each assigned host**

The WSL smoke owns `bdg/rings-bridges`:

```bash
set -euo pipefail
TASK8_SOURCE_COMMIT="<replace-with-the-pinned-full-40-hex-commit>"
SOURCE_COMMIT="$TASK8_SOURCE_COMMIT"
test "$(git -C /home/zibojin/code/nnv-zibo rev-parse HEAD)" = "$SOURCE_COMMIT"
OMP_NUM_THREADS=1 MKL_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 \
PYTHONPATH=/home/zibojin/code/nnv-zibo/tracks/qmc/solutions/no-negative-vibes \
/home/zibojin/miniforge3/envs/quantum_harness/bin/python \
  -m oracle.overlap_klein \
  --family bdg \
  --mask rings-bridges \
  --workers 1 \
  --source-commit "$SOURCE_COMMIT" \
  --output /home/zibojin/code/nnv-zibo/tracks/qmc/results/no-negative-vibes/overlap-klein-v1/R01-E002-smoke-rings-bridges-attempt-01.json
```

The CPU smoke owns `bdg/rings-diagonals-bridges` and runs from its solution
directory with its dedicated Python:

```bash
set -euo pipefail
TASK8_SOURCE_COMMIT="<replace-with-the-pinned-full-40-hex-commit>"
SOURCE_COMMIT="$TASK8_SOURCE_COMMIT"
test "$(git -C /home/jzb/code/nnv-zibo rev-parse HEAD)" = "$SOURCE_COMMIT"
OMP_NUM_THREADS=1 MKL_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 \
PYTHONPATH=/home/jzb/code/nnv-zibo/tracks/qmc/solutions/no-negative-vibes \
/home/jzb/miniforge3/envs/quantum-harness/bin/python \
  -m oracle.overlap_klein \
  --family bdg \
  --mask rings-diagonals-bridges \
  --workers 1 \
  --source-commit "$SOURCE_COMMIT" \
  --output /home/jzb/code/nnv-zibo/tracks/qmc/results/no-negative-vibes/overlap-klein-v1/R01-E002-smoke-rings-diagonals-bridges-attempt-01.json
```

These distinct smokes may run concurrently.  Verify exit status, exact pinned
source/family/mask, no `status="error"`, and every embedded primal/double-dual
certificate before production.  Use a new `attempt-NN` path for any retry and
record a failed attempt even when no JSON was produced.  If CPU readiness
failed, replace only the CPU paths/interpreter above with their WSL absolute
counterparts and run this larger-mask smoke on WSL before proceeding.

- [ ] **Step 3: Run the disjoint production pair**

Only after both matching smokes pass:

- WSL runs `bdg/rings-bridges` with 14 workers;
- CPU runs `bdg/rings-diagonals-bridges` with
  `max(1,logical_cpus-2)` workers.

If it is not ready, WSL runs both cells sequentially. Never run the same
production cell on both machines unless the protocol is explicitly changed to
independent verification.

On each assigned worker, from the solution directory, run the corresponding
command:

```bash
set -euo pipefail
TASK8_SOURCE_COMMIT="<replace-with-the-pinned-full-40-hex-commit>"
SOURCE_COMMIT="$TASK8_SOURCE_COMMIT"
test "$(git -C /home/zibojin/code/nnv-zibo rev-parse HEAD)" = "$SOURCE_COMMIT"
OMP_NUM_THREADS=1 MKL_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 \
PYTHONPATH=/home/zibojin/code/nnv-zibo/tracks/qmc/solutions/no-negative-vibes \
/home/zibojin/miniforge3/envs/quantum_harness/bin/python \
  -m oracle.overlap_klein \
  --family bdg \
  --mask rings-bridges \
  --workers 14 \
  --source-commit "$SOURCE_COMMIT" \
  --output /home/zibojin/code/nnv-zibo/tracks/qmc/results/no-negative-vibes/overlap-klein-v1/R01-E002-rings-bridges-attempt-01.json
```

For the CPU worker, set `CPU_WORKERS` to exactly two fewer than the probed
logical CPU count:

```bash
set -euo pipefail
TASK8_SOURCE_COMMIT="<replace-with-the-pinned-full-40-hex-commit>"
SOURCE_COMMIT="$TASK8_SOURCE_COMMIT"
test "$(git -C /home/jzb/code/nnv-zibo rev-parse HEAD)" = "$SOURCE_COMMIT"
CPU_PYTHON=/home/jzb/miniforge3/envs/quantum-harness/bin/python
CPU_WORKERS="$("$CPU_PYTHON" -c 'import os; print(max(1, (os.cpu_count() or 1) - 2))')"
OMP_NUM_THREADS=1 MKL_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 \
PYTHONPATH=/home/jzb/code/nnv-zibo/tracks/qmc/solutions/no-negative-vibes \
"$CPU_PYTHON" -m oracle.overlap_klein \
  --family bdg \
  --mask rings-diagonals-bridges \
  --workers "$CPU_WORKERS" \
  --source-commit "$SOURCE_COMMIT" \
  --output /home/jzb/code/nnv-zibo/tracks/qmc/results/no-negative-vibes/overlap-klein-v1/R01-E002-rings-diagonals-bridges-attempt-01.json
```

In the CPU-unavailable fallback, run this larger-mask production on WSL with
the WSL absolute clone/interpreter/output paths and `--workers 14`, only after
the matching larger-mask workers=1 WSL smoke has passed.

For each host-local smoke/production pair, remove only the top-level
`execution` object and require the complete remaining payloads to be equal.
Do not drop package versions, solver diagnostics, source commit,
classifications, or certificates from this comparison.

- [ ] **Step 4: Return all four raw files with end-to-end hashes**

Validate and SHA-256 hash all four generated raws in place.  In the normal
split, this means two WSL raws plus two CPU raws: copy the CPU pair into WSL
using unique `.part` destinations, recompute the hash, and atomically rename
only after it matches.  In the CPU-unavailable fallback, all four raws are
already on WSL, so skip the nonexistent CPU hop.  In either route, copy all
four WSL-held raws through the outer Windows gateway and into the local
ignored results tree, again using `.part`, recomputing SHA-256 at every hop,
and atomically renaming only after a match.  A transfer mismatch is an
operational failure; preserve the source raw and failed `.part` and never
overwrite a previously named attempt.

- [ ] **Step 5: Migrate the fixture schema and replay BdG evidence**

Before creating E002 data, add RED tests that require exactly two ordered BdG
cells, their expected labels/shapes, both raw roles/hashes/worker counts,
scientific-payload equality, terminal non-error branches, sign-local evidence,
and exact replay of every certificate.

The E001 fixture has one top-level experiment/source/package record, which
cannot correctly describe E002 or two software hosts.  Migrate to
`fixture_schema_version=2`:

```text
protocol: overlap-klein-v1
experiments:
  - experiment_id: R01-E001
    source_commit: 24c80c4e1c1f182278e799b7f5de53deb65bf2f4
    cells: [...]
  - experiment_id: R01-E002
    source_commit: TASK8_SOURCE_COMMIT
    cells: [...]
```

Store package versions and public host role per cell (or per raw pair), not as
one false cross-host constant.  Preserve every `numerical-only` diagnostic but
do not use it for a theorem.  If one sign has an exact primal while the other
is merely numerically infeasible, report the latter as unresolved rather than
as an exact one-sided exclusion.

The migration test must also require exactly the original two E001
number-conserving cells with their full source commit
`24c80c4e1c1f182278e799b7f5de53deb65bf2f4`, raw hashes, classifications, and
replaying exact certificates.  The v2 fixture contains exactly two
experiments with two cells each; migration must not weaken or silently drop
the already reviewed E001 evidence.

Use the exact inclusion `K_NC -> K_BdG` as a consistency check.  Since E001
proved every number-conserving bridge zero, a BdG hopping primal may survive
only with at least one nonzero pairing coefficient; an all-zero-pairing
hopping witness is a hard contradiction.  Distinguish hopping anchors from
pair-creation/pair-annihilation anchors.  Do not infer a Hermitian Hamiltonian
from separate directed survivors; a later functional-anchor test must impose
the hopping adjoint pair or `pc=pa` in one common cone element.

- [ ] **Step 6: Record, verify on both hosts, commit, and push R01-E002**

Append the full experiment schema and the lesson that distinguishes hopping
from pair-creation/pair-annihilation bridges.  Record every scientific and
operational attempt, source/bundle/raw hashes, machine assignment, all
anchor/sign evidence, strict claim scope, and next decision.  Run focused and
full tests on WSL and the committed fixture replay tests on CPU.

The distributed verification order is:

1. locally construct and preflight the fixture/tests/docs;
2. commit the candidate tracked state **without pushing**;
3. create, verify, and hash a complete bundle for that exact candidate commit;
4. fast-forward clean WSL and CPU clones to the same candidate commit;
5. run the WSL focused/full suites and CPU committed fixture replay tests;
6. if either host fails, fix locally in a new commit and repeat the
   bundle/synchronization/tests;
7. only after both hosts pass, push the exact verified commit.

Then publish the verified result:

```bash
set -euo pipefail
VERIFIED_CANDIDATE_COMMIT="<replace-with-the-full-40-hex-commit-tested-on-both-hosts>"
test -z "$(git status --short)"
test "$(git rev-parse HEAD)" = "$VERIFIED_CANDIDATE_COMMIT"
git push shared work/zibo/representation-cones
```

---

### Task 9: Exact fixture classifier and fixed-structure bridge no-go

**Task 9 base:** start only from the reviewed and shared Task 8 candidate
`408266c3c85bc8466683364f545a16e0d79559f0`. Do not run a new scientific
scan. Task 9 aggregates and exactly replays the committed R01 evidence.

**Files:**

- Modify:
  `tracks/qmc/solutions/no-negative-vibes/oracle/overlap_klein.py`
- Modify:
  `tracks/qmc/solutions/no-negative-vibes/tests/test_overlap_klein.py`
- Create:
  `tracks/qmc/solutions/no-negative-vibes/docs/OVERLAPPING_KLEIN_RESULTS.md`
- Modify:
  `tracks/qmc/solutions/no-negative-vibes/docs/EXPERIMENT_LOG.md`
- Modify `docs/RESEARCH_OPERATIONS.md` only if a genuinely new reusable
  operational lesson appears.

The fixture and all ignored raw JSON files are read-only. Task 10, not Task 9,
owns the proposal ledger, README, collaborator update, and protocol terminal
routing.

**Only public interface added in Task 9:**

```python
def classify_r01_fixture(
    payload: Mapping[str, object],
) -> dict[str, object]:
    """Validate and exactly classify the overlap-klein-v1 R01 fixture."""
```

The classifier must not mutate `payload`. Malformed schema, incomplete
registered coverage, inconsistent provenance/evidence, a missing required
exact certificate, or an exact replay failure raises `ValueError`.

Do **not** implement, export, or test the following survivor-only helpers on
the current all-zero fixture:

```text
certificate_operator
commutator_is_nonzero
support_graph_invariants
common_bilinear_forms
parity_word_trace_audit
```

The fixture contains no exact primal ray. A dual certificate lives in
inequality-row dual space and cannot be treated as a coefficient vector,
operator, or support graph. Therefore commutator, topology, common-form,
known-reduction, and word-trace audits are preempted, not failed.

The old common-form test was also vacuous: iterating over an empty result
checked nothing. If a future exact survivor justifies that helper, its initial
RED test must require a complete nonempty canonical basis, for example the
single generator `diag(1,-1)` returning exactly the nonsingular symmetric form
`[[0,1],[1,0]]`, with exact invariance and signature `(1,1)`.

**Branch gate:**

```text
validate fixture-v2 structure and complete registered anchor coverage
  |
  +-- any replayed exact F --> survivor-branch-required
  |                           (future survivor audits require a new amendment)
  |
  +-- no F, any N ----------> evidence-incomplete
  |
  +-- all 24 exact Z -------> exact-bridge-coordinate-no-go
```

Here `F` means `certified-feasible` with a replaying exact primal, `N` means
`numerical-only`, and `Z` means `certified-zero` with both signs infeasible
and one replaying exact double-dual certificate. The committed fixture has
2 experiments, 4 cells, 24 anchors, 24 `Z`, zero `F`, and zero `N`.

- [ ] **Step 1: Review and publish this plan amendment alone**

Have a fresh theory/spec reviewer check the branch gate, deferred interfaces,
certificate semantics, non-overclaim boundaries, TDD order, and dual-host
verification. Fix every finding, run `git diff --check`, then commit and push
only this plan:

```text
docs: amend Task 9 for the exact no-go branch
```

Confirm by read-only remote query that the shared topic branch resolves to the
exact amendment SHA before writing the RED tests.

- [ ] **Step 2: RED — specify the committed-fixture outcome**

Import `copy` and `classify_r01_fixture`. Add module-scoped fixtures that load
the JSON once and call the classifier on a deep copy once. The happy-path test
must require:

```python
{
    "outcome": "exact-bridge-coordinate-no-go",
    "fixture_schema_version": 2,
    "protocol": "overlap-klein-v1",
    "totals": {
        "experiments": 2,
        "cells": 4,
        "anchors": 24,
        "certified_zero": 24,
        "certified_feasible": 0,
        "numerical_only": 0,
        "dual_certificates": 24,
        "primal_certificates": 0,
    },
}
```

It must require the four ordered cell summaries:

```text
R01-E001 number-conserving rings-bridges
  [560,24]: h0<-4 h1<-5 h4<-0 h5<-1
R01-E001 number-conserving rings-diagonals-bridges
  [748,32]: h0<-4 h1<-5 h4<-0 h5<-1
R01-E002 bdg rings-bridges
  [1052,42]: h0<-4 h1<-5 h4<-0 h5<-1 pa0,4 pa1,5 pc0,4 pc1,5
R01-E002 bdg rings-diagonals-bridges
  [1456,58]: h0<-4 h1<-5 h4<-0 h5<-1 pa0,4 pa1,5 pc0,4 pc1,5
```

Every cell has an empty `unresolved_labels` list. The audits are exactly:

```python
{
    "noncommutativity": "not-applicable-no-bridge-primal",
    "topology": "preempted-by-exact-bridge-no-go",
    "known_reduction": "not-applicable-empty-survivor-set",
    "word_trace": "skipped-no-survivor-rays",
}
```

Forbid top-level keys `rays`, `operators`, `commutators`, `support_graph`,
`forms`, `word_traces`, and `known_mechanism`. The valid RED is the missing
`classify_r01_fixture` import, not an unrelated collection/environment error.
Keep this failure together with the fail-closed mutation failures in Step 3
before making the RED commit.

Add a non-mutation test that keeps the exact object passed to the classifier,
compares it with a pre-call deep copy after a successful return, and requires
equality. Passing a deep copy of the module fixture alone does not prove this
contract.

- [ ] **Step 3: RED — specify fail-closed mutation behavior**

All mutations use `copy.deepcopy`; never write the committed fixture. Tests
must prove structural rejection happens before `build_system` for:

- missing/extra/duplicate or reordered registered anchors;
- wrong anchor kind;
- wrong experiment/source commit/family/mask/system shape;
- wrong transform/exact field/schema/protocol;
- wrong raw path, SHA, host role, role order, workers, packages, BLAS strings,
  spawn method, payload-equality flag, or nonpositive wall time;
- `certified-zero` without both infeasible statuses or a dual-shaped
  `zero_certificate`;
- `certified-feasible` without at least one sign-local exact primal payload;
- `numerical-only` carrying a zero certificate.

Also require:

- replacing the first `Z` by well-formed `N` returns only
  `evidence-incomplete` and does not call `build_system`;
- corrupting the first double dual raises an exact replay error;
- a false or sign-mismatched primal raises rather than becoming a survivor.

Add a fast instrumented call-count test with monkeypatched shape-compatible
systems and parsed-certificate objects. On the all-`Z` fixture it must observe
exactly four `build_system` calls (one per ordered cell) and exactly 24
`certificate_from_json` calls (one per dual), with no direct
`verify_zero_dual`/`verify_primal` calls. This protects the single-replay
architecture without adding a second expensive exact replay to the normal
module run.

Run the happy-path and every mutation node while the public interface is still
absent. Preserve the valid missing-interface failure for the complete RED
surface, then commit all RED tests together:

```text
test: specify exact R01 no-go classification
```

The structural pass pins exactly:

```text
R01-E001 @ 24c80c4e1c1f182278e799b7f5de53deb65bf2f4
R01-E002 @ d42786ae8a47899c90ac4811424c66aad2910713
```

and the reviewed fixture-v2 metadata for all eight raw records: exact relative
path and byte SHA-256, WSL/CPU public host role, smoke then production, workers
`1/14`, `1/14`, `1/14`, `1/62`, package versions
`numpy=2.4.6`, `scipy=1.17.1`, `sympy=1.14.0`, `oracle=0.1.0`, all three BLAS
thread strings `"1"`, process start method `spawn`, and positive exact stored
wall times. This is a structural classification gate; Task 8's
`oracle.r01_evidence` remains the byte/raw-content validation gate.

- [ ] **Step 4: GREEN — implement one structural path and one replay path**

Add private immutable expected metadata and private helpers in
`overlap_klein.py`. Before compiling any system, validate the complete
classification pattern and select `N`, `F`, or all-`Z`.

- `N` branch returns only outcome/schema/protocol and the ordered unresolved
  experiment/family/mask/label records. It does not report verified-zero
  totals because those other duals were intentionally not replayed.
- `F` branch parses every returned sign-local primal exactly once and returns
  `survivor-branch-required`, `replayed_primals`, and unresolved records.
  Fixture input and returned JSON both use the sign-local key `certificate`;
  do not substitute the legacy key `exact_primal_certificate` or return
  dataclass/SymPy objects. A mere `certified-feasible` string is never
  sufficient.
- all-`Z` builds each `(family, mask)` system once, checks its stored shape,
  parses every double dual once, and returns the exact no-go summary.

The alternate outputs are exactly:

```python
{
    "outcome": "evidence-incomplete",
    "fixture_schema_version": 2,
    "protocol": "overlap-klein-v1",
    "unresolved": [
        {
            "experiment_id": str,
            "family": str,
            "mask": str,
            "label": str,
        },
    ],
}
```

and:

```python
{
    "outcome": "survivor-branch-required",
    "fixture_schema_version": 2,
    "protocol": "overlap-klein-v1",
    "replayed_primals": [
        {
            "experiment_id": str,
            "family": str,
            "mask": str,
            "label": str,
            "sign": int,  # exactly +1 or -1
            "certificate": Mapping[str, object],
        },
    ],
    "unresolved": [
        {
            "experiment_id": str,
            "family": str,
            "mask": str,
            "label": str,
        },
    ],
}
```

`certificate_from_json` already verifies the exact identity. Do not call
`verify_zero_dual` or `verify_primal` again after it succeeds. Check the parsed
type, anchor label, and sign binding. Do not create zero rays or invoke any
deferred audit.

Refactor
`test_r01_fixture_classifications_are_consistent_and_all_certificates_replay`
to consume the same module-scoped verified summary. One normal module run must
replay all 24 duals once, not twice.

Commit GREEN:

```text
research: classify the exact R01 bridge no-go
```

- [ ] **Step 5: Write the exact result document**

Create `OVERLAPPING_KLEIN_RESULTS.md` only after GREEN. It must contain:

1. status `exact-bridge-coordinate-no-go` and strict fixed scope;
2. transform `U = U_[2,3,4,5] U_[0,1,2,3]`, even/odd Fock convention,
   exact field `Q(sqrt(2))`, and fixed basis/label order;
3. the 2/4/24/24/0/0 evidence inventory and all four system shapes;
4. a per-coordinate table pointing to each fixture `zero_certificate`;
5. proof: for every registered coordinate `a`,
   `A^T y_+ = e_a`, `A^T y_- = -e_a`, and `y_+,y_- >= 0`, hence
   `x_a = 0` for every exact cone element;
6. the two-mask conclusions
   `projection_B_NC(K_NC(M)) = {0}` and
   `projection_B_BdG(K_BdG(M)) = {0}`;
7. Hermitian hopping and `pc=pa` corollaries because each directed coordinate
   is already zero;
8. coordinate-subcone monotonicity: additional exact coordinate restrictions
   inherit the result, but adding basis directions is not covered;
9. the four preempted audit statuses above;
10. physical consequence: close only this fixed six-mode `U_6` route, not the
    four-mode positive-coefficient HS target;
11. fixture/protocol/source/raw provenance and reproducibility commands.

The document must explicitly state that it does **not** prove:

- the whole cone is `{0}`;
- all feasible internal rays commute or lack graph topology;
- a split, contraction, Kramers, Majorana, MTR, or other known reduction;
- failure of another transform, support, basis, nonlinear micro-word,
  gauge/ancilla, `N=8`, general BdG, Hamiltonian, or HS construction.

Forbidden unqualified phrases include “full BdG no-go”, “all feasible rays
commute”, “no loop topology survives”, “not split”, “novel mechanism”, and
“dual weights are generator coefficients”.

The strongest terminal sentence is:

```text
For the fixed six-mode overlap_klein_circuit, exact field Q(sqrt(2)),
the tested real number-conserving/BdG basis spans, and the two preregistered
masks, every registered cross-cluster hopping/pairing coordinate vanishes
identically in the exact Metzler cone.
```

Record the exact aggregation and every implementation/replay attempt that
occurs before candidate freeze in `EXPERIMENT_LOG.md`. Commit the result
document/log after implementation and preserve the separate RED commit.
Post-freeze WSL/CPU/review evidence belongs to the ignored immutable Task 9
SDD report described below, so recording a successful final gate cannot
mutate the candidate it verifies.

- [ ] **Step 6: Freeze and verify the exact candidate on both hosts**

From the solution directory, with `PYTHONPATH=.` and all three BLAS thread
limits equal to `1`, run the new mutation nodes, then in one pytest process:

```bash
python -m pytest \
  tests/test_overlap_klein.py::test_r01_fixture_classifies_exact_bridge_coordinate_no_go \
  tests/test_overlap_klein.py::test_r01_fixture_classifications_are_consistent_and_all_certificates_replay \
  -q
```

Commit all tracked candidate changes and logs, require a clean worktree,
create/verify/hash a complete bundle, transfer it by unique `.part` paths, and
fast-forward the clean WSL and CPU clones to the exact candidate SHA.

Use detached status-last wrappers. WSL runs the focused Task 9 nodes and then
the full solution suite. CPU runs in one process:

```bash
python -m pytest \
  tests/test_overlap_klein.py::test_r01_fixture_classifies_exact_bridge_coordinate_no_go \
  tests/test_overlap_klein.py::test_r01_fixture_classifications_are_consistent_and_all_certificates_replay \
  tests/test_overlap_klein.py::test_r01_classifier_rejects_a_corrupted_exact_double_dual \
  -q
```

Require explicit zero exit codes, final pytest summaries, exact candidate
SHAs, clean remote worktrees, and hashes of final log/status files. A dropped
SSH connection is an operational attempt, not a verdict. Record every
post-freeze wrapper, transport, WSL/CPU test, and review attempt in an ignored
append-only Markdown report under
`.superpowers/sdd/2026-07-28-r01-overlapping-klein-cone/`, with hashes pointing
to the immutable remote log/status artifacts. If a failure requires a tracked
code, test, claim, or reusable-operations fix, first add that failure and fix
to the tracked Markdown, commit a new candidate, and restart both-host
verification. A successful final gate never causes a tracked edit.

- [ ] **Step 7: Independent final review and push**

A fresh reviewer must inspect the complete base-to-candidate diff and verify:

- only `classify_r01_fixture` was added; all five ray-only helpers are absent;
- structural validation precedes exact replay and the `N` shortcut;
- the four systems are built once and 24 duals replay once per normal module
  invocation;
- parser success is not followed by duplicate certificate verification;
- no dual is interpreted as a primal/operator/graph;
- fixture pointers, counts, shapes, commits, raw hashes, and claim scope;
- no secret, ignored raw, `.superpowers`, or `AGENT_HANDOFF.md` is tracked;
- WSL/CPU evidence belongs to the exact clean candidate.

Fix every finding and repeat all verification/review gates. Push only the
zero-finding candidate to `work/zibo/representation-cones`, then use a
read-only remote query to confirm the exact SHA. Do not merge internal PR #3,
touch the organizer branch, or update PR #178.

The ignored Task 9 report is the final verification manifest: it records all
post-freeze attempts, exact candidate and bundle SHA-256, WSL/CPU log/status
hashes, reviewer identity/verdict, push output, and read-only remote SHA.
This satisfies the Markdown experiment-memory requirement without creating
the self-invalidating cycle “test candidate -> edit tracked log -> retest”.

Task 9 hands Task 10 exactly this terminal state:

```text
falsified — for overlap-klein-v1's fixed six-mode transform and the tested
number-conserving/BdG basis spans on the two preregistered masks, exact
double-dual certificates force every registered cross-cluster coordinate to
zero.
```

It must not hand off `known-reduction`, `proof-candidate`,
`physical-candidate`, “all rays commute,” or “full BdG no-go.”

---

### Task 10: Close Plan A and route the next paper branch

**Files:**

- Modify: `tracks/qmc/solutions/no-negative-vibes/docs/PROPOSAL_LEDGER.md`
- Modify: `tracks/qmc/solutions/no-negative-vibes/docs/README.md`
- Modify: `tracks/qmc/solutions/no-negative-vibes/docs/EXPERIMENT_LOG.md`
- Modify: `tracks/qmc/solutions/no-negative-vibes/docs/COLLABORATOR_UPDATE.zh-CN.md`
- Modify: `tracks/qmc/solutions/no-negative-vibes/protocols/overlap-klein-v1/provenance.json`

**Interfaces:**

- Produces: terminal R01 status and one explicit next-plan decision.

- [ ] **Step 1: Update the proposal state from exact evidence**

Allowed terminal/continuation states:

- `falsified` when the intended cross-cluster claim has an exact no-go;
- `known-reduction` when an exact known mechanism covers every survivor;
- `proof-candidate` when an exact noncommuting cross-cluster cone survives but
  physical HS is still open;
- `physical-candidate` only if an already exact positive local gate exists.

Link the fixture, result document, experiments, protocol, and closing commit.

- [ ] **Step 2: Choose exactly one next main plan**

- If R01 has an exact noncommuting survivor, write Plan B for R02 using that
  global transform.
- If R01 proves a no-go, write Plan B around the four-mode HS separation/no-go
  theorem and promote CP/gauge reserve structures only through new cards.
- In either case, R03 triality may receive independent Plan C and run in
  parallel after Plan A review.

- [ ] **Step 3: Final verification**

Run on the WSL worker at the closing commit:

```bash
PYTHONPATH=. python -m pytest tests -q
git status --short
```

Expected: all tests pass and the worktree is clean after documentation commit.

- [ ] **Step 4: Commit, push, and update internal PR #3**

```bash
git add tracks/qmc/solutions/no-negative-vibes/docs \
        tracks/qmc/solutions/no-negative-vibes/protocols/overlap-klein-v1/provenance.json
git commit -m "docs: conclude R01 overlapping Klein investigation"
git push shared work/zibo/representation-cones
```

Keep PR #3 draft until the teammate can review the exact claim. Do not merge it
or export to the organizer-facing branch as part of Plan A.
