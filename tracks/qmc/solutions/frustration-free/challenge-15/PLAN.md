# Challenge #15 Core Projected-Pfaffian NQS Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build and validate a reproducible neural variational calculation of the finite-size `L=0` ground-state energy, lowest `L=2` energy, and `Δ₂` gap for `N=6–8` spin-polarized `ν=1/3` electrons on the Haldane sphere.

**Architecture:** The production state is a shared sector-conditioned mixture of fixed-degree holomorphic Pfaffian carriers. Every carrier is an exact `M_z=0` member of the fermionic LLL Hilbert space, and a finite band-limited `SU(2)` projector produces exact `L=0` or `L=2`. An independent occupation-space implementation supplies angular-momentum and finite-sphere Coulomb ED oracles for small systems.

**Tech Stack:** Python 3.12, NumPy, SciPy, SymPy Wigner algebra, JAX x64, Flax, Optax, h5py, pytest, Matplotlib, uv.

## Global Constraints

- Work only under `tracks/qmc/solutions/frustration-free/challenge-15/` and `tracks/qmc/results/frustration-free/challenge-15/`, except for an explicitly approved repository-level dependency change.
- Use `2Q=3(N-1)`, `R=√Q ℓ_B`, chord Coulomb distance, and energy unit `E_C=e²/(4π ε₀ ε ℓ_B)`.
- Use finite-`Q` spherical Coulomb matrix elements; planar pseudopotentials are forbidden.
- Use ordered fermionic determinants and doubled integer quantum numbers (`two_q`, `two_m`, `two_l`) in all discrete APIs.
- Enable JAX and NumPy float64/complex128 for validation and reported results.
- No trainable parameter may be indexed by a determinant or exact multiplicity-basis vector.
- No generic coordinate activation may change per-particle holomorphic degree `2Q`.
- `L=0` and `L=2` must use one parameter set; separate private models are forbidden.
- Complete dense irrep projectors are small-system oracles only and must not appear in production amplitude evaluation.
- Coordinate VMC estimates `⟨V⟩`; the variance of bare `V(z)` must never be labeled projected-Hamiltonian variance.
- A chiral-graviton claim and the fusion-network research extension are outside this plan.
- Each task uses TDD, ends with focused and cumulative tests, and is committed locally only after its review gate passes.

## File Map

- `pyproject.toml`, `uv.lock`: isolated locked runtime.
- `src/challenge15/spec.py`: immutable sphere conventions and validation.
- `src/challenge15/monopole.py`: spinors, monopole LLL orbitals, gauge charts, and rotations.
- `src/challenge15/fermions.py`: ordered determinants and fermionic one-/two-body actions.
- `src/challenge15/angular.py`: many-body `L_z`, `L_±`, `L²`, target-irrep isometries, and ladder checks.
- `src/challenge15/coulomb.py`: independent finite-sphere Coulomb integral and pseudopotential builders.
- `src/challenge15/oracle.py`: target-sector Hamiltonians, eigensystems, and exact diagnostics.
- `src/challenge15/pfaffian.py`: stable complex Pfaffian value and derivative primitive.
- `src/challenge15/carriers.py`: even/odd fixed-degree Pfaffian carriers and determinant coefficients.
- `src/challenge15/projector.py`: exact finite-band `P^L_{M0}` quadrature.
- `src/challenge15/model.py`: shared Flax hypernetwork and projected NQS.
- `src/challenge15/vmc.py`: sphere sampler and unbiased energy/gradient estimators.
- `src/challenge15/train.py`: joint-sector optimization and nested-rank convergence.
- `src/challenge15/artifacts.py`: schemas, hashes, atomic publication, and reload validation.
- `src/challenge15/cli.py`: reproducible command-line entry points.
- `tests/`: one focused test module for every source module plus end-to-end acceptance.
- `README.md`: environment, commands, conventions, limitations, and result interpretation.

---

### Task 1: Locked runtime, sphere specification, and monopole LLL orbitals

**Files:**
- Create: `tracks/qmc/solutions/frustration-free/challenge-15/pyproject.toml`
- Create: `tracks/qmc/solutions/frustration-free/challenge-15/uv.lock`
- Create: `tracks/qmc/solutions/frustration-free/challenge-15/src/challenge15/__init__.py`
- Create: `tracks/qmc/solutions/frustration-free/challenge-15/src/challenge15/spec.py`
- Create: `tracks/qmc/solutions/frustration-free/challenge-15/src/challenge15/monopole.py`
- Create: `tracks/qmc/solutions/frustration-free/challenge-15/tests/test_spec.py`
- Create: `tracks/qmc/solutions/frustration-free/challenge-15/tests/test_monopole.py`

**Interfaces:**
- Produces: `SphereSpec`, `normalized_spinors`, `north_lll_orbitals`, `south_lll_orbitals`, `rotate_spinors`.
- Consumes: none.

- [ ] **Step 1: Create the isolated package and lock its dependencies**

```toml
[project]
name = "challenge15-nqs"
version = "0.1.0"
requires-python = ">=3.12,<3.13"
dependencies = [
  "flax",
  "h5py==3.14.0",
  "jax",
  "matplotlib==3.10.9",
  "numpy==2.2.6",
  "optax",
  "pytest",
  "scipy==1.15.3",
  "sympy",
]

[build-system]
requires = ["hatchling"]
build-backend = "hatchling.build"

[tool.hatch.build.targets.wheel]
packages = ["src/challenge15"]

[tool.pytest.ini_options]
addopts = "-q"
testpaths = ["tests"]
```

