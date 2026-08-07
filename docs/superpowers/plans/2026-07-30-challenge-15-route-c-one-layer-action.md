# Challenge #15 Route C One-Layer Exact Action Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Re-freeze Route C at one exact LLL scalar-operator layer and decide, with correctness and resource evidence, whether its JK coordinate action is viable for the frozen N=6/N=8 workload.

**Architecture:** Preserve the validated JK `L=0/2` seed family and projected-density scalars. Decompose each scalar as a one-body constant plus a pair-Casimir polynomial, evaluate that polynomial with a division-free rank-4 pair jet of the raw JK polynomial, and block all model/VMC work behind an actual microbenchmark gate.

**Tech Stack:** Python 3.11+, NumPy/SciPy, existing `scalable_v1` contracts and protocol, pytest, `complex128`.

---

## Scope boundary

This plan covers the protocol amendment and exact-action feasibility gate only.
It intentionally stops before `model.py`, sampling, local energy, training,
checkpoint freeze, or ED reveal. If the microbenchmark passes, a second plan
will connect the exact action to the one-layer neural model and VMC. If it
fails, attempt a02 closes with the measured gate result rather than consuming
time on an unusable trainer.

## File map

- Modify `docs/superpowers/specs/2026-07-28-challenge-15-scalable-v1-design.md`
  to record the approved one-layer common amendment.
- Modify `tracks/qmc/solutions/BOTS-848/scalable_v1/protocol.json` and
  `protocol.py` to freeze and validate the new Route C capacity.
- Modify `tracks/qmc/solutions/BOTS-848/tests/test_scalable_protocol.py` for
  TDD coverage of the capacity and tamper rejection.
- Create `tracks/qmc/solutions/BOTS-848/scalable_v1/routes/cf_operator_nqs/pair_casimir.py`
  for the two-particle scalar decomposition.
- Create `tracks/qmc/solutions/BOTS-848/scalable_v1/routes/cf_operator_nqs/jets.py`
  for bounded Taylor arithmetic and a division-free determinant.
- Create `tracks/qmc/solutions/BOTS-848/scalable_v1/routes/cf_operator_nqs/coordinate_action.py`
  for exact JK pointwise scalar action.
- Create `tracks/qmc/solutions/BOTS-848/scalable_v1/routes/cf_operator_nqs/microbenchmark.py`
  for reproducible correctness/resource records.
- Create focused tests
  `test_cf_operator_nqs_pair_casimir.py`, `test_cf_operator_nqs_jets.py`,
  `test_cf_operator_nqs_coordinate_action.py`, and
  `test_cf_operator_nqs_microbenchmark.py`.
- Create `tracks/qmc/solutions/BOTS-848/logs/scalable-v1/s02c-a02.md` and
  update the scalable-v1 index only after the measured outcome is known.

### Task 1: Freeze the one-layer protocol amendment

**Files:**

- Modify: `tracks/qmc/solutions/BOTS-848/tests/test_scalable_protocol.py`
- Modify: `tracks/qmc/solutions/BOTS-848/scalable_v1/protocol.json`
- Modify: `tracks/qmc/solutions/BOTS-848/scalable_v1/protocol.py`
- Modify: `docs/superpowers/specs/2026-07-28-challenge-15-scalable-v1-design.md`

- [ ] **Step 1: Change the capacity assertion and add a tamper case**

Update the Route C assertion to one layer and extend the invalid-contract table:

```python
def test_route_c_uses_strict_lll_operator_capacity() -> None:
    protocol = load_protocol()
    assert protocol.capacity["routes"]["cf_operator_nqs"] == {
        "operator_layers": 1,
        "density_ranks": [2, 3, 4],
        "hidden_width": 64,
    }
    assert "cf_flow_l2" not in protocol.capacity["routes"]


# Add to the parametrized cases:
("route_c_capacity", "invalid Route C capacity"),

# Add to the case mutation chain:
elif case == "route_c_capacity":
    data["capacity"]["routes"]["cf_operator_nqs"]["operator_layers"] = 2
```

- [ ] **Step 2: Run the focused test and verify RED**

Run:

```powershell
python -m pytest tracks/qmc/solutions/BOTS-848/tests/test_scalable_protocol.py -q
```

Expected: the capacity assertion fails because committed JSON still says `2`;
the tamper case also fails because the loader currently accepts it.

- [ ] **Step 3: Change only the Route C layer count in protocol JSON**

The approved mapping is exactly:

```json
"cf_operator_nqs": {
  "operator_layers": 1,
  "density_ranks": [2, 3, 4],
  "hidden_width": 64
}
```

Do not change any other protocol byte except formatting required to retain the
existing one-line section style.

- [ ] **Step 4: Validate the exact Route C mapping in the loader**

Add this to `_validate` after the oracle check:

```python
    route_c = data["capacity"]["routes"].get("cf_operator_nqs")
    expected_route_c = {
        "operator_layers": 1,
        "density_ranks": [2, 3, 4],
        "hidden_width": 64,
    }
    if route_c != expected_route_c:
        raise ValueError("invalid Route C capacity")
```

- [ ] **Step 5: Record the amendment in the common design**

Replace the Route C two-layer wording by one layer, add the a01 failure as the
reason, and state that the new common-base SHA is the Task 1 commit itself. Do
not write a guessed SHA before the commit exists; amend the doc with the actual
SHA in Task 5's journal commit.

- [ ] **Step 6: Verify GREEN and commit**

Run:

