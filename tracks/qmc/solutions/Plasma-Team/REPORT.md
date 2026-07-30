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
is orthogonally projected onto `ker(L_+)`; the resulting states are numerical
`L=0` and `L=2` highest weights with acceptance-gated residuals. Both heads are optimized together by
L-BFGS on their mean energy.

The production ED cross-check builds the same pair-pseudopotential Hamiltonian
as NQS. A second implementation independently integrates Coulomb
pseudopotentials in first quantization, constructs pair projectors from
polynomial highest weights, and assembles its own determinant Hamiltonian for
`N=3,4`. For `N=5..8`, ED remains a precise but shared-kernel cross-check. For smaller
sectors it diagonalizes in the dense highest-weight null space. For larger
sectors it uses a sparse positive `L^2` penalty in the `M=L` sector, then reports
the expectation of the physical Hamiltonian and rejects a state unless its
`<L^2>` matches `L(L+1)`.

For `N>=8`, the dense null-space basis is replaced by the matrix-free projector

`P = I - L_+^dagger (L_+ L_+^dagger)^(-1) L_+`,

applied with sparse conjugate gradients. The reported `||L_+ psi||/||psi||`
directly certifies the target irrep; no ED eigenvector or `L^2` penalty enters
the ansatz. The NQS diagnostic also draws independent samples from its enumerated `|psi|^2`
distribution. Because these are posterior IID draws from a fully enumerated
distribution, burn-in and autocorrelation corrections are zero. This is an
exact-sampling estimator check, not a scalable VMC/MCMC implementation.

## Neutral-gap results

Energies are in `e^2/(epsilon*l_B)`.

| N | 2Q | ED gap | NQS gap | absolute NQS-ED error | sampled gap +/- 1 s.e. |
|---:|---:|---:|---:|---:|---:|
| 3 | 6 | 0.1189915765 | 0.1189915765 | 4.44e-16 | 0.1189915765 +/- 9.06e-19 |
| 4 | 9 | 0.1318567549 | 0.1318567549 | 2.22e-16 | 0.1318567549 +/- 2.65e-13 |
| 5 | 12 | 0.1261720638 | 0.1261720638 | 4.44e-16 | 0.1261720638 +/- 1.06e-12 |
| 6 | 15 | 0.1316884120 | 0.1316884120 | 2.14e-12 | 0.1316884120 +/- 1.68e-9 |
| 7 | 18 | 0.1291980978 | 0.1291980978 | 4.96e-13 | 0.1291980969 +/- 1.85e-9 |
| 8 | 21 | 0.1287852882 | 0.1287852882 | 2.42e-12 | 0.1287852863 +/- 2.06e-9 |
| 9 | 24 | - | 0.1305092442 | - | 0.1305092418 +/- 6.64e-9 |

The `N=8` fixed-`Lz` ED dimensions are 8512 (`Lz=0`) and 8439 (`Lz=2`), with
eigenpair residuals below `2.0e-11`. The `N=9` NQS dimensions are 45207 and
44938. Its sparse-projection residuals are `1.92e-10` (`L=0`) and `4.05e-11`
(`L=2`). There is no independent `N=9` reference. It has low variance within
the current enumerated ansatz and single-run optimizer tolerance, but is not
independently validated and is not thermodynamic-scale VMC evidence.

## Spin-2 output-projection certification

For `N=7`, both the ED state and the NQS `L=2,M=2` head were lowered four times
with the exact
many-body `L_-` operator. The five energies for `M=2,1,0,-1,-2` are

`[5.189720805604572, 5.189720805604571, 5.189720805604573,
  5.189720805604574, 5.189720805604575]`.

The ED spread is `4.44e-15`; the NQS-only spread is `1.78e-15`, and every NQS
`<L^2>` is 6 within `1.1e-14`. A coherent
superposition was rotated about the generic axis `(1,2,3)/sqrt(14)` by 0.371
radians in the many-body Fock representation and in the analytic spin-2
representation. The NQS tower rotation error is `8.16e-13`.

This certifies the projected output state and its spin-2 tower. It does not make
the determinant-bit-string input MLP a coordinate-space SO(3)-equivariant
network.

## Bright/dark chirality

Motivated by Liou *et al.*, finite-sphere parent-channel proxies are implemented as
a rank-two spherical tensor: dark `O_+` maps relative pair momentum `m=1` to
`m=3` with `q=+2`; bright `O_-` is its exact adjoint and maps `m=3` to `m=1`
with `q=-2`. All five components pass the rank-two SU(2) ladder commutator.

For the `N=4` `V1` Laughlin zero mode, the integrated dark weight is
`4.4e-32`, while the bright weight is `0.919`; 98.6% of the bright weight lies
in the lowest `L=2` pole. For `N=7` Coulomb:

- integrated bright weight: `1.74983`;
- integrated dark weight: `0.00284036`;
- integrated bright/dark ratio: `616.1`;
- fraction of bright weight in the lowest `L=2` pole: `77.4%`;
- lowest-pole bright/dark ratio: `1442.9`.

This identifies the computed lowest spin-2 level as the dominant chiral pole
inside this ED parent-channel proxy. Absolute weights depend on the common reduced
matrix-element normalization. The operator is a finite-sphere `m=1<->3`
Laughlin parent-channel proxy motivated by the paper, not its full momentum-space
operator and not a metric derivative of the finite-sphere Coulomb Hamiltonian.
The same parent-channel proxy can also be evaluated from trained projected NQS
states via `train_nqs_chirality`; this closes the previous ED-only evaluation
path but does not upgrade the observable into the full Coulomb metric derivative.
For the reviewed `N=7` sparse run, the NQS-native result has gap
`0.1291980978231`, integrated bright/dark ratio `616.061`, bright lowest-pole
fraction `0.774345`, and projected-irrep error `1.38e-14`.