Run:

```bash
cd tracks/qmc/solutions/frustration-free/challenge-15
uv lock
uv sync
```

Expected: a new `uv.lock`, successful imports of `jax`, `flax`, `optax`, `sympy`, and `jax.config.update("jax_enable_x64", True)` reporting x64 enabled.

- [ ] **Step 2: Write failing specification tests**

```python
import pytest
from challenge15.spec import SphereSpec


@pytest.mark.parametrize(
    ("particles", "two_q", "orbitals", "dimension"),
    [(6, 15, 16, 8008), (7, 18, 19, 50388), (8, 21, 22, 319770)],
)
def test_laughlin_sphere_spec(particles, two_q, orbitals, dimension):
    spec = SphereSpec(particles)
    assert spec.two_q == two_q
    assert spec.orbital_count == orbitals
    assert spec.full_dimension == dimension
    assert spec.two_m_values[0] == -two_q
    assert spec.two_m_values[-1] == two_q


def test_invalid_particle_number_is_rejected():
    with pytest.raises(ValueError, match="particles must be at least 2"):
        SphereSpec(1)
```

- [ ] **Step 3: Run the tests and verify RED**

Run: `uv run pytest tests/test_spec.py -q`

Expected: FAIL with `ModuleNotFoundError` or missing `SphereSpec`.

- [ ] **Step 4: Implement the immutable convention object**

```python
from dataclasses import dataclass
from math import comb, sqrt


@dataclass(frozen=True, slots=True)
class SphereSpec:
    particles: int

    def __post_init__(self) -> None:
        if isinstance(self.particles, bool) or self.particles < 2:
            raise ValueError("particles must be at least 2")

    @property
    def two_q(self) -> int:
        return 3 * (self.particles - 1)

    @property
    def q(self) -> float:
        return self.two_q / 2

    @property
    def orbital_count(self) -> int:
        return self.two_q + 1

    @property
    def two_m_values(self) -> tuple[int, ...]:
        return tuple(range(-self.two_q, self.two_q + 1, 2))

    @property
    def radius_in_magnetic_lengths(self) -> float:
        return sqrt(self.q)

    @property
    def l_max(self) -> int:
        return self.particles * self.two_q // 2

    @property
    def full_dimension(self) -> int:
        return comb(self.orbital_count, self.particles)
```

- [ ] **Step 5: Write failing monopole-orbital and chart tests**

```python
import numpy as np
from challenge15.monopole import (
    north_lll_orbitals,
    normalized_spinors,
    south_lll_orbitals,
)
from challenge15.spec import SphereSpec


def test_lll_orbitals_are_normalized_by_sphere_quadrature():
    spec = SphereSpec(4)
    x, wx = np.polynomial.legendre.leggauss(80)
    phi = np.linspace(0.0, 2.0 * np.pi, 161, endpoint=False)
    theta = np.arccos(x)
    spinors = normalized_spinors(theta[:, None], phi[None, :])
    values = north_lll_orbitals(spinors, spec)
    norms = np.einsum("x,xpm,xpm->m", wx, values.conj(), values)
    norms *= 2.0 * np.pi / phi.size
    np.testing.assert_allclose(norms, np.ones(spec.orbital_count), atol=2e-12)


def test_chart_change_is_one_particle_monopole_phase():
    spec = SphereSpec(4)
    spinors = normalized_spinors(np.array([1.1]), np.array([0.7]))
    north = north_lll_orbitals(spinors, spec)
    south, phase = south_lll_orbitals(spinors, spec, return_transition=True)
    np.testing.assert_allclose(south, phase[:, None] * north, atol=1e-13)
```

- [ ] **Step 6: Implement normalized spinors and fixed-degree orbitals**

Use

```python
φ_m(u,v) = sqrt((2Q+1)/(4π) * binom(2Q,Q+m)) * u^(Q+m) * v^(Q-m)
```

with integer exponents `(two_q±two_m)//2`. Normalize input spinors and reject zero norm. Implement rotations as normalized `SU(2)` matrices acting on the last spinor axis. Document the exact north/south transition phase and test it rather than inferring it numerically.

- [ ] **Step 7: Run focused and cumulative tests**

Run:

```bash
uv run pytest tests/test_spec.py tests/test_monopole.py -q
```

Expected: all tests pass in x64.

- [ ] **Step 8: Commit Task 1**

```bash
git add tracks/qmc/solutions/frustration-free/challenge-15
git commit -m "Add locked Haldane-sphere LLL foundation"
```

---

### Task 2: Ordered fermion basis and exact angular-momentum oracle

**Files:**
- Create: `src/challenge15/fermions.py`
- Create: `src/challenge15/angular.py`
- Create: `tests/test_fermions.py`
- Create: `tests/test_angular.py`

**Interfaces:**
- Consumes: `SphereSpec`.
- Produces: `DeterminantBasis`, `apply_one_body`, `angular_operators`, `target_irrep_isometry`, `verify_ladder_multiplet`.

- [ ] **Step 1: Write failing CAR and sign tests**