```powershell
python -m pytest tracks/qmc/solutions/BOTS-848/tests/test_scalable_protocol.py tracks/qmc/solutions/BOTS-848/tests/test_scalable_gates.py -q
git diff --check
```

Expected: all focused tests pass and `git diff --check` emits no errors.

Commit:

```powershell
git add -f docs/superpowers/specs/2026-07-28-challenge-15-scalable-v1-design.md
git add tracks/qmc/solutions/BOTS-848/scalable_v1/protocol.json tracks/qmc/solutions/BOTS-848/scalable_v1/protocol.py tracks/qmc/solutions/BOTS-848/tests/test_scalable_protocol.py
git commit -m "docs(qmc): freeze one-layer Route C protocol"
```

### Task 2: Derive the pair-Casimir scalar polynomial

**Files:**

- Create: `tracks/qmc/solutions/BOTS-848/scalable_v1/routes/cf_operator_nqs/pair_casimir.py`
- Create: `tracks/qmc/solutions/BOTS-848/tests/test_cf_operator_nqs_pair_casimir.py`
- Modify: `tracks/qmc/solutions/BOTS-848/scalable_v1/routes/cf_operator_nqs/__init__.py`

- [ ] **Step 1: Write the two-particle reconstruction tests**

The test constructs the direct distinguishable-particle contraction from
`projected_density_tensor`, then compares it with the polynomial:

```python
def direct_pair_fixture(
    two_q: int, ell: int
) -> tuple[complex, np.ndarray, np.ndarray]:
    dimension = two_q + 1
    j = 0.5 * two_q
    jz = np.diag(np.arange(dimension, dtype=float) - j).astype(np.complex128)
    jplus = np.zeros((dimension, dimension), dtype=np.complex128)
    for orbital in range(two_q):
        jplus[orbital + 1, orbital] = math.sqrt(
            (two_q - orbital) * (orbital + 1)
        )
    jminus = jplus.T.conj()
    pair_dot = (
        np.kron(jz, jz)
        + 0.5 * np.kron(jplus, jminus)
        + 0.5 * np.kron(jminus, jplus)
    )
    tensors = {
        m: projected_density_tensor(two_q=two_q, ell=ell, m=m)
        for m in range(-ell, ell + 1)
    }
    self_matrix = sum(
        ((-1) ** m) * tensors[m] @ tensors[-m]
        for m in range(-ell, ell + 1)
    )
    cross = sum(
        ((-1) ** m)
        * (
            np.kron(tensors[m], tensors[-m])
            + np.kron(tensors[-m], tensors[m])
        )
        for m in range(-ell, ell + 1)
    )
    return complex(np.trace(self_matrix) / dimension), cross, pair_dot


@pytest.mark.parametrize(
    ("two_q", "ell"),
    ((3, 2), (9, 2), (15, 3), (15, 4), (21, 2), (21, 3), (21, 4)),
)
def test_pair_casimir_reconstructs_projected_density_scalar(
    two_q: int, ell: int
) -> None:
    decomposition = pair_casimir_decomposition(two_q=two_q, ell=ell)
    expected_self, expected_cross, pair_dot = direct_pair_fixture(two_q, ell)

    np.testing.assert_allclose(
        decomposition.self_scalar,
        expected_self,
        rtol=0.0,
        atol=1.0e-11,
    )
    reconstructed = decomposition.evaluate_matrix(pair_dot)
    residual = np.linalg.norm(reconstructed - expected_cross) / np.linalg.norm(
        expected_cross
    )
    assert residual <= 1.0e-10
    assert decomposition.degree == ell
```

Add rejection tests for Boolean/non-integral flux, unsupported rank, and any
fit whose reconstruction residual exceeds `1e-10`.

- [ ] **Step 2: Run the new test and verify RED**

Run:

```powershell
python -m pytest tracks/qmc/solutions/BOTS-848/tests/test_cf_operator_nqs_pair_casimir.py -q
```

Expected: collection fails with `ModuleNotFoundError` for `pair_casimir`.

- [ ] **Step 3: Implement the decomposition type and angular-momentum matrices**

Create this public surface:

```python
@dataclass(frozen=True)
class PairCasimirDecomposition:
    two_q: int
    ell: int
    self_scalar: complex
    scale: float
    coefficients: np.ndarray
    reconstruction_residual: float

    @property
    def degree(self) -> int:
        return len(self.coefficients) - 1

    def evaluate_matrix(self, pair_dot: np.ndarray) -> np.ndarray:
        scaled = np.asarray(pair_dot, dtype=np.complex128) / self.scale
        result = np.zeros_like(scaled)
        for coefficient in self.coefficients[::-1]:
            result = result @ scaled + coefficient * np.eye(len(scaled))
        return result

    def evaluate_scalar(self, pair_dot: float) -> complex:
        scaled = pair_dot / self.scale
        result = 0.0j
        for coefficient in self.coefficients[::-1]:
            result = result * scaled + coefficient
        return complex(result)


@lru_cache(maxsize=None)
def pair_casimir_decomposition(
    *, two_q: int, ell: int
) -> PairCasimirDecomposition:
    if isinstance(two_q, bool) or not isinstance(two_q, Integral):
        raise TypeError("two_q must be an integer")
    if isinstance(ell, bool) or not isinstance(ell, Integral):
        raise TypeError("ell must be an integer")
    if two_q <= 0 or ell not in (2, 3, 4) or ell > two_q:
        raise ValueError("invalid pair-Casimir flux or rank")
    dimension = two_q + 1
    j = 0.5 * two_q
    jz = np.diag(np.arange(dimension, dtype=float) - j).astype(np.complex128)
    jplus = np.zeros((dimension, dimension), dtype=np.complex128)
    for orbital in range(two_q):
        jplus[orbital + 1, orbital] = math.sqrt(
            (two_q - orbital) * (orbital + 1)
        )
    jminus = jplus.T.conj()
    identity = np.eye(dimension, dtype=np.complex128)
    pair_identity = np.eye(dimension * dimension, dtype=np.complex128)
    pair_dot = (
        np.kron(jz, jz)
        + 0.5 * np.kron(jplus, jminus)
        + 0.5 * np.kron(jminus, jplus)
    )
    tensors = {
        m: projected_density_tensor(two_q=two_q, ell=ell, m=m)
        for m in range(-ell, ell + 1)
    }
    self_matrix = sum(
        ((-1) ** m) * tensors[m] @ tensors[-m]
        for m in range(-ell, ell + 1)
    )
    self_scalar = complex(np.trace(self_matrix) / dimension)
    if np.linalg.norm(self_matrix - self_scalar * identity) > 1.0e-10 * max(
        np.linalg.norm(self_matrix), np.finfo(float).tiny
    ):
        raise ValueError("projected-density self contraction is not scalar")
    cross = sum(
        ((-1) ** m)
        * (
            np.kron(tensors[m], tensors[-m])
            + np.kron(tensors[-m], tensors[m])
        )
        for m in range(-ell, ell + 1)
    )
    scale = float(np.max(np.abs(np.linalg.eigvalsh(pair_dot))))
    scaled = pair_dot / scale
    powers = [pair_identity]
    for _ in range(ell):
        powers.append(powers[-1] @ scaled)
    design = np.column_stack([power.reshape(-1) for power in powers])
    coefficients = np.linalg.lstsq(design, cross.reshape(-1), rcond=None)[0]
    reconstructed = sum(
        coefficient * power
        for coefficient, power in zip(coefficients, powers, strict=True)
    )
    residual = float(
        np.linalg.norm(reconstructed - cross)
        / max(np.linalg.norm(cross), np.finfo(float).tiny)
    )
    if not np.all(np.isfinite(coefficients)) or residual > 1.0e-10:
        raise ValueError("pair-Casimir reconstruction failed")
    coefficients.setflags(write=False)
    return PairCasimirDecomposition(
        two_q=two_q,
        ell=ell,
        self_scalar=self_scalar,
        scale=scale,
        coefficients=coefficients,
        reconstruction_residual=residual,
    )
```

Inside the cached builder:

1. construct one-body `J_z`, `J_+`, `J_-` at `Q=two_q/2`;
2. build `X=J_i dot J_j` on the `(two_q+1)^2` distinguishable pair space;
3. compute the self contraction
   `sum_m (-1)^m t_m @ t_-m` and verify it is scalar;
4. compute the ordered-pair cross contraction
   `sum_m (-1)^m [kron(t_m,t_-m)+kron(t_-m,t_m)]`;
5. fit increasing powers of `X/scale` through degree `ell` with
   `np.linalg.lstsq`;
6. reject a non-finite coefficient or reconstruction residual above `1e-10`;
7. mark the returned coefficient array read-only.

Use `scale=max(abs(eigvalsh(X)))` so the Vandermonde/power fit is bounded at
`2Q=21`.

- [ ] **Step 4: Verify GREEN and existing operator regressions**

Run:

```powershell
python -m pytest tracks/qmc/solutions/BOTS-848/tests/test_cf_operator_nqs_pair_casimir.py tracks/qmc/solutions/BOTS-848/tests/test_cf_operator_nqs_operators.py -q
```

Expected: all tests pass.

- [ ] **Step 5: Commit**

```powershell
git add tracks/qmc/solutions/BOTS-848/scalable_v1/routes/cf_operator_nqs/pair_casimir.py tracks/qmc/solutions/BOTS-848/scalable_v1/routes/cf_operator_nqs/__init__.py tracks/qmc/solutions/BOTS-848/tests/test_cf_operator_nqs_pair_casimir.py
git commit -m "feat(qmc): derive Route C pair Casimir action"
```

### Task 3: Implement the bounded pair-jet algebra

**Files:**

- Create: `tracks/qmc/solutions/BOTS-848/scalable_v1/routes/cf_operator_nqs/jets.py`
- Create: `tracks/qmc/solutions/BOTS-848/tests/test_cf_operator_nqs_jets.py`

- [ ] **Step 1: Write arithmetic, derivative, and determinant tests**

Use normalized Taylor coefficients `D^alpha f / alpha!` and the fixed envelope
`degree(alpha[0:2])<=4`, `degree(alpha[2:4])<=4`:

```python
def test_pair_jet_matches_known_polynomial_derivatives() -> None:
    u_i = PairJet.variable(1.2 - 0.3j, axis=0)
    v_i = PairJet.variable(-0.4 + 0.2j, axis=1)
    u_j = PairJet.variable(0.7 + 0.1j, axis=2)
    v_j = PairJet.variable(-0.2 - 0.5j, axis=3)
    value = (u_i * v_j - v_i * u_j) ** 3

    expected = (1.2 - 0.3j) * (-0.2 - 0.5j) - (
        -0.4 + 0.2j
    ) * (0.7 + 0.1j)
    np.testing.assert_allclose(value.constant_term, expected**3)
    np.testing.assert_allclose(
        value.derivative(0).constant_term,
        3.0 * expected**2 * (-0.2 - 0.5j),
    )


def test_pair_jet_determinant_is_division_free_and_exact() -> None:
    x = PairJet.variable(0.3 + 0.1j, axis=0)
    matrix = [[x, PairJet.constant(2.0)],
              [PairJet.constant(3.0), PairJet.constant(5.0)]]
    determinant = jet_determinant(matrix)
    np.testing.assert_allclose(determinant.constant_term, 5.0 * x.constant_term - 6.0)
    np.testing.assert_allclose(determinant.derivative(0).constant_term, 5.0)
```

