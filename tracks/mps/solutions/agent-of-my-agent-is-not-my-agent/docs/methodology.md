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

## Planned validation layers

1. Exact periodic Hurwitz-zeta coupling.
2. Exponential fitting and periodization.
3. MPO coefficient reconstruction.
4. Small-system observable comparison.
5. Independent `K` and `χ` convergence in DMRG scaling.

No TeNPy API, MPO, DMRG, or many-body observable is included at this stage.