```python
import numpy as np
from challenge15.fermions import DeterminantBasis, apply_creation, apply_annihilation
from challenge15.spec import SphereSpec


def test_creation_annihilation_obey_car():
    basis = DeterminantBasis.full(SphereSpec(3))
    for state in basis.states[:20]:
        for p in range(basis.spec.orbital_count):
            lhs = 0.0
            first = apply_annihilation(state, p)
            if first is not None:
                second = apply_creation(first.state, p)
                lhs += first.sign * second.sign
            first = apply_creation(state, p)
            if first is not None:
                second = apply_annihilation(first.state, p)
                lhs += first.sign * second.sign
            assert lhs == 1.0
```

- [ ] **Step 2: Run RED, then implement ordered bit-state operations**

Represent determinants as Python `int` bit patterns, sort states numerically, validate popcount, and compute every fermion sign as `(-1)**popcount(state & ((1 << orbital)-1))`. Never cast an unchecked negative state to an unsigned integer.

- [ ] **Step 3: Write failing angular-algebra tests**

```python
import numpy as np
import pytest
from challenge15.angular import angular_operators, target_irrep_isometry
from challenge15.fermions import DeterminantBasis
from challenge15.spec import SphereSpec


@pytest.mark.parametrize("particles", [2, 3, 4, 6])
def test_many_body_su2_commutators(particles):
    basis = DeterminantBasis.full(SphereSpec(particles))
    lz, lp, lm = angular_operators(basis)
    scale = max(np.linalg.norm(lz.toarray()), 1.0)
    assert np.linalg.norm((lz @ lp - lp @ lz - lp).toarray()) / scale < 1e-12
    assert np.linalg.norm((lp @ lm - lm @ lp - 2 * lz).toarray()) / scale < 1e-12


@pytest.mark.parametrize("particles,target_l", [(4, 0), (4, 2), (6, 0), (6, 2)])
def test_target_isometry_has_exact_l2(particles, target_l):
    basis = DeterminantBasis.with_two_m(SphereSpec(particles), 0)
    l2 = angular_operators(basis, return_l2_only=True)
    t = target_irrep_isometry(basis, target_l)
    np.testing.assert_allclose(t.conj().T @ t, np.eye(t.shape[1]), atol=1e-12)
    np.testing.assert_allclose(l2 @ t, target_l * (target_l + 1) * t, atol=1e-11)
```

- [ ] **Step 4: Implement sparse `L_z`, `L_+`, `L_-`, and `L²`**

For orbital `m→m+1`, use coefficient

```text
sqrt((Q-m)(Q+m+1))
```

and the exact fermionic sign from Task 2. Build `L²` in a fixed-`M` basis through compatible neighboring-`M` maps, not by truncating `L_±` inside one sector. For `M=0`, use `L²=L_-L_+`.

- [ ] **Step 5: Implement deterministic target-irrep isometries**

Diagonalize the small-system `M=0` `L²`, select eigenvalues within `1e-10` of `L(L+1)`, sort columns by lexicographically phase-fixed pivots, QR-orthonormalize, and reject ambiguous rank. Store no Coulomb information.

- [ ] **Step 6: Add dimension and ladder reconstruction tests**

Check

```text
dim M_L = dim H_{M=L} - dim H_{M=L+1}
Σ_L (2L+1) dim M_L = binom(2Q+1,N)
```

and reconstruct all five `L=2` members from `M=0`, verifying ladder norms and orthogonality.

- [ ] **Step 7: Run tests and commit**

Run: `uv run pytest tests/test_fermions.py tests/test_angular.py -q`

Expected: all tests pass through `N=6`; mark `N=7,8` dimensional smoke tests as `pytest.mark.slow`.

```bash
git add tracks/qmc/solutions/frustration-free/challenge-15
git commit -m "Add exact fermion and angular momentum oracle"
```

---

### Task 3: Two independent finite-sphere Coulomb builders

**Files:**
- Create: `src/challenge15/coulomb.py`
- Create: `tests/test_coulomb.py`

**Interfaces:**
- Consumes: `SphereSpec`, determinant actions, SymPy Wigner symbols.
- Produces: `density_multipole_integrals`, `orbital_coulomb_tensor`, `pair_pseudopotentials`, `many_body_coulomb`.

- [ ] **Step 1: Write failing two-particle rotational and independence tests**

```python
import numpy as np
import pytest
from challenge15.coulomb import (
    orbital_coulomb_tensor,
    pair_pseudopotentials,
    pseudopotential_coulomb_tensor,
)
from challenge15.spec import SphereSpec


@pytest.mark.parametrize("particles", [2, 3, 4])
def test_independent_coulomb_builders_agree(particles):
    spec = SphereSpec(particles)
    direct = orbital_coulomb_tensor(spec)
    reduced = pseudopotential_coulomb_tensor(spec, pair_pseudopotentials(spec))
    np.testing.assert_allclose(direct, reduced, rtol=0.0, atol=1e-11)


def test_two_electron_levels_are_pair_angular_momentum_multiplets():
    spec = SphereSpec(2)
    values = pair_pseudopotentials(spec)
    assert set(values) == {j for j in range(0, spec.two_q + 1) if (spec.two_q - j) % 2 == 1}
    assert all(np.isfinite(list(values.values())))
```

- [ ] **Step 2: Run RED and implement the direct multipole builder**

Use the exact sphere expansion

```text
1/|r-r'| = (1/R) Σ_{kq} 4π/(2k+1) Y*_{kq}(Ω)Y_{kq}(Ω')
```