Also test immutable coefficient storage, invalid axes, non-finite inputs, and
envelope truncation.

- [ ] **Step 2: Run the test and verify RED**

Run:

```powershell
python -m pytest tracks/qmc/solutions/BOTS-848/tests/test_cf_operator_nqs_jets.py -q
```

Expected: collection fails because `jets.py` is absent.

- [ ] **Step 3: Implement `PairJet`**

Use this public API:

```python
from dataclasses import dataclass
from numbers import Number
from types import MappingProxyType
from typing import Mapping, Sequence

import numpy as np


MultiIndex = tuple[int, int, int, int]


@dataclass(frozen=True)
class PairJet:
    coefficients: Mapping[MultiIndex, complex]

    def __post_init__(self) -> None:
        checked: dict[MultiIndex, complex] = {}
        for index, value in self.coefficients.items():
            if len(index) != 4 or any(
                isinstance(item, bool) or not isinstance(item, int) or item < 0
                for item in index
            ):
                raise ValueError("invalid pair-jet multi-index")
            if sum(index[:2]) > 4 or sum(index[2:]) > 4:
                continue
            scalar = complex(value)
            if not np.isfinite(scalar.real) or not np.isfinite(scalar.imag):
                raise ValueError("pair-jet coefficients must be finite")
            if scalar != 0.0:
                checked[index] = scalar
        object.__setattr__(self, "coefficients", MappingProxyType(checked))

    @classmethod
    def constant(cls, value: complex) -> "PairJet":
        return cls({(0, 0, 0, 0): complex(value)})

    @classmethod
    def variable(cls, value: complex, *, axis: int) -> "PairJet":
        if isinstance(axis, bool) or not isinstance(axis, int) or axis not in range(4):
            raise ValueError("pair-jet axis must be 0, 1, 2, or 3")
        unit = [0, 0, 0, 0]
        unit[axis] = 1
        return cls({(0, 0, 0, 0): complex(value), tuple(unit): 1.0})

    @property
    def constant_term(self) -> complex:
        return self.coefficients.get((0, 0, 0, 0), 0.0j)

    @staticmethod
    def _coerce(other: object) -> "PairJet" | None:
        if isinstance(other, PairJet):
            return other
        if isinstance(other, Number) and not isinstance(other, (bool, np.bool_)):
            return PairJet.constant(complex(other))
        return None

    def derivative(self, axis: int) -> "PairJet":
        if isinstance(axis, bool) or not isinstance(axis, int) or axis not in range(4):
            raise ValueError("pair-jet axis must be 0, 1, 2, or 3")
        result: dict[MultiIndex, complex] = {}
        for index, value in self.coefficients.items():
            if index[axis] == 0:
                continue
            target = list(index)
            target[axis] -= 1
            result[tuple(target)] = result.get(tuple(target), 0.0j) + index[axis] * value
        return PairJet(result)

    def __add__(self, other: object) -> "PairJet":
        checked = self._coerce(other)
        if checked is None:
            return NotImplemented
        result = dict(self.coefficients)
        for index, value in checked.coefficients.items():
            result[index] = result.get(index, 0.0j) + value
        return PairJet(result)

    __radd__ = __add__

    def __neg__(self) -> "PairJet":
        return PairJet({index: -value for index, value in self.coefficients.items()})

    def __sub__(self, other: object) -> "PairJet":
        checked = self._coerce(other)
        if checked is None:
            return NotImplemented
        return self + (-checked)

    def __rsub__(self, other: object) -> "PairJet":
        checked = self._coerce(other)
        if checked is None:
            return NotImplemented
        return checked - self

    def __mul__(self, other: object) -> "PairJet":
        checked = self._coerce(other)
        if checked is None:
            return NotImplemented
        result: dict[MultiIndex, complex] = {}
        for left_index, left_value in self.coefficients.items():
            for right_index, right_value in checked.coefficients.items():
                target = tuple(
                    left + right
                    for left, right in zip(left_index, right_index, strict=True)
                )
                if sum(target[:2]) <= 4 and sum(target[2:]) <= 4:
                    result[target] = result.get(target, 0.0j) + left_value * right_value
        return PairJet(result)

    __rmul__ = __mul__

    def __pow__(self, exponent: int) -> "PairJet":
        if isinstance(exponent, bool) or not isinstance(exponent, int) or exponent < 0:
            raise ValueError("pair-jet exponent must be a nonnegative integer")
        result = PairJet.constant(1.0)
        factor = self
        power = exponent
        while power:
            if power & 1:
                result = result * factor
            factor = factor * factor
            power >>= 1
        return result
```

Multiplication adds multi-indices and discards a term only when either
particle's two-variable degree exceeds four. Derivation maps normalized Taylor
coefficient `c[alpha+e_axis]` to
`(alpha_axis+1)*c[alpha+e_axis]`. Reject Boolean exponents, negative powers,
and every non-finite scalar.

- [ ] **Step 4: Implement the division-free determinant**

Use row/subset dynamic programming over the commutative jet ring:

```python
def jet_determinant(matrix: Sequence[Sequence[PairJet]]) -> PairJet:
    n = len(matrix)
    states = {0: PairJet.constant(1.0)}
    for row in range(n):
        next_states: dict[int, PairJet] = {}
        for mask, partial in states.items():
            for column in range(n):
                if mask & (1 << column):
                    continue
                occupied_after = (mask >> (column + 1)).bit_count()
                sign = -1.0 if occupied_after % 2 else 1.0
                new_mask = mask | (1 << column)
                term = sign * partial * matrix[row][column]
                next_states[new_mask] = next_states.get(
                    new_mask, PairJet.constant(0.0)
                ) + term
        states = next_states
    return states[(1 << n) - 1]
```

This algorithm uses no inverse or pivot and remains defined when the constant
matrix is singular.

- [ ] **Step 5: Verify GREEN and commit**

Run:

```powershell
python -m pytest tracks/qmc/solutions/BOTS-848/tests/test_cf_operator_nqs_jets.py -q
git diff --check
```

Expected: all jet tests pass and no diff errors occur.

Commit:

```powershell
git add tracks/qmc/solutions/BOTS-848/scalable_v1/routes/cf_operator_nqs/jets.py tracks/qmc/solutions/BOTS-848/tests/test_cf_operator_nqs_jets.py
git commit -m "feat(qmc): add bounded pair jet algebra"
```

### Task 4: Evaluate exact scalar action on JK coordinate seeds

**Files:**

- Create: `tracks/qmc/solutions/BOTS-848/scalable_v1/routes/cf_operator_nqs/coordinate_action.py`
- Create: `tracks/qmc/solutions/BOTS-848/tests/test_cf_operator_nqs_coordinate_action.py`
- Modify: `tracks/qmc/solutions/BOTS-848/scalable_v1/routes/cf_operator_nqs/__init__.py`
- Modify: `tracks/qmc/solutions/BOTS-848/scalable_v1/routes/cf_operator_nqs/seeds.py`

- [ ] **Step 1: Write RED tests for pair-dot and N=2 eigenvalues**

For N=2 every supported `L` multiplet occurs with multiplicity one, so a
scalar action has the analytic eigenvalue
`2*self_scalar+p_ell(x_L)`:

```python
def normalized_non_node_spinors(
    *, seed: int, batch: int, n_electrons: int
) -> np.ndarray:
    rng = np.random.default_rng(seed)
    values = rng.normal(size=(batch, n_electrons, 2)) + 1.0j * rng.normal(
        size=(batch, n_electrons, 2)
    )
    return values / np.linalg.norm(values, axis=-1, keepdims=True)


@pytest.mark.parametrize(("l", "m"), ((0, 0), (2, -2), (2, 0), (2, 2)))
@pytest.mark.parametrize("ell", (2, 3))
def test_coordinate_scalar_action_has_exact_n2_eigenvalue(
    l: int, m: int, ell: int
) -> None:
    family = JKCFSeedFamily(n_electrons=2, two_q=3)
    state = family.state(l=l, m=m)
    configs = normalized_non_node_spinors(seed=848, batch=4, n_electrons=2)
    seed_values, actions = evaluate_seed_and_actions(state, configs, ells=(ell,))
    decomposition = pair_casimir_decomposition(two_q=3, ell=ell)
    q = 1.5
    x_l = 0.5 * (l * (l + 1) - 2.0 * q * (q + 1.0))
    expected = 2.0 * decomposition.self_scalar + decomposition.evaluate_scalar(x_l)
    np.testing.assert_allclose(actions[:, 0], expected * seed_values, rtol=1e-10, atol=1e-11)


def test_pair_dot_matches_explicit_monomial_action() -> None:
    values = (0.8 + 0.1j, -0.3 + 0.2j, 0.7 - 0.2j, 0.4 + 0.3j)
    coordinates = tuple(
        PairJet.variable(value, axis=axis)
        for axis, value in enumerate(values)
    )
    u_i, v_i, u_j, v_j = coordinates
    value = u_i**2 * v_i * u_j * v_j**2
    actual = apply_pair_dot(value, coordinates).constant_term
    ui, vi, uj, vj = values
    base = ui**2 * vi * uj * vj**2
    expected = (
        0.25 * (2 - 1) * (1 - 2) * base
        + 0.5 * 1 * 1 * ui**3 * uj**0 * vj**3
        + 0.5 * 2 * 2 * ui * vi**2 * uj**2 * vj
    )
    np.testing.assert_allclose(actual, expected, rtol=2e-14, atol=2e-14)


def test_all_five_m_components_share_finite_coordinate_action() -> None:
    family = JKCFSeedFamily(n_electrons=6, two_q=15)
    configs = normalized_non_node_spinors(seed=3848, batch=2, n_electrons=6)
    for state in family.generate_multiplet().values():
        seed_values, actions = evaluate_seed_and_actions(state, configs)
        assert seed_values.shape == (2,)
        assert actions.shape == (2, 3)
        assert np.all(np.isfinite(seed_values))
        assert np.all(np.isfinite(actions))


def test_coordinate_action_rejects_nonfinite_configs() -> None:
    family = JKCFSeedFamily(n_electrons=2, two_q=3)
    configs = normalized_non_node_spinors(seed=848, batch=1, n_electrons=2)
    configs[0, 0, 0] = np.nan
    with pytest.raises(CoordinateActionNumericalError, match="finite"):
        evaluate_seed_and_actions(family.ground_state(), configs)
```

- [ ] **Step 2: Write RED tests for raw complex seed regression and nontriviality**

Refactoring seed helpers for object-ring arithmetic must not change existing
complex amplitudes:

```python
def test_ring_generic_seed_polynomial_matches_existing_complex_path() -> None:
    family = JKCFSeedFamily(n_electrons=6, two_q=15)
    configs = normalized_non_node_spinors(seed=1848, batch=3, n_electrons=6)
    for state in (family.ground_state(), family.reduced_l2_state()):
        expected = state.amplitude(configs)
        actual = np.asarray([
            polynomial_seed_amplitude(
                state,
                config,
                lambda matrix: np.linalg.det(
                    np.asarray(matrix, dtype=np.complex128)
                ),
            )
            for config in configs
        ])
        np.testing.assert_allclose(actual, expected, rtol=2e-12, atol=1e-300)


def symbolic_pair_dot(expression: object, variables: tuple[object, ...]) -> object:
    import sympy as sp

    u_i, v_i, u_j, v_j = variables
    jzi = sp.Rational(1, 2) * (
        u_i * sp.diff(expression, u_i) - v_i * sp.diff(expression, v_i)
    )
    zz = sp.Rational(1, 2) * (
        u_j * sp.diff(jzi, u_j) - v_j * sp.diff(jzi, v_j)
    )
    plus_minus = v_j * sp.diff(u_i * sp.diff(expression, v_i), u_j)
    minus_plus = u_j * sp.diff(v_i * sp.diff(expression, u_i), v_j)
    return zz + sp.Rational(1, 2) * (plus_minus + minus_plus)


def test_pair_jet_action_matches_independent_symbolic_reference() -> None:
    import sympy as sp

    family = JKCFSeedFamily(n_electrons=2, two_q=3)
    state = family.reduced_l2_state()
    variables = sp.symbols("u_i v_i u_j v_j")
    expression = polynomial_seed_amplitude(
        state,
        ((variables[0], variables[1]), (variables[2], variables[3])),
        lambda matrix: sp.Matrix(matrix).det(),
    )
    decomposition = pair_casimir_decomposition(two_q=3, ell=2)
    scaled_powers = [expression]
    for _ in range(decomposition.degree):
        scaled_powers.append(
            symbolic_pair_dot(scaled_powers[-1], variables) / decomposition.scale
        )
    symbolic_action = 2.0 * decomposition.self_scalar * expression + sum(
        coefficient * power
        for coefficient, power in zip(
            decomposition.coefficients, scaled_powers, strict=True
        )
    )
    substitutions = dict(
        zip(
            variables,
            (sp.Rational(3, 5), sp.Rational(4, 5),
             sp.Rational(5, 13), sp.Rational(12, 13)),
            strict=True,
        )
    )
    configs = np.asarray(
        [[[(3 / 5), (4 / 5)], [(5 / 13), (12 / 13)]]],
        dtype=np.complex128,
    )
    _, actual = evaluate_seed_and_actions(state, configs, ells=(2,))
    expected = complex(sp.N(symbolic_action.subs(substitutions), 30))
    np.testing.assert_allclose(actual[0, 0], expected, rtol=1e-10, atol=1e-11)


@pytest.mark.parametrize("l", (0, 2))
def test_operator_dressing_is_not_only_global_normalization(l: int) -> None:
    family = JKCFSeedFamily(n_electrons=6, two_q=15)
    state = family.state(l=l, m=0)
    configs = normalized_non_node_spinors(seed=2848 + l, batch=8, n_electrons=6)
    seed_values, actions = evaluate_seed_and_actions(state, configs)
    matrix = np.column_stack((seed_values, actions))
    singular_values = np.linalg.svd(matrix, compute_uv=False)
    assert singular_values[1] / singular_values[0] >= 1.0e-8


def test_coordinate_action_runtime_has_no_ed_import() -> None:
    runtime = (
        Path(coordinate_action.__file__),
        Path(pair_casimir.__file__),
        Path(jets.__file__),
    )
    imported: set[str] = set()
    for module_path in runtime:
        tree = ast.parse(module_path.read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                imported.update(alias.name for alias in node.names)
            elif isinstance(node, ast.ImportFrom) and node.module is not None:
                imported.add(node.module)
    assert not any(
        module == "benchmark_v0" or module.startswith("benchmark_v0.")
        for module in imported
    )
```

- [ ] **Step 3: Run the focused file and verify RED**

Run:

```powershell
python -m pytest tracks/qmc/solutions/BOTS-848/tests/test_cf_operator_nqs_coordinate_action.py -q
```

Expected: collection fails because `coordinate_action.py` is absent.

- [ ] **Step 4: Make the JK polynomial helpers ring-generic**

Keep the public `CFSeed.amplitude` result unchanged. Remove hard `complex(...)`
casts from pair-factor helpers, choose `dtype=object` when spinors contain
`PairJet`, and expose this internal helper from `seeds.py`:

```python
def polynomial_seed_amplitude(
    state: CFSeed,
    spinors: Sequence[Sequence[object]],
    determinant: Callable[[Sequence[Sequence[object]]], object],
) -> object:
    """Evaluate the raw division-free JK polynomial over a scalar ring."""
```

The normal complex path passes `np.linalg.det`; the jet path passes
`jet_determinant`. Do not alter the stable log-amplitude implementation.

- [ ] **Step 5: Implement pair-dot action on a jet**

