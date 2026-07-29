# Methodology

Framework: TeNPy. Language: Python 3.11. Method: MPS/DMRG. The production
Hamiltonian will use a custom periodized exponential MPO.

This document records the pinned Hamiltonian convention, exponential
decomposition, periodic MPO construction, validation criteria, and separate
Hamiltonian/MPS error budgets. Phase 1 is framework-independent and constructs
the exact finite-ring coupling that later TeNPy MPOs must reproduce.

## Runtime dependencies

Run with the existing `mps` conda environment. It must import `tenpy`, `numpy`,
and `scipy`; TeNPy is sourced from `~/tenpy`. Do not create a separate project
environment.

## Exact finite-size reference

For `p = 1 + σ`, ring length `L`, and integer separation `1 ≤ r < L`,

```text
J_L(r) = Σ_{n∈ℤ} |r+nL|^(-p)
       = L^(-p) [ζ(p, r/L) + ζ(p, 1-r/L)].
```

The implementation must validate positivity, periodic symmetry
`J_L(r) = J_L(L-r)`, and agreement with a directly truncated image sum. The
open-chain value `r^(-p)` is not the finite-size reference.

## Exponential decomposition

Phase 2 fits only `f(r) = r^(-p)` on integer distances `1 <= r <= r_fit`.
For fixed bounded decays `0 < lambda_k < 1`, nonnegative coefficients are
solved by least squares against the relative residual. The logarithms of the
decay rates are then optimized deterministically by variable projection.

The coefficient solve uses nonnegative least squares rather than unconstrained
least squares. A power law with `p > 0` is completely monotone and has a
positive Laplace representation, so a faithful exponential discretization
should have `c_k >= 0`. Negative coefficients can cancel positive terms inside
the finite fit window and produce an excellent apparent residual there, while
the slowest negative exponential dominates differently outside the window.
Analytical periodization sums that uncontrolled tail over infinitely many
images, turning the cancellation into a systematic finite-ring bias.
Positivity prevents this failure mode, keeps every exponential channel
ferromagnetic, and makes the periodized reconstruction stable and
interpretable.

The fitted infinite-chain expansion is periodized without refitting:

```text
J_tilde_L(r) =
  sum_k c_k [lambda_k^r + lambda_k^(L-r)] / [1-lambda_k^L].
```

Kernel and periodic maximum/RMS relative errors are reported separately.
Distance-resolved profiles preserve where the largest errors occur. The
default validation uses `L=64`, `sigma=1.75`, `r_fit=512`, and
`K=8,12,16,20,24`.

For each K, the periodic JSON summary also records the global maximum and its
distance. Regional maximum and RMS relative errors are reported for the
short-distance window `r=1,...,10` and the central five distances
`r=L/2-2,...,L/2+2`. Equal symmetry-related global maxima are represented by
the smaller distance.

### Fixed-window K convergence

At `L=64`, `sigma=1.75`, and `r_fit=512`, increasing K through 20 and 24
continues to reduce the fitted-kernel error, but the analytically periodized
error approaches a floor near `2e-4`. From K=20 to K=24, the kernel RMS error
falls from `1.90e-7` to `2.70e-8`, while the periodized maximum changes only
from `2.01e-4` to `1.95e-4` and remains at `r=32`. The central-region RMS
similarly changes only from `1.99e-4` to `1.94e-4`.

This is a fixed-`r_fit` tail plateau, not saturation of the exponential basis
inside the fitted interval. Adding exponentials no longer controls the
geometric image tail beyond `r_fit`; reducing this floor requires a
longer-distance fitting protocol or an explicit tail constraint, rather than
K alone.

### Tail-window study

The follow-up scan holds `L=64` and `sigma=1.75` fixed, uses `K=16,24`, and
varies `r_fit=512,1024,2048`. For K=24, extending the window from 512 to 1024
reduces the periodized maximum relative error from `1.95e-4` to `1.72e-5`
while the maximum remains at `r=32`. This confirms that the earlier
approximately `2e-4` floor is caused by the finite fitting window rather than
by a lack of exponential terms.

Naively extending the same optimization is not monotone or robust. At
`r_fit=2048`, the K=24 periodized maximum returns to `2.03e-4`. More
dramatically, the K=16 fits at 1024 and 2048 have small in-window kernel
errors but periodized maximum errors of about `1.18e2` and `1.27e2`. In those
fits, nonnegative least squares assigns a tiny positive coefficient to a
decay with `lambda` extremely close to one. Its contribution is harmless on
the finite fit grid but is amplified after periodization by
`1/(1-lambda^L)`.

Coefficient positivity is therefore necessary but not sufficient. Every fit
must be validated after analytical periodization, and production fitting
needs an additional tail-control condition, such as a physically motivated
lower bound on `-log(lambda)`, explicit long-distance samples, or a tail
penalty. Selecting `r_fit=1024, K=24` solely because it is the best point in
this scan would be premature until that stability condition is defined and
tested.

### Correlation-length-bound study

