# Challenge #15 reproduction report

## Scope

This calculation targets the Haldane-sphere problem specified by Quantum Harness
Challenge #15, using Liou *et al.* (2019) as the physics reference. It is not a
digitization of the paper's torus/disk spectral-function figures. The sphere
observable is

`Delta_N = E_N(L=2) - E_N(L=0)`

for spin-polarized LLL electrons at `2Q=3(N-1)`, with the three-dimensional
chord-distance Coulomb interaction. A state-independent neutralizing-background
term is omitted because it cancels in the same-`N` gap.

## Ansatz and solvers

Each determinant is an ordered occupation bit string in the monopole-harmonic
shell, so fermionic antisymmetry is exact. A one-hidden-layer MLP has a shared
trunk and separate scalar heads for the `Lz=0` and `Lz=2` sectors. Each raw head
is orthogonally projected onto `ker(L_+)`; the resulting states are therefore
exact `L=0` and `L=2` highest weights. Both heads are optimized together by
L-BFGS on their mean energy.

The ED oracle builds the same pair-pseudopotential Hamiltonian. For smaller
sectors it diagonalizes in the dense highest-weight null space. For larger
sectors it uses a sparse positive `L^2` penalty in the `M=L` sector, then reports
the expectation of the physical Hamiltonian and rejects a state unless its
`<L^2>` matches `L(L+1)`.

The NQS estimator also draws independent samples from its enumerated `|psi|^2`
distribution. Because these are exact independent draws, burn-in and
autocorrelation corrections are zero. This is a validation VMC path, not a
claim of scalable sampling beyond the enumerated Hilbert space.

## Neutral-gap results

Energies are in `e^2/(epsilon*l_B)`.

| N | 2Q | ED gap | NQS gap | absolute NQS-ED error | sampled gap +/- 1 s.e. |
|---:|---:|---:|---:|---:|---:|
| 3 | 6 | 0.1189915765 | 0.1189915765 | 4.44e-16 | 0.1189915765 +/- 9.06e-19 |
| 4 | 9 | 0.1318567549 | 0.1318567549 | 2.22e-16 | 0.1318567549 +/- 2.65e-13 |
| 5 | 12 | 0.1261720638 | 0.1261720638 | 4.44e-16 | 0.1261720638 +/- 1.06e-12 |
| 6 | 15 | 0.1316884120 | 0.1316884120 | 2.14e-12 | 0.1316884120 +/- 1.68e-9 |
| 7 | 18 | 0.1291980978 | 0.1291980978 | 4.96e-13 | 0.1291980969 +/- 1.85e-9 |
| 8 | 21 | 0.1287852882 | - | - | - |

The `N=8` fixed-`Lz` ED dimensions are 8512 (`Lz=0`) and 8439 (`Lz=2`), with
eigenpair residuals below `2.0e-11`. Exact dense angular-momentum projection in
the current NQS becomes the bottleneck at this size, so the NQS validation stops
at `N=7` rather than presenting an uncontrolled result.

## Spin-2 and equivariance certification

For `N=7`, the lowest `L=2,M=2` state was lowered four times with the exact
many-body `L_-` operator. The five energies for `M=2,1,0,-1,-2` are

`[5.189720805604572, 5.189720805604571, 5.189720805604573,
  5.189720805604574, 5.189720805604575]`.

Their spread is `4.44e-15`, and every `<L^2>` is 6 within `2e-14`. A coherent
superposition was rotated about the generic axis `(1,2,3)/sqrt(14)` by 0.371
radians in the many-body Fock representation and in the analytic spin-2
representation. The norm of their difference is `9.43e-12`.

## Finite-size estimate

A least-squares fit `Delta_N = Delta_infinity + a/N` over `N=4..8` gives

`Delta_infinity = 0.1274 +/- 0.0048`,

with residual RMS `0.00203`. The quoted uncertainty is the regression standard
error only; it does not cover the choice of finite-size ansatz or the pronounced
even/odd oscillation. It should therefore be read as a small-size extrapolation,
not a thermodynamic-limit precision result.

The `0.07-0.105` interval in Liou *et al.* was inferred from spectral-response
peaks on a torus with sample-specific finite-thickness Coulomb effects. The
present pure chord-Coulomb sphere level gap is a different finite-size observable,
so the numbers are not expected to coincide directly.

## Acceptance matrix

| Deliverable | Evidence | Status |
|---|---|---|
| antisymmetric NQS | ordered fermionic Fock determinants | pass |
| SO(3)-equivariant NQS | exact `ker(L_+)` projection and generic rotation check | pass |
| `E(L=0)`, `E(L=2)`, and gap | `N=3..7` NQS; `N=3..8` ED | pass |
| MC error bars | 100,000 direct independent samples per sector | pass |
| `<L^2>=6` | NQS/ED result JSON and multiplet report | pass |
| fivefold degeneracy | `N=7` spread `4.44e-15` | pass |
| small-`N` ED cross-check | maximum gap error `2.14e-12` for `N=3..7` | pass |
| strong-version extrapolation | linear `1/N` fit over `N=4..8` | pass, bounded |
| bright/dark chirality response | not evaluated | optional, not claimed |
| beyond-ED NQS scaling | not implemented by enumerated ansatz | not claimed |

The base acceptance deliverables are complete. The paper's helicity-resolved
metric spectral function is deliberately left out: total `L=2` does not by
itself determine chirality, and labeling `M=+/-2` as bright/dark would be
incorrect.

## Reproduction

From `tracks/qmc/solutions/Plasma-Team`:

```powershell
& powershell -NoProfile -ExecutionPolicy Bypass -File scripts/run_acceptance.ps1
```

The accepted artifacts from this run are under
`tracks/qmc/results/20260729-chiral-graviton-final/`:

- `ed-n3.json` through `ed-n8.json`;
- `nqs-n3.json` through `nqs-n7.json`;
- `multiplet-n7.json`;
- `gap_table.csv`;
- `scaling_fit.json`.

Random seed: `1729`. Runtime: CPython 3.12.12, NumPy 2.5.1, SciPy 1.18.0,
SymPy 1.14.0, pytest 9.1.1.