```python
def apply_pair_dot(value: PairJet, coordinates: tuple[PairJet, ...]) -> PairJet:
    u_i, v_i, u_j, v_j = coordinates
    jzi = 0.5 * (u_i * value.derivative(0) - v_i * value.derivative(1))
    # Apply the j-th generator to the full intermediate, not only its value.
    zz = 0.5 * (
        u_j * jzi.derivative(2) - v_j * jzi.derivative(3)
    )
    plus_i = u_i * value.derivative(1)
    minus_i = v_i * value.derivative(0)
    plus_minus = v_j * plus_i.derivative(2)
    minus_plus = u_j * minus_i.derivative(3)
    return zz + 0.5 * (plus_minus + minus_plus)
```

Add a direct monomial test before trusting this formula; if the test reveals a
generator-order error, fix the formula rather than the expected value.

- [ ] **Step 6: Implement the coordinate action**

Create:

```python
class CoordinateActionNumericalError(FloatingPointError):
    pass


def evaluate_seed_and_actions(
    state: CFSeed,
    configs: object,
    *,
    ells: tuple[int, ...] = (2, 3, 4),
) -> tuple[np.ndarray, np.ndarray]:
    """Return raw seed values and exact S_ell seed values per configuration."""
```

For each configuration and each particle pair:

1. lift the pair's `(u_i,v_i,u_j,v_j)` as the four `PairJet.variable` axes and
   every other spinor component as `PairJet.constant`;
2. evaluate the raw JK polynomial once over the jet ring;
3. create scaled powers
   `f, (X/scale)f, (X/scale)^2f, (X/scale)^3f, (X/scale)^4f` by applying
   `(1.0 / decomposition.scale) * apply_pair_dot(current, coordinates)`
   recursively;
4. evaluate all requested pair polynomials by Horner contraction of the cached
   scaled coefficients;
5. sum pairs and add `N*self_scalar*seed_value`;
6. reject any non-finite coefficient or result with
   `CoordinateActionNumericalError`.

Preserve scalar/batch cardinality and return `complex128` arrays of shapes
`(B,)` and `(B,len(ells))`.

- [ ] **Step 7: Verify GREEN, full construction regressions, and forbidden imports**

Run:

```powershell
python -m pytest tracks/qmc/solutions/BOTS-848/tests/test_cf_operator_nqs_coordinate_action.py tracks/qmc/solutions/BOTS-848/tests/test_cf_operator_nqs_seeds.py tracks/qmc/solutions/BOTS-848/tests/test_cf_operator_nqs_operators.py -q
rg -n "benchmark_v0\.(ed_oracle|fock_ed|projected_nqs|nqs_benchmark)" tracks/qmc/solutions/BOTS-848/scalable_v1/routes/cf_operator_nqs
```

Expected: tests pass and `rg` emits no production import.

- [ ] **Step 8: Commit**

```powershell
git add tracks/qmc/solutions/BOTS-848/scalable_v1/routes/cf_operator_nqs/coordinate_action.py tracks/qmc/solutions/BOTS-848/scalable_v1/routes/cf_operator_nqs/seeds.py tracks/qmc/solutions/BOTS-848/scalable_v1/routes/cf_operator_nqs/__init__.py tracks/qmc/solutions/BOTS-848/tests/test_cf_operator_nqs_coordinate_action.py
git commit -m "feat(qmc): apply one-layer scalars to JK seeds"
```

### Task 5: Run the frozen exact-action microbenchmark and close a02

**Files:**

- Create: `tracks/qmc/solutions/BOTS-848/scalable_v1/routes/cf_operator_nqs/microbenchmark.py`
- Create: `tracks/qmc/solutions/BOTS-848/tests/test_cf_operator_nqs_microbenchmark.py`
- Create: `tracks/qmc/solutions/BOTS-848/logs/scalable-v1/s02c-a02.md`
- Modify: `tracks/qmc/solutions/BOTS-848/logs/scalable-v1/README.md`
- Generate outside Git: `tracks/qmc/results/BOTS-848-scalable-v1-s02c-a02/action-microbenchmark.json`

- [ ] **Step 1: Write RED tests for resource classification and atomic records**

```python
def test_action_budget_requires_half_wall_and_quarter_memory_reserve() -> None:
    protocol = load_protocol()
    record = classify_action_budget(
        n6_batch_seconds=0.10,
        peak_rss_bytes=1024,
        placement="local",
        protocol=protocol,
    )
    assert record.projected_action_seconds == pytest.approx(409.6)
    assert record.wall_valid
    assert record.memory_valid
    assert record.valid

    too_slow = classify_action_budget(
        n6_batch_seconds=0.20,
        peak_rss_bytes=1024,
        placement="local",
        protocol=protocol,
    )
    assert not too_slow.wall_valid
    assert not too_slow.valid


@pytest.mark.parametrize(
    ("kwargs", "message"),
    (
        ({"placement": "locla"}, "placement"),
        ({"n6_batch_seconds": float("nan")}, "finite"),
        ({"peak_rss_bytes": -1}, "peak_rss"),
    ),
)
def test_action_budget_rejects_invalid_measurements(
    kwargs: dict[str, object], message: str
) -> None:
    arguments: dict[str, object] = {
        "n6_batch_seconds": 0.10,
        "peak_rss_bytes": 1024,
        "placement": "local",
        "protocol": load_protocol(),
    }
    arguments.update(kwargs)
    with pytest.raises((TypeError, ValueError), match=message):
        classify_action_budget(**arguments)


def test_n8_completion_is_required() -> None:
    decision = classify_action_budget(
        n6_batch_seconds=0.10,
        peak_rss_bytes=1024,
        placement="local",
        protocol=load_protocol(),
        n8_complete=False,
    )
    assert not decision.n8_complete
    assert not decision.valid
```