and the declared monopole-harmonic triple integral

```text
F^(kq)_(m,m') =
(-1)^(Q+m)
sqrt((2Q+1)^2(2k+1)/(4π))
( Q k Q; -Q 0 Q )
( Q k Q; -m q m' ).
```

Evaluate Wigner symbols with doubled-integer inputs through a cached SymPy wrapper, convert once to `float64`, and sum `k=0,...,2Q`. Keep the raw unsymmetrized tensor and assert `m_1+m_2=m_3+m_4`.

- [ ] **Step 3: Implement the independent pair-channel route**

Construct antisymmetric normalized pair states

```text
|J,M⟩ = Σ_(m1<m2) C^(JM)_(m1,m2) |m1,m2⟩
```

directly from Clebsch–Gordan coefficients. Do not obtain `V_J` by diagonalizing
the tensor from Step 2. Instead evaluate

```text
V_J =
1/(2J+1) Σ_M ∫dΩ₁dΩ₂ |Ψ_JM(Ω₁,Ω₂)|² /
                         [2√Q sin(γ₁₂/2)].
```

The `M`-sum is invariant under simultaneous rotations, so fix `Ω₁` at the north
pole, multiply by `4π`, and integrate `x=cos θ₂`. At the north pole only the
`m=Q` monopole component survives. Remove the known Coulomb weight
`(1-x)^(-1/2)` and evaluate the remaining finite polynomial with
Gauss–Jacobi nodes `roots_jacobi(order, -1/2, 0)`. Increase `order` until two
successive values agree within `1e-13 E_C`; additionally verify independence
of the admissible pair-state `M` before taking the rotational average.

Reconstruct the four-index tensor from these independently integrated `V_J`
and pair projectors. This path may share normalized monopole orbitals and CG
coefficients, but it must not call the density-multipole integral or
`orbital_coulomb_tensor`. For low `Q`, add a slower full product-quadrature
check for each individual `M` and verify that the resulting `V_J` is
`M`-independent before trusting the reduced north-pole integral.

- [ ] **Step 4: Add normalization, Hermiticity, and convention tests**

Test the `1/R=1/√Q` factor, antisymmetrization convention, tensor exchange symmetries, and the location of the many-body `1/2`. Include an `N=2` brute-force matrix comparison and a stored JSON fixture containing `two_q`, allowed `J`, and `V_J/E_C`.

- [ ] **Step 5: Implement sparse Slater–Condon assembly**

`many_body_coulomb(basis, tensor)` must enumerate only legal double substitutions, preserve `M_z`, accumulate in bounded NumPy buffers, and return CSR. Add a commutator test with `L²` below `1e-10`.

- [ ] **Step 6: Run tests and commit**

Run: `uv run pytest tests/test_coulomb.py tests/test_fermions.py tests/test_angular.py -q`

Expected: all tests pass; the two independent tensors agree to `1e-11 E_C`.

```bash
git add tracks/qmc/solutions/frustration-free/challenge-15
git commit -m "Add independent finite-sphere Coulomb builders"
```

---

### Task 4: Target-sector ED oracle and immutable reference artifacts

**Files:**
- Create: `src/challenge15/oracle.py`
- Create: `src/challenge15/artifacts.py`
- Create: `tests/test_oracle.py`
- Create: `tests/test_artifacts.py`

**Interfaces:**
- Consumes: target isometries and Coulomb matrices.
- Produces: `solve_target_sectors`, `OracleResult`, `publish_json_atomic`, `verify_artifact`.

- [ ] **Step 1: Write failing target-sector solver tests**

```python
from challenge15.oracle import solve_target_sectors
from challenge15.spec import SphereSpec


def test_oracle_returns_ground_l0_and_lowest_l2():
    result = solve_target_sectors(SphereSpec(4))
    assert result.energy_l2 > result.energy_l0
    assert result.gap == result.energy_l2 - result.energy_l0
    assert result.residual_l0 < 1e-11
    assert result.residual_l2 < 1e-11
    assert result.l2_variance_l0 < 1e-20
    assert result.l2_variance_l2 < 1e-20
```

- [ ] **Step 2: Implement projected Hamiltonians without hidden re-solves**

Compute `H_L=T_L† H_M=0 T_L`, diagonalize it once, and pass eigensystems explicitly to diagnostics. Scan all accessible low-lying `L` sectors for the report so `Δ₂` is not mislabeled as the absolute neutral gap.

- [ ] **Step 3: Write RED tests for transactional artifacts**

Test that publication writes to a unique sibling partial path, `fsync`s file and parent directory, verifies schema and SHA256 before `os.replace`, preserves an existing valid artifact on injected failure, and rejects absolute or parent-traversing manifest paths.

- [ ] **Step 4: Implement immutable oracle result schema**

Record physical conventions, package versions, Git revision, source hashes, dimensions, energies, residuals, `L²` variances, pair pseudopotentials, and hashes of every array. JSON must use sorted keys and reject NaN/Infinity.

- [ ] **Step 5: Generate and reload `N=4` smoke oracle**

Run:

```bash
uv run python - <<'PY'
from pathlib import Path
from challenge15.artifacts import publish_json_atomic, verify_artifact
from challenge15.oracle import solve_target_sectors
from challenge15.spec import SphereSpec

path = Path("/tmp/challenge15-n4/result.json")
publish_json_atomic(path, solve_target_sectors(SphereSpec(4)).to_payload())
verify_artifact(path)
print(path)
PY
```

