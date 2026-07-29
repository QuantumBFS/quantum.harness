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

### NQS

```python
ProjectedNQS(
    basis: FockBasis,
    total_l: int,
    shared_model,
    projection_tolerance: float = 1e-10,
)
```

Required methods:

```python
model.log_amplitude(states) -> complex_array
model.energy(parameters, hamiltonian) -> Estimate
model.l2(parameters) -> Estimate
model.equivariance_error(parameters, rotations) -> float
```

### Observables

```python
metric_response(state0, state2, helicity: int) -> complex
multiplet_report(highest_weight_state, hamiltonian) -> MultipletReport
```

Allowed helicities: `-2`, `+2`.

## Command-line API

### Run ED

```text
python -m chiral_graviton ed --n 6 --interaction coulomb --output RESULT.json
```

### Train/solve projected NQS

```text
python -m chiral_graviton nqs --n 6 --config configs/nqs-small.toml --output RESULT.json
```

### Validate a result

```text
python -m chiral_graviton validate RESULT.json
```

### Reproduce the small-system suite

```text
python scripts/reproduce_small.py --n 4 5 6 7 8 --output-dir OUTPUT_DIR
```

## JSON result schema

```json
{
  "schema_version": 1,
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
  "conventions": {}
}
```

Numeric placeholders above are replaced by computed values. JSON never stores NaN or infinity.

## Exit codes

| Exit | Meaning |
|---:|---|
| 0 | success |
| 2 | invalid configuration |
| 3 | physics invariant failure |
| 4 | solver non-convergence |
| 5 | insufficient Monte Carlo statistics |
| 6 | result-schema failure |