The CLI integration test must parse the written JSON and assert exactly two
warmup and five measured repetitions for each size/sector, matching
`source_commit` and `protocol_sha256`, strict finite JSON numbers, and a final
LF byte. It must monkeypatch only the timer/action callback, not the classifier
or writer, so atomic replacement is exercised without running the expensive
kernel in the unit suite.

- [ ] **Step 2: Run the microbenchmark tests and verify RED**

Run:

```powershell
python -m pytest tracks/qmc/solutions/BOTS-848/tests/test_cf_operator_nqs_microbenchmark.py -q
```

Expected: collection fails because `microbenchmark.py` is absent.

- [ ] **Step 3: Implement the record and classifier**

```python
@dataclass(frozen=True)
class ActionBudgetDecision:
    placement: str
    n6_batch_seconds: float
    projected_action_seconds: float
    peak_rss_bytes: int
    wall_valid: bool
    memory_valid: bool
    n8_complete: bool

    @property
    def valid(self) -> bool:
        return self.wall_valid and self.memory_valid and self.n8_complete


def classify_action_budget(
    *,
    n6_batch_seconds: float,
    peak_rss_bytes: int,
    placement: str,
    protocol: ProtocolConfig,
    n8_complete: bool = True,
) -> ActionBudgetDecision:
    resources = protocol.resources
    wall_limit = resources[f"{placement}_wall_seconds"]
    rss_limit = resources[f"{placement}_peak_rss_bytes"]
    projected = 2.0 * protocol.training["optimizer_updates"] * n6_batch_seconds
    return ActionBudgetDecision(
        placement=placement,
        n6_batch_seconds=n6_batch_seconds,
        projected_action_seconds=projected,
        peak_rss_bytes=peak_rss_bytes,
        wall_valid=projected <= 0.5 * wall_limit,
        memory_valid=peak_rss_bytes <= 0.75 * rss_limit,
        n8_complete=n8_complete,
    )
```

The CLI must generate normalized deterministic batches from seeds `848` and
`4848`, run both `L=0` and reduced `L=2`, use two warmups and five measured
repetitions, record every repetition, and write with temporary-file plus
`Path.replace` semantics.

- [ ] **Step 4: Verify GREEN before the expensive run**

Run:

```powershell
python -m pytest tracks/qmc/solutions/BOTS-848/tests/test_cf_operator_nqs_microbenchmark.py tracks/qmc/solutions/BOTS-848/tests/test_cf_operator_nqs_coordinate_action.py -q
python -m pytest tracks/qmc/solutions/BOTS-848/tests -q
```

Expected: all focused and full BOTS:848 tests pass.

- [ ] **Step 5: Run the actual N=6/N=8 benchmark without ED access**

Run:

```powershell
python -m scalable_v1.routes.cf_operator_nqs.microbenchmark `
  --protocol tracks/qmc/solutions/BOTS-848/scalable_v1/protocol.json `
  --placement local `
  --output tracks/qmc/results/BOTS-848-scalable-v1-s02c-a02/action-microbenchmark.json
```

Run from `tracks/qmc/solutions/BOTS-848` on `PYTHONPATH`, or invoke the module
with that directory inserted exactly as existing tests do. Set a process
timeout of the selected placement wall ceiling; a timeout is a measured fail,
not a reason to lower batch size.

- [ ] **Step 6: Classify the outcome without changing budgets**

Read only the generated microbenchmark JSON. Do not read any ED result.

- If correctness is false, close a02 `failed` with the named residual.
- If correctness is true but resource decision is false, close a02 `failed`
  with wall/memory evidence.
- If the result cannot finish inside the time boundary, close a02
  `inconclusive` with the last completed size/repetition.
- If all exact-action checks pass, mark only the action prerequisite
  `slice-pass`; do not claim `route-frozen` and do not start ED reveal.

- [ ] **Step 7: Write the a02 journal and update the index**

The journal must contain:

- starting commit `7eb2825f79ca35476272e72d3b8e9c42c68f908e`;
- design commit `e01e809`;
- Task 1 amendment commit and old/new protocol SHA-256;
- RED/GREEN commands and commit list;
- exact N=6/N=8 repetitions, projected action wall, peak RSS, device
  fingerprint, and microbenchmark artifact path/hash;
- explicit statements that no trainer/checkpoint/freeze receipt/ED reveal was
  produced;
- attempts remaining (`3` after a02) and one concrete next action.

- [ ] **Step 8: Fresh verification and journal commit**

Run:

```powershell
python -m pytest tracks/qmc/solutions/BOTS-848/tests -q
git diff --check
git status --short --branch
```

Commit tracked source/tests/journal only; keep the raw result bundle ignored:

```powershell
git add tracks/qmc/solutions/BOTS-848/scalable_v1/routes/cf_operator_nqs/microbenchmark.py tracks/qmc/solutions/BOTS-848/tests/test_cf_operator_nqs_microbenchmark.py tracks/qmc/solutions/BOTS-848/logs/scalable-v1/s02c-a02.md tracks/qmc/solutions/BOTS-848/logs/scalable-v1/README.md
git commit -m "docs(qmc): record one-layer action gate"
```

## Completion criteria for this plan

This plan is complete only when:

1. the committed protocol and loader both enforce one layer;
2. pair-Casimir reconstruction and pair-jet correctness tests pass;
3. an exact JK coordinate action exists without production ED/full-basis
   imports;
4. an actual N=6/N=8 microbenchmark record exists and is classified under the
   unchanged resource ceilings;
5. a02 is journaled as `slice-pass`, `failed`, or `inconclusive` without a
   false Challenge-compliant or route-frozen claim.