Expected: verification succeeds and reloaded energies match bit-for-bit.

- [ ] **Step 6: Run tests and commit**

```bash
uv run pytest tests/test_oracle.py tests/test_artifacts.py -q
git add tracks/qmc/solutions/frustration-free/challenge-15
git commit -m "Add exact angular momentum resolved ED oracle"
```

---

### Task 5: Stable complex Pfaffian primitive and fixed-degree carriers

**Files:**
- Create: `src/challenge15/pfaffian.py`
- Create: `src/challenge15/carriers.py`
- Create: `tests/test_pfaffian.py`
- Create: `tests/test_carriers.py`

**Interfaces:**
- Consumes: monopole orbitals and `SphereSpec`.
- Produces: `pfaffian`, `bordered_pfaffian`, `carrier_amplitudes`, `carrier_determinant_coefficients`.

- [ ] **Step 1: Write failing Pfaffian value and derivative tests**

```python
import jax
import jax.numpy as jnp
import numpy as np
from challenge15.pfaffian import pfaffian

jax.config.update("jax_enable_x64", True)


def test_pfaffian_squared_equals_determinant():
    rng = np.random.default_rng(4)
    raw = rng.normal(size=(8, 8)) + 1j * rng.normal(size=(8, 8))
    matrix = raw - raw.T
    value = np.asarray(pfaffian(jnp.asarray(matrix)))
    np.testing.assert_allclose(value * value, np.linalg.det(matrix), rtol=2e-11)


def test_log_pfaffian_gradient_matches_finite_difference():
    matrix = jnp.asarray([[0, 2 + 1j, 3, 0], [-2 - 1j, 0, 0, 4], [-3, 0, 0, 5j], [0, -4, -5j, 0]], dtype=jnp.complex128)
    tangent = jnp.asarray([[0, 1, 0, 0], [-1, 0, 0, 0], [0, 0, 0, 0], [0, 0, 0, 0]], dtype=jnp.complex128)
    automatic = jax.jvp(lambda x: jnp.log(pfaffian(x)), (matrix,), (tangent,))[1]
    eps = 1e-6
    finite = (jnp.log(pfaffian(matrix + eps * tangent)) - jnp.log(pfaffian(matrix - eps * tangent))) / (2 * eps)
    np.testing.assert_allclose(automatic, finite, rtol=2e-7, atol=2e-8)
```

- [ ] **Step 2: Implement pivoted skew elimination and custom JVP**

The primal path performs complete `2×2` pivot selection, applies identical row/column permutations while tracking permutation sign, and returns zero for rank-deficient matrices. Away from zeros, implement

```text
d log Pf(A) = 1/2 Tr(A^-1 dA).
```

Reject nonsquare, odd-dimensional, or non-skew input above `1e-12`. Compare all matrices up to size 10 with an independent recursive NumPy oracle in tests.

- [ ] **Step 3: Write failing carrier symmetry and degree tests**

Test even `N=4,6` and odd `N=3,5`:

- swapping two particle spinors negates the carrier;
- multiplying particle `i` by phase `e^{iα}` multiplies the carrier by `e^{i2Qα}`;
- a `z`-axis rotation leaves the `M_z=0` carrier unchanged;
- odd carriers use a bordered matrix with the unique `m=0` orbital;
- analytic determinant coefficients reproduce direct coordinate evaluation at random spinors.

- [ ] **Step 4: Implement pair kernels and bordered odd carriers**

Evaluate only `m>0` pair channels, antisymmetrize the kernel explicitly, and verify every generated matrix is skew before calling `pfaffian`. Implement determinant coefficients as Pfaffians of the orbital-space pair matrix restricted to occupied orbitals, with the same border rule for odd `N`.

- [ ] **Step 5: Run tests and commit**

```bash
uv run pytest tests/test_pfaffian.py tests/test_carriers.py -q
git add tracks/qmc/solutions/frustration-free/challenge-15
git commit -m "Add differentiable holomorphic Pfaffian carriers"
```

---

### Task 6: Exact finite-band `SU(2)` projector

**Files:**
- Create: `src/challenge15/projector.py`
- Create: `tests/test_projector.py`

**Interfaces:**
- Consumes: carrier amplitude callable, spinor rotations, `SphereSpec`.
- Produces: `ProjectionGrid`, `project_m0`, `project_multiplet`.

- [ ] **Step 1: Write failing quadrature-bound tests**

```python
import numpy as np
import pytest
from challenge15.projector import ProjectionGrid
from challenge15.spec import SphereSpec


@pytest.mark.parametrize("particles,target_l", [(4, 0), (4, 2), (6, 0), (6, 2)])
def test_grid_satisfies_exact_bandlimit(particles, target_l):
    spec = SphereSpec(particles)
    grid = ProjectionGrid.exact(spec, target_l)
    assert grid.n_alpha >= 2 * spec.l_max + 1
    assert 2 * grid.n_beta - 1 >= spec.l_max + target_l
    assert abs(grid.alpha_weights.sum() - 2 * np.pi) < 1e-13
    assert abs(grid.beta_weights.sum() - 2.0) < 1e-13


@pytest.mark.parametrize("target_l", [0, 2])
def test_beta_rule_is_an_exact_legendre_projector(target_l):
    spec = SphereSpec(6)
    grid = ProjectionGrid.exact(spec, target_l)
    p_target = np.polynomial.legendre.Legendre.basis(target_l)(grid.beta_nodes)
    for source_l in range(spec.l_max + 1):
        p_source = np.polynomial.legendre.Legendre.basis(source_l)(grid.beta_nodes)
        projected = (2 * target_l + 1) / 2 * np.sum(
            grid.beta_weights * p_target * p_source
        )
        np.testing.assert_allclose(
            projected, float(source_l == target_l), atol=2e-12
        )
```

