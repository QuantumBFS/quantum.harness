# Chiral Graviton Computational API

This document defines the Python and command-line interfaces. It is a scientific-computing API, not a web service.

## Python API

### `SphereSystem`

```python
SphereSystem.from_electron_count(n_electrons: int) -> SphereSystem
```

Fields: `n_electrons`, `two_q`, `n_orbitals`, `radius_over_lb`.

Invariant: `two_q == 3 * (n_electrons - 1)`.

### `FockBasis`

```python
FockBasis(system: SphereSystem, two_lz: int) -> FockBasis
```

Returns ordered fermionic determinants represented as Python integers. The `two_lz` convention avoids half-integer floating-point labels.

Core methods:

```python
basis.states: tuple[int, ...]
basis.index: dict[int, int]
basis.dimension: int
basis.occupied(state: int) -> tuple[int, ...]
```

### Fermionic operators

```python
apply_annihilation(state: int, orbital: int) -> tuple[int, int] | None
apply_creation(state: int, orbital: int) -> tuple[int, int] | None
apply_one_body(state: int, create: int, annihilate: int) -> tuple[int, int] | None
apply_two_body(state: int, a: int, b: int, c: int, d: int) -> tuple[int, int] | None
```

Each successful call returns `(new_state, sign)`.

### Angular momentum

```python
angular_momentum_raising(source: FockBasis, target: FockBasis) -> scipy.sparse.csr_matrix
angular_momentum_lowering(source: FockBasis, target: FockBasis) -> scipy.sparse.csr_matrix
l2_operator(basis: FockBasis) -> scipy.sparse.csr_matrix
```

`l2_operator` is dimensionless with eigenvalues `L(L+1)`.

### Interactions

```python
v1_pseudopotentials(two_q: int) -> dict[int, float]
coulomb_pseudopotentials(two_q: int) -> dict[int, float]
pair_matrix_elements(two_q: int, pseudopotentials: dict[int, float]) -> PairTable
```

Pseudopotential keys are odd relative angular momenta. Coulomb values use `e^2/(epsilon l_B)`.

### Hamiltonian

```python
build_hamiltonian(basis: FockBasis, pair_table: PairTable) -> scipy.sparse.csr_matrix
```

The returned operator excludes any state-independent neutralizing-background constant.

### ED

```python
solve_sector(
    basis: FockBasis,
    hamiltonian,
    n_eigenpairs: int = 8,
    tolerance: float = 1e-11,
) -> SectorSpectrum
```

`SectorSpectrum` stores energies, eigenvectors, `<L^2>`, assigned `L`, and residual norms.

```python
neutral_gap(system: SphereSystem, interaction: str = "coulomb") -> GapResult
```

`GapResult` fields include `e_l0`, `e_l2`, `gap`, sector sizes, residuals, and conventions.

The independent acceptance kernel is intentionally limited to `N<=4` and does
not import the production basis, CG/Wigner, Hamiltonian, or ED modules:

```python
oracle_neutral_gap(n_electrons, x_order=64, phi_points=256) -> IndependentOracleResult
```

### NQS

```python
SharedProjectedMLP.build(
    system: SphereSystem,
    interaction: str = "coulomb",
    hidden_width: int = 24,
    seed: int = 1729,
) -> SharedProjectedMLP
```

Core methods:

```python
model.fit(max_iterations=400) -> NQSTrainingResult
model.vector(parameters, total_l) -> numpy.ndarray
model.estimate(parameters, total_l) -> NQSEstimate
model.sample_energy(parameters, total_l, n_samples=50000, seed=1729) -> MonteCarloEstimate
model.irrep_error(parameters) -> float
model.scalar_rotation_error(parameters) -> float
model.multiplet_rotation_error(parameters) -> float
```

`irrep_error` measures the projected output state's L² deviation.  It does NOT
test whether the raw neural network is input-equivariant.  For genuine
rotation-equivariance verification, use `scalar_rotation_error` (checks
L₋|ψ₀⟩≈0 for the L=0 ground state) and `multiplet_rotation_error`
(constructs the full L=2 multiplet and compares finite-rotation behaviour
against the spin-2 Wigner-D transformation).