## Finite-size estimate

A least-squares fit `Delta_N = Delta_infinity + a/N` over `N=4..9` gives

`Delta_infinity = 0.1289 +/- 0.0035`,

with residual RMS `0.00193`. Linear even and odd subsequences give `0.1269` and
`0.1361`, while a quadratic fit gives `0.1422`. The maximum displacement from
the primary fit is `0.0134`; this small-size model envelope is more honest than
the regression error alone. The result is exploratory, not a controlled
thermodynamic-limit precision prediction.

The `0.07-0.105` interval in Liou *et al.* was inferred from spectral-response
peaks on a torus with sample-specific finite-thickness Coulomb effects. The
present pure chord-Coulomb sphere level gap is a different finite-size observable,
so the numbers are not expected to coincide directly.

## Review remediation status

| Review finding | Remediation |
|---|---|
| optimizer/NaN/threshold failures could exit 0 | fixed: failed JSON plus nonzero exit; non-finite JSON is never written |
| base/research verifiers could print a low score and exit 0 | fixed: both exit nonzero; the review gate tests the failure path |
| incomplete environment/run provenance | fixed: dependency lock plus timestamps, platform, Git, config, and tolerances |
| ED was not an independent oracle | fixed for `N=3,4` with a separate first-quantized/determinant kernel |
| chirality used ED states only | fixed state-source path: `nqs-chirality` uses trained NQS vectors |
| claimed equivariance exceeded the evidence | corrected: output irrep passes; input equivariance is not implemented |
| enumerated optimization was called scalable VMC | corrected: posterior IID diagnostic and enumerated bridge only |
| full Coulomb metric derivative and controlled extrapolation | still open; explicitly partial below |

## Acceptance matrix

| Deliverable | Evidence | Status |
|---|---|---|
| antisymmetric NQS | ordered fermionic Fock determinants | pass |
| SO(3)-projected NQS output | `ker(L_+)` residual and generic rotation check | pass |
| input-equivariant neural network | raw bit-string MLP has no rotation action | not implemented |
| `E(L=0)`, `E(L=2)`, and gap | `N=3..9` NQS; `N=3..8` ED | pass |
| posterior sampling SEM | 100,000 IID samples at one optimized parameter vector | partial, diagnostic only |
| `<L^2>=6` | NQS/ED result JSON and multiplet report | pass |
| fivefold degeneracy | `N=7` NQS spread `1.78e-15` | pass |
| independent small-`N` oracle | separate first-quantized kernel at `N=3,4`, agreement within `2e-5` | pass |
| shared-kernel ED cross-check | maximum gap error `2.14e-12` for `N=3..7` | pass for `N=3..8` |
| thermodynamic extrapolation | model comparison over `N=4..9` | partial, exploratory/model-sensitive |
| bright/dark chirality response | ED and NQS state paths | partial, parent-channel proxy only |
| NQS beyond completed ED sizes | sparse projected `N=9` result | one size beyond current ED run; still enumerated |

The finite-size gap, projected-irrep, multiplet, fail-closed validation, and
small-system independent-oracle components have machine-checked evidence. A
non-enumerated autoregressive/MCMC ansatz, an input-equivariant network, the full
Coulomb metric-derivative spectral function, and a controlled `N->infinity`
limit remain unimplemented and are not claimed here.

## Reproduction

From `tracks/qmc/solutions/Plasma-Team`:

```powershell
& powershell -NoProfile -ExecutionPolicy Bypass -File scripts/run_acceptance.ps1
```

The generated finite-size artifacts from this run are under
`tracks/qmc/results/20260729-chiral-graviton-final/`:

- `ed-n3.json` through `ed-n8.json`;
- `nqs-n3.json` through `nqs-n7.json`;
- `multiplet-n7.json`;
- `gap_table.csv`;
- `scaling_fit.json`.

Strong-version artifacts are under
`tracks/qmc/results/20260729-chiral-graviton-strong/`, including the `N=8,9`
sparse NQS, NQS multiplet, chirality, combined table, and fit-model comparison.

Review-remediation evidence is under
`tracks/qmc/results/20260730-graviton-review/`: independent `N=3,4` oracle JSON
and the `N=7` NQS-native parent-channel response. Generated results are ignored
by Git; the commands and schema are versioned in this solution directory.

Random seed: `1729`. Runtime: CPython 3.12.12, NumPy 2.5.1, SciPy 1.18.0,
SymPy 1.14.0, pytest 9.1.1.

Newly generated CLI JSON also embeds an exact run configuration, acceptance
tolerances, timestamp, platform, dependency versions, and Git commit/dirty
state. Failed runs are retained as `status: failed` diagnostics and are rejected
by `validate`; NaN and infinity are never serialized.

## CPMC-Lab Figure 4(a-c) addendum

The official MATLAB route now contains all nine integer interaction points.
Figure 4(a) plots all nine total energies rather than the earlier even-grid
subset. Panels (b,c) use independent cross-U statistical propagation and quote
the absolute three-point versus five-point derivative difference separately as
a finite-difference systematic contribution. `mc_diagnostics.csv` records
lag-one autocorrelation, an initial-positive-sequence effective sample size,
blocking standard errors, and a split-half drift diagnostic. The ED readback is
stored in `cpmc_lab_fig4/ed_digitized_fig4.csv` with provenance; it is a
digitized paper reference, not a local ED calculation.