- [ ] **Step 2: Implement periodic Fourier and Gauss–Legendre grids**

Use

```text
P^L_00 = (2L+1)/(4π) ∫dα ∫dx P_L(x) R_z(α)R_y(arccos x).
```

Generate `n_alpha=2L_max+1` equispaced points and
`n_beta=ceil((L_max+L+1)/2)` Gauss–Legendre points. Store all weights in complex128 and expose blocked iteration so peak memory is independent of the full grid size.

- [ ] **Step 3: Test against the occupation-space projector**

For random `N=2–4` carrier coefficients:

1. evaluate the coordinate projector at random spinors;
2. project analytic determinant coefficients with `T_L T_L†`;
3. reconstruct the coordinate amplitude from projected coefficients;
4. require relative agreement below `1e-10`.

Also verify an input with pure `J≠L` projects to below `1e-11`.

- [ ] **Step 4: Add multiplet tests**

Generate `M=-2,...,2` with `P^2_M0` and independently with ladder operators. Verify the Wigner ladder coefficients, equal norms, random finite-rotation covariance, and no `M`-specific trainable inputs.

- [ ] **Step 5: Run tests and commit**

```bash
uv run pytest tests/test_projector.py tests/test_angular.py tests/test_carriers.py -q
git add tracks/qmc/solutions/frustration-free/challenge-15
git commit -m "Add exact band-limited SU2 projection"
```

---

### Task 7: Shared sector-conditioned neural Pfaffian model

**Files:**
- Create: `src/challenge15/model.py`
- Create: `tests/test_model.py`

**Interfaces:**
- Consumes: carriers and projector.
- Produces: `ModelConfig`, `ProjectedPfaffianNQS.init`, `ProjectedPfaffianNQS.apply`, `embed_rank`.

- [ ] **Step 1: Write failing shared-parameter and nested-rank tests**

```python
import jax
import jax.numpy as jnp
import numpy as np
from challenge15.model import ModelConfig, ProjectedPfaffianNQS, embed_rank
from challenge15.spec import SphereSpec


def test_one_parameter_tree_serves_both_sectors():
    model = ProjectedPfaffianNQS(ModelConfig(rank=2, hidden_width=32, depth=2))
    points = jnp.ones((4, 2), dtype=jnp.complex128) / jnp.sqrt(2)
    variables = model.init(jax.random.key(0), SphereSpec(4), points, target_l=0)
    value_l0 = model.apply(variables, SphereSpec(4), points, target_l=0)
    value_l2 = model.apply(variables, SphereSpec(4), points, target_l=2)
    assert jnp.isfinite(value_l0)
    assert jnp.isfinite(value_l2)
    assert "parameters_l0" not in variables["params"]
    assert "parameters_l2" not in variables["params"]


def test_rank_embedding_preserves_old_wavefunction_exactly():
    spec = SphereSpec(4)
    points = jnp.asarray([[1, 0], [0.8, 0.6], [0.6j, 0.8], [2**-0.5, 2**-0.5]], dtype=jnp.complex128)
    small = ProjectedPfaffianNQS(ModelConfig(rank=2, hidden_width=32, depth=2))
    params = small.init(jax.random.key(2), spec, points, target_l=0)
    expanded = embed_rank(params, old_rank=2, new_rank=4)
    large = ProjectedPfaffianNQS(ModelConfig(rank=4, hidden_width=32, depth=2))
    np.testing.assert_array_equal(
        np.asarray(small.apply(params, spec, points, target_l=0)),
        np.asarray(large.apply(expanded, spec, points, target_l=0)),
    )
```

- [ ] **Step 2: Implement the shared hypernetwork**

Use fixed Fourier features of `m/Q`, learned carrier tokens, a fixed embedding of `L∈{0,2}`, shared residual dense layers, and two-real-component complex outputs. Generate each carrier independently; prohibit cross-carrier softmax or normalization. Keep the explicit complex gate `a_s` outside the hypernetwork.

- [ ] **Step 3: Implement exact nested rank growth**

Copy all old parameters and carrier tokens bit-for-bit. Append new tokens deterministically from a new PRNG key and initialize new gates to exact complex zero. Add a serialization test proving old bytes are unchanged.

- [ ] **Step 4: Add structural symmetry tests**

For both sectors and multiple random parameter seeds, verify exchange sign, chart phase, per-particle degree phase, `L²`, finite rotations, and quadrature-order stability. Inspect the parameter tree and reject any axis equal to determinant count or `dim M_L`.

- [ ] **Step 5: Run tests and commit**

```bash
uv run pytest tests/test_model.py tests/test_projector.py tests/test_carriers.py -q
git add tracks/qmc/solutions/frustration-free/challenge-15
git commit -m "Add shared projected neural Pfaffian ansatz"
```

---

### Task 8: Exact coefficient bridge and small-system NQS acceptance