The stable redesign constrains every decay rate by
`a_k=-log(lambda_k) >= alpha/r_fit`, while retaining the same relative-error
objective on the infinite-chain kernel and the same nonnegative least-squares
coefficient solve. The scan uses `alpha=0.25,0.5,1.0`, `K=16,24`, and
`r_fit=512,1024,2048`. Every JSON cell records the full lambda/rate spectrum
and verifies `a_min*r_fit >= alpha`.

The constraint removes the near-unit-lambda catastrophes in all 18 cells.
The most stable branch is `alpha=0.5, K=24`: as `r_fit` increases, the
periodized maximum relative error decreases monotonically from `8.98e-5` to
`3.13e-5` to `8.28e-6`, with the maximum at `r=32`. The corresponding kernel
RMS errors are `1.30e-8`, `2.53e-8`, and `3.65e-8`; the modest increase is the
cost of fitting a longer interval under fixed K.

Against the unconstrained K=24 baseline, `alpha=0.5` improves the periodized
maximum at `r_fit=512` (`1.95e-4` to `8.98e-5`) and at 2048 (`2.03e-4` to
`8.28e-6`). At 1024 it is slightly worse than the unusually favorable
unconstrained cell (`3.13e-5` versus `1.72e-5`), but it belongs to a monotone,
tail-stable sequence rather than an isolated optimum.

The result remains sensitive to K. K=16 is stabilized—its order-`1e2`
periodization failures disappear—but its best errors remain around `1e-4`,
and the maximum can move back to short distance at `r_fit=2048`. K=24 is
therefore the supported compact representation for the next validation
stage, with `alpha=0.5` as the preferred tail constraint. The full
lambda/rate spectra must remain part of every run record; the scalar coupling
error alone cannot diagnose a mode approaching lambda one.

## Periodized exponential MPO

The finite TeNPy MPO uses open virtual boundaries; the ring geometry is
encoded entirely in the pair coefficients. For zero-based `i<j`, each
exponential contributes two graph states:

- direct: open with `lambda_k Sigmaz`, propagate with `lambda_k Id`, and
  close with `-A_k Sigmaz`;
- wrapped: open with `lambda_k^i Sigmaz`, propagate with `Id`, and close with
  `-A_k lambda_k^(L-j) Sigmaz`.

Here `A_k=c_k/(1-lambda_k^L)`. The wrapped factorization avoids both inverse
lambda propagation and products of huge and tiny numbers. The transverse
field is the direct graph edge `-Gamma Sigmax`. Pauli operators are required:
using TeNPy's `Sx` or `Sz` would change the normalization.

The uncompressed bulk MPO bond dimension is `2K+2`, equal to 50 for K=24.
Before any DMRG, small-L tests contract the actual MPO to a dense matrix and
recover every pair coefficient with the Pauli Hilbert-Schmidt projection
`Tr(H Sigmaz_i Sigmaz_j)/2^L`. This independently validates the direct and
wrapped paths, signs, field normalization, and the complete fitted
periodized coupling table.

## Planned validation layers

1. Exact periodic Hurwitz-zeta coupling.
2. Exponential fitting and periodization.
3. MPO coefficient reconstruction.
4. Small-system observable comparison.
5. Independent `K` and `χ` convergence in DMRG scaling.

No DMRG or many-body observable calculation is included at this stage.
## Phase 4 DMRG qualification

The DMRG implementation is qualified first on the periodic nearest-neighbor
Pauli TFIM, `H = -Σ_i Z_i Z_(i+1) - Γ Σ_i X_i`, at `Γ=1`. A compact finite
MPO carries the closing `(L-1,0)` bond while the MPS remains open-boundary.
The same two-site sweep settings and diagnostic collection are used later for
the periodized long-range MPO.

At `L=8,10,12`, sparse ED supplies strict references for `E0`, `E1`, the gap,
and `ZZ` correlations. Ground-state DMRG uses both z- and +x-polarized starts.
The first excited state is optimized separately with TeNPy's
`orthogonal_to=[psi0]`; its energy, positive ordering, overlap, variance, and
ED agreement must all pass before scaling work begins. The benchmark also
plots `L Delta(L)` at `Gamma=1`, which should approach a constant for `z=1`.

Variance below `1e-10` is a small-system benchmark acceptance criterion, not
a universal production cutoff. Large systems will instead report variance,
maximum discarded weight, and convergence under increasing `chi` together.

## Phase 5 three-layer MPO validation

At `sigma=1.75`, the fixed `K=24`, `alpha=0.5`, `r_fit=2048` MPO is checked
for `L=8,10,12` and `Gamma=1.2,1.56,2.0`. Exact Hurwitz-pair ED is compared
first with ED of the actual dense-expanded MPO, isolating Hamiltonian
compression error. The latter is then compared with DMRG on that same MPO,
isolating MPS optimization and truncation error.

Both absolute and reference-relative errors are retained for `E0`, `E1`, and
the gap. The ground-state correlation is translation averaged around the
ring, `C(r)=(1/L) sum_i <Z_i Z_(i+r)>`, in all three layers. The primary MPO
diagnostics are the distance-resolved coupling residual, low-energy spectrum,
and `C(r)`. Relative Frobenius matrix error is reported only for these small
dense systems and is not used as a production-scale accuracy measure.