Allowed `total_l` values are `0` and `2`. The final vectors are numerical
highest-weight projections with checked residuals, not penalty-only approximations. This is an
output-state SO(3) projection; the bit-string input MLP is not itself a
coordinate-space equivariant architecture.

For larger enumerated sectors:

```python
SparseProjectedMLP.build(system, interaction="coulomb") -> SparseProjectedMLP
model.projection_certificate(parameters, total_l) -> ProjectionCertificate
```

`SparseHighestWeightProjector` applies
`I-L_+^dagger(L_+L_+^dagger)^(-1)L_+` with sparse conjugate gradients and never
constructs `highest_weight_basis`.

### Observables

```python
multiplet_report(highest_basis, highest_vector, total_l, pair_table) -> MultipletReport
transition_weight(initial, final, operator) -> float
chirality_ratio(bright_weight, dark_weight) -> float
chiral_weights(basis, state) -> ChiralWeights
chiral_graviton_response(ground_basis, ground, graviton_basis, graviton) -> ChiralGravitonResponse
train_nqs_chirality(system, interaction="coulomb", projection="dense") -> NQSChiralityResult
```

`multiplet_report` returns all `M` values, their energies and `<L^2>`, the energy
spread, and a generic-axis rotation-equivariance error. The chiral response uses
the rank-two `m=1<->3` Laughlin parent-channel proxy. `train_nqs_chirality`
evaluates that proxy with trained projected NQS states; it is still not the full
finite-sphere Coulomb metric derivative.

## Command-line API

### Run ED

```text
python -m chiral_graviton ed --n 6 --interaction coulomb --output RESULT.json
```

### Run the independent small-system oracle

```text
python -m chiral_graviton oracle --n 4 --output ORACLE.json
```

This route is intentionally limited to `N=2..4` and uses its own
first-quantized Coulomb quadrature, pair projectors, determinant basis, and
diagonalizer rather than the production ED/NQS Hamiltonian kernel.

### Train/solve projected NQS

```text
python -m chiral_graviton nqs --n 6 --samples 100000 --output RESULT.json
```

Use `--projection sparse` for `N=8,9`.

### Certify the spin-2 multiplet

```text
python -m chiral_graviton multiplet --n 7 --output MULTIPLET.json
```

### Certify the NQS tower and chirality

```text
python -m chiral_graviton nqs-multiplet --n 7 --projection sparse --output NQS_MULTIPLET.json
python -m chiral_graviton chirality --n 7 --interaction coulomb --output CHIRALITY.json
python -m chiral_graviton nqs-chirality --n 7 --projection sparse --output NQS_CHIRALITY.json
python -m chiral_graviton nqs-chirality --n 4 --interaction coulomb --output NQS_CHIRALITY.json
```

`chirality` uses ED states; `nqs-chirality` trains projected NQS states and
evaluates the same parent-channel proxy.

### Validate a result

```text
python -m chiral_graviton validate RESULT.json
```

### Reproduce the small-system suite

```text
python scripts/reproduce_small.py --n 4 5 6 7 8 --output-dir OUTPUT_DIR
```

The finite-size regression/reproduction suite is available as
`powershell -File scripts/run_acceptance.ps1`.

## JSON result schema

```json
{
  "schema_version": 2,
  "status": "complete",
  "method": "ed",
  "n_electrons": 6,
  "two_q": 15,
  "interaction": "coulomb",
  "energy_unit": "e^2/(epsilon*l_B)",
  "e_l0": 0.0,
  "e_l2": 0.0,
  "gap": 0.0,
  "l2_excited": 6.0,
  "residual_norms": [],
  "seed": 1729,
  "software": {},
  "provenance": {
    "timestamps": {}, "software": {}, "platform": {}, "git": {},
    "run_config": {}, "tolerances": {}
  },
  "conventions": {}
}
```

Numeric placeholders above are replaced by computed values. JSON never stores
NaN or infinity. A numerically finite but rejected calculation is written with
`status: failed` and `quality_errors`; `validate` accepts only complete results.

## Exit codes

| Exit | Meaning |
|---:|---|
| 0 | success |
| 2 | invalid configuration |
| 3 | optimizer or scientific-quality gate failure |
| 4 | non-finite numerical result |
| 6 | result-schema failure |