**Files:**
- Modify: `src/challenge15/oracle.py`
- Modify: `src/challenge15/carriers.py`
- Create: `tests/test_exact_acceptance.py`

**Interfaces:**
- Consumes: model parameters, analytic carrier determinant coefficients, `T_L`, and ED eigensystems.
- Produces: `evaluate_exact_nqs`, `ExactNQSMetrics`.

- [ ] **Step 1: Write failing exact-metric tests**

```python
from challenge15.oracle import evaluate_exact_nqs, solve_target_sectors
from challenge15.spec import SphereSpec


def test_exact_metrics_distinguish_energy_overlap_and_true_variance(trained_n4):
    spec = SphereSpec(4)
    oracle = solve_target_sectors(spec)
    metrics = evaluate_exact_nqs(spec, trained_n4, oracle)
    assert metrics.norm_l0 > 0
    assert metrics.norm_l2 > 0
    assert 0 <= metrics.overlap_l0 <= 1
    assert 0 <= metrics.overlap_l2 <= 1
    assert metrics.h_variance_l0 >= 0
    assert metrics.h_variance_l2 >= 0
    assert metrics.bare_potential_sampling_variance is None
```

- [ ] **Step 2: Implement analytic determinant expansion**

Enumerate only `M_z=0` determinants for `N≤8`, evaluate each unprojected carrier coefficient by orbital-space Pfaffian, combine carriers, and apply the immutable target isometry. Do not recover coefficients by fitting random coordinate samples.

- [ ] **Step 3: Implement exact observables**

Normalize once and compute:

```text
E = ψ†Hψ
Var(H) = ψ†H²ψ - E²
overlap = |ψ_ED†ψ|²
L² residual and variance
projected carrier Gram singular values
```

Use dataset/chunked operations for `N=8`; never materialize a square Gram matrix in the full determinant dimension.

- [ ] **Step 4: Add projected-span and quadrature stability tests**

Report relative singular values and rank at `1e-10`; do not claim completeness unless rank equals `dim M_L`. Double both quadrature orders and require normalized coefficients and energies to change by at most `1e-11`.

- [ ] **Step 5: Run tests and commit**

```bash
uv run pytest tests/test_exact_acceptance.py tests/test_oracle.py tests/test_model.py -q
git add tracks/qmc/solutions/frustration-free/challenge-15
git commit -m "Add exact NQS to ED acceptance bridge"
```

---

### Task 9: Coordinate-space VMC sampler and unbiased estimators

**Files:**
- Create: `src/challenge15/vmc.py`
- Create: `tests/test_vmc.py`

**Interfaces:**
- Consumes: projected model amplitude and `SphereSpec`.
- Produces: `SamplerConfig`, `SphereMetropolis`, `coulomb_value`, `energy_and_score_gradient`, `SamplingDiagnostics`.

- [ ] **Step 1: Write failing measure and estimator tests**

```python
import numpy as np
from challenge15.vmc import coulomb_value, energy_and_score_gradient


def test_chord_coulomb_uses_radius_sqrt_q(spec_n4, separated_spinors):
    value = coulomb_value(separated_spinors, spec_n4)
    assert np.isfinite(value)
    assert value > 0


def test_score_covariance_is_zero_for_constant_energy():
    scores = np.array([1 + 2j, 3 - 1j, -2 + 0.5j])
    values = np.full(3, 7.0)
    _, gradient = energy_and_score_gradient(values, scores)
    np.testing.assert_allclose(gradient, 0.0, atol=1e-14)
```

- [ ] **Step 2: Implement sphere proposals**

Represent each walker by normalized spinors. Propose independent small random `SU(2)` rotations of one labeled particle and occasional rigid rotations of all particles. Adapt widths only during burn-in, freeze them for measurement, and include proposal symmetry tests.

- [ ] **Step 3: Implement Coulomb and score-covariance estimators**

Use

```text
r_ij/ℓ_B = 2√Q sqrt(1-|z_i†z_j|²)
V/E_C = Σ_(i<j) 1/(r_ij/ℓ_B)
∂θE = 2 Re[⟨Oθ*V⟩-⟨Oθ*⟩⟨V⟩].
```

Label the sample variance only as bare-potential estimator variance. Do not expose a field named `hamiltonian_variance`.

- [ ] **Step 4: Add chain diagnostics**

Implement burn-in discard, blocking autocorrelation estimates, effective sample size, split-chain `R̂`, acceptance rate, and paired-chain covariance for `E_L` and `Δ₂`. Tests use seeded Gaussian/mock log amplitudes with known stationary distributions.

- [ ] **Step 5: Compare coordinate VMC with exact sums for `N=3,4`**

Run sufficiently long seeded chains and require exact energies to lie within two combined standard errors. This is a statistical test with a fixed seed and conservative sample count, not a bitwise test.

- [ ] **Step 6: Run tests and commit**

```bash
uv run pytest tests/test_vmc.py tests/test_exact_acceptance.py -q
git add tracks/qmc/solutions/frustration-free/challenge-15
git commit -m "Add coordinate sphere VMC estimators"
```

---

### Task 10: Joint optimization, nested-rank convergence, CLI, and core report

**Files:**
- Create: `src/challenge15/train.py`
- Create: `src/challenge15/cli.py`
- Create: `tests/test_train.py`
- Create: `tests/test_cli.py`
- Create: `tests/test_end_to_end.py`
- Create: `README.md`

