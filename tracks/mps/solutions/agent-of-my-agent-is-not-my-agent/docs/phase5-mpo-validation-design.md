# Phase 5 Long-Range MPO Validation Design

## Scope

Validate the fixed compact periodized-exponential MPO before any production
DMRG or critical-point scan. The validation grid is

- `sigma = 1.75`;
- `K = 24`, `alpha = 0.5`, `r_fit = 2048`;
- `L = 8, 10, 12`;
- `Gamma = 1.2, 1.56, 2.0`.

No automatic gap search and no system above `L=12` is in scope.

The Hamiltonian convention is

```text
H = -sum_(i<j) J_L(j-i) Z_i Z_j - Gamma sum_i X_i,
```

with Pauli `X` and `Z` operators. The exact finite-ring reference is

```text
J_L(r) = L^(-1-sigma)
         [zeta(1+sigma, r/L) + zeta(1+sigma, 1-r/L)].
```

## Three validation layers

1. **Exact pair Hamiltonian ED.** Construct every pair coefficient directly
   from the periodic Hurwitz-zeta coupling and diagonalize the resulting
   finite Hamiltonian.
2. **Compact MPO dense ED.** Fit the infinite kernel deterministically,
   construct the `K=24` periodized MPO, expand that MPO to a dense matrix, and
   diagonalize it.
3. **Compact MPO DMRG.** Run the same two-site TeNPy workflow qualified by the
   nearest-neighbor Phase 4 benchmark, without changing initialization,
   convergence, truncation, or excited-state targeting conventions.

The first comparison isolates the Hamiltonian approximation:

```text
exact pair ED - compact MPO ED.
```

The second comparison isolates MPS optimization and truncation:

```text
compact MPO ED - compact MPO DMRG.
```

## Hamiltonian diagnostics

For each `L`, reconstruct the exact and compact pair-coupling tables and
retain the distance-resolved relative error. For each `(L, Gamma)` cell,
compare the explicit dense matrices and report the relative Frobenius error

```text
||H_exact - H_MPO||_F / ||H_exact||_F.
```

The Frobenius error is only a small-system implementation diagnostic. The
primary scalable MPO-accuracy metric remains the distance-resolved coupling
error against the exact Hurwitz-zeta `J_L(r)`.

Dense matrices are processed one cell at a time. At `L=12`, one real
`4096 x 4096` matrix occupies about 134 MB, so this validation remains a local
calculation below the harness resource threshold.

## Spectrum and observable comparisons

For all three layers, report where available:

- ground-state energy `E0`;
- first-excited energy `E1`;
- gap `Delta = E1 - E0`;
- translation-averaged ground-state correlation

```text
C(r) = (1/L) sum_i <Z_i Z_(i+r mod L)>,
```

  for `r=1,...,floor(L/2)`.

For `E0`, `E1`, and `Delta`, both comparisons report absolute and relative
errors. Relative errors use the earlier layer as the reference denominator:

```text
absolute error = abs(value_later - value_reference)
relative error = absolute error / abs(value_reference).
```

If a reference value is exactly zero, the relative error is recorded as
`null` in JSON and left blank in CSV rather than reported as infinite.
Relative gap error is kept separate because a small gap can amplify a modest
absolute error even when both extensive energies agree closely.

ED correlations use their respective normalized ground-state eigenvectors.
DMRG correlations use the optimized compact-MPO ground state and explicitly
average all periodic pairs, including wrapped pairs. This avoids comparing a
single-site OBC-MPS correlator with a translation-averaged ring observable.

For the DMRG layer also retain:

- ground- and excited-state variance;
- maximum discarded weight;
- maximum reached bond dimension `chi`;
- `abs(<psi0|psi1>)`;
- the complete TeNPy sweep statistics.

## Outputs

The Phase 5 command writes incrementally under `results/phase5_mpo_validation/`:

- one JSON record per `(L, Gamma)` cell;
- an aggregate JSON summary and flat CSV table;
- one distance-resolved coupling CSV per `L`;
- translation-averaged correlation CSV files;
- plots separating MPO errors from MPS errors.

The primary summary plot shows energy, gap, and `C(r)` errors in two series:
exact-pair ED versus compact-MPO ED, and compact-MPO ED versus DMRG. A
separate coupling plot shows the scalable distance-resolved MPO error.

## Acceptance

Every cell must finish all three layers and preserve positive energy ordering.
The Phase 4 excited-state checks remain active: ground/excited overlap below
`1e-10`, with variance, discarded weight, and reached `chi` reported.

The results are interpreted numerically rather than hidden behind a single
pass threshold: the report must expose both the MPO bias and MPS error for
each energy, gap, and correlation. Any MPS error comparable to or larger than
the MPO error blocks production use until the DMRG settings are converged.

## Tests

Tests will cover:

- exact pair Hamiltonian coefficients and Pauli/sign conventions;
- dense expansion of the actual TeNPy MPO;
- translation averaging, including wrapped pairs;
- separation and labeling of MPO and MPS errors;
- incremental JSON/CSV schemas;
- a reduced `L=4` end-to-end cell suitable for the test suite.