## Phase 6 validated local reproduction

The local campaign fixes `sigma=1.75`, `L=32,64`, and the two-point crossing
bracket `Gamma=1.560,1.565`. It uses the rotated parity basis, the full
physical correlation function without connected-correlation subtraction,
exact-zero MPO pruning, and HDF5 checkpoints. It does not extrapolate to the
thermodynamic limit.

MPS uncertainty is isolated at `L=64`, `K=24` by fully reoptimizing the even
and odd states at `chi=256` from audited `chi=128` initialization tensors.
The historical and current code hashes are both recorded. Hamiltonian
parameters, fit-file and coefficient hashes, active MPO channels, operator
convention, parity, and serialized lattice structure must match before an
old MPS can seed optimization. Historical energies and observables are never
promoted to current-code results.

MPO uncertainty is isolated at common `chi=128` by independently optimizing
`K=24` and `K=32` states. The Hamiltonian-level comparison retains the full
distance-resolved Hurwitz-zeta residual. The physics-level comparison uses
the same signed differences
`R_xi(32,Gamma)-R_xi(64,Gamma)` and the same neighboring-point linear
interpolation for both K values, together with gap comparisons at both sizes
and both Gamma values.

The qualitative stability criterion is internal: the single fixed-bracket
crossing must persist, gaps must remain positive, and the measured chi/K
shifts must be reported separately. Agreement with a published
thermodynamic-limit critical field or dynamic exponent is not an acceptance
condition.

## Phase 7 crossover exploration

The validated local reproduction motivates an inexpensive first map over
`sigma=1.50,1.60,1.70,1.75,1.80,1.90,2.00`. Exploration fixes `K=24`,
`chi=64`, and `L=32,64`. All sigma values share the preregistered broad grid
`Gamma=1.20:0.05:1.90`. A unique observed R_xi crossing bracket is linearly
interpolated, with half the endpoint spacing recorded as the grid-resolution
indicator. The deadline-bounded deliverable does not execute the proposed
narrow refinement.

Unresolved brackets remain unresolved. Cells with failed convergence,
excess relative variance or discarded weight, invalid second-moment data,
or nonpositive gap behavior are marked for selective `chi=128` validation
without being silently replaced. The scan provides no thermodynamic-limit
claim; its purpose is to identify where additional sigma resolution is
scientifically useful.

The final gap analysis reoptimizes only the odd sector at `chi=128` at the
two existing broad-bracket endpoints. Compatible `chi=64` tensors seed the
three required sigma values but are never reused as final states. Gaps are
interpolated to the unchanged broad crossing. The resulting two-size
`z_eff=-log(Delta_64/Delta_32)/log(2)` is accepted at
`sigma=1.75,1.80,2.00`; `sigma=1.60` is retained as incomplete because the
two `L=64` odd states retain discarded-weight flags.

For the minimal structure-factor analysis, `S(0)` from the completed
even-sector endpoint states is interpolated to the same broad crossing.
The reported quantity is
`log[S_64(0)/S_32(0)]/log(2)`. Because this uses the equal-time spatial
structure factor rather than the imaginary-time-integrated susceptibility,
it is an auxiliary equal-time exponent and is not labeled `gamma/nu`. MPO,
MPS, and finite-size uncertainties remain separate in the final report, with
the two-size limitation dominant.

## Phase 8 sigma=1.75 finite-size scaling

Phase 8 first adds only the `L=128` even-sector endpoint states at
`Gamma=1.55,1.60`. The crossing stage uses `K=24` and `chi=64`; the latter is
restricted to `R_xi` because Phase 7 measured `chi=64 -> 128` changes below
`4e-6`, smaller than the relevant crossing-resolution uncertainty. All final
common-field even/odd states use `chi=128`.

A strict sign change in
`D_64,128(Gamma)=R_xi(64,Gamma)-R_xi(128,Gamma)` is required before linear
interpolation. An unbracketed result remains unresolved without extending
the Gamma window. The two available crossings are then evaluated in `1/L`
and `1/log(L)` sensitivity coordinates. These coordinates do not assume a
known leading correction exponent; with two points they are exact two-point
sensitivity extrapolations with no residual degrees of freedom.

All three gaps are evaluated at the common power-coordinate sensitivity
field. The alternative logarithmic-coordinate `Gamma_c` and its spread from
the power value are reported separately, but this critical-field sensitivity
is not fully propagated into the gap uncertainty because only two crossings
exist. The gap sequence yields `z_eff(32,64)` and `z_eff(64,128)`, followed
by power/log two-point sensitivity extrapolations.

The final report compares these values with Shiratani--Todo's published
`sigma=7/4` results, `z_power=0.91(2)` and `z_log=0.98(3)`, from Table 2 of
arXiv:2305.14121v4. Their maximum size is `L=362`, so the present `L<=128`
analysis is not presented as a precision reproduction.

No later-sigma plan is created until the complete `sigma=1.75` result is
reviewed. The imaginary-time-integrated susceptibility and `gamma/nu` remain
outside the DMRG scope. Equal-time `C_eq(r)` and `S_eq(0)` are auxiliary
diagnostics only.