**Interfaces:**
- Consumes: model, exact bridge, VMC, artifact publisher.
- Produces: `TrainConfig`, `train_joint_sectors`, `analyze_rank_convergence`, CLI subcommands `oracle`, `train`, `evaluate`, `verify`, `report`.

- [ ] **Step 1: Write failing joint-training and parameter-structure tests**

```python
from challenge15.train import TrainConfig, train_joint_sectors


def test_joint_training_returns_one_parameter_tree(smoke_problem):
    result = train_joint_sectors(smoke_problem, TrainConfig(steps=3, rank=1, seed=4))
    assert result.shared_parameters is not None
    assert not hasattr(result, "parameters_l0")
    assert not hasattr(result, "parameters_l2")


def test_train_config_has_no_private_sector_model_option():
    assert "separate_sector_models" not in TrainConfig.__dataclass_fields__
```

- [ ] **Step 2: Implement deterministic smoke optimization**

Use Optax Adam for smoke tests and stochastic reconfiguration/natural-gradient preconditioning only after its covariance matrix has an eigenvalue cutoff and condition-number test. Alternate paired `L=0/2` batches, optimize

```text
loss = w0 E0 + w2 E2,
```

and store every PRNG split, optimizer state, acceptance rate, and norm diagnostic.

- [ ] **Step 3: Implement fail-closed rank convergence**

For two consecutive rank doublings require

```text
|δE_L| + 2σ_diff ≤ 1e-4 E_C
|δΔ₂| + 2σ_diff ≤ 0.002 Δ₂
```

using paired seeds/chains and retained covariance. Large uncertainty fails. For exact sums set `σ_diff=0`. Require overlap change at most `1e-3` where the oracle is available.

- [ ] **Step 4: Implement restartable CLI and atomic checkpoints**

Every command accepts a JSON configuration, computes its SHA256, refuses incompatible resume, writes checkpoints to unique partial files, verifies before replace, and records code/runtime/input provenance.

Example:

```bash
uv run python -m challenge15.cli oracle --particles 6 --output tracks/qmc/results/frustration-free/challenge-15/oracle-n6
uv run python -m challenge15.cli train --particles 6 --ranks 1,2,4 --seeds 0,1,2,3,4 --output tracks/qmc/results/frustration-free/challenge-15/n6
uv run python -m challenge15.cli verify --artifact tracks/qmc/results/frustration-free/challenge-15/n6/result.json
```

- [ ] **Step 5: Write the end-to-end smoke test**

For `N=4`, rank `1`, two optimization steps, and exact evaluation, verify:

- artifact reload and hashes;
- exact antisymmetry, degree, chart phase, and target `L`;
- one shared parameter tree;
- finite `E_0`, `E_2`, and positive `Δ₂`;
- no chirality or thermodynamic claim in the report;
- no field confusing bare-potential variance with `Var(H_LLL)`.

- [ ] **Step 6: Write README and limitation language**

Document environment creation, all CLI commands, CPU/GPU x64 checks, physical conventions, exact versus stochastic estimators, rank convergence, expected resource scaling, and the explicit statement:

```text
This core result establishes the finite-size lowest-L=2 sector gap.
It is not called a chiral graviton until the separate metric-response
acceptance plan is completed.
```

- [ ] **Step 7: Run the full core verification**

```bash
cd tracks/qmc/solutions/frustration-free/challenge-15
uv run pytest -q
uv run python -m compileall -q src tests
git diff --check
```

Expected: zero test failures, compile success, and no whitespace errors.

- [ ] **Step 8: Run `N=6`, then gated `N=7,8` production**

Run `N=6` exact oracle and ranks until acceptance. Proceed to `N=7`, then `N=8`, only if all prior symmetry, Hamiltonian, quadrature, and rank gates pass. Publish one manifest linking every accepted artifact and explicitly list any failed gate.

- [ ] **Step 9: Commit Task 10**

```bash
git add tracks/qmc/solutions/frustration-free/challenge-15
git commit -m "Complete Challenge 15 core projected Pfaffian pipeline"
```

## Deferred Independent Plans

The following work is intentionally excluded from this core plan:

1. **Chiral metric response:** finite-sphere `O^(2)_{σ,M}`, spectral functions, sum rules, and the chiral-graviton claim.
2. **Exterior-power fusion research:** CAR-compatible truncation, polynomial contraction proof, recoupling, and comparison with the projected-Pfaffian production ansatz.
3. **Beyond `N=8` scaling:** cluster profiles, distributed walkers, and finite-size extrapolation after rank growth is empirically controlled.

Each deferred subsystem requires its own reviewed design and implementation plan.

## Plan Self-Review

- Spec coverage: core physical conventions, exact symmetries, independent Coulomb oracle, projected Pfaffian model, coordinate VMC, exact acceptance, rank convergence, artifacts, and claim boundaries are assigned to Tasks 1–10.
- Scope: chiral response, fusion, and beyond-`N=8` scaling are explicitly separated.
- Completeness scan: every task names concrete files, interfaces, commands,
  expected outcomes, and failure behavior.
- Type consistency: `SphereSpec`, carrier/projector/model interfaces, exact metrics, VMC diagnostics, and CLI artifacts are introduced before use.
- Scientific separation: coordinate sampling variance and true projected-Hamiltonian variance remain distinct in every task.
