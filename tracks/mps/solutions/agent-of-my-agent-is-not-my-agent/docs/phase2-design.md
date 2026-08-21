# Phase 2: Exponential Decomposition Validation

## Scope

Approximate only the infinite-chain kernel `f(r) = r^(-p)`, with
`p = 1 + sigma`, by `sum_k c_k lambda_k^r`. The periodic Hurwitz-zeta
coupling is not used by the fit. It is used only after fitting to validate
the analytical periodization. TeNPy APIs, MPO construction, and DMRG are
out of scope.

## Fitting design

For a requested `K`, initialize `K` positive decay rates deterministically
on a logarithmic scale spanning the fit window. Parameterize the nonlinear
variables so every fitted `lambda_k` remains strictly between zero and one
and ordered. At every nonlinear objective evaluation, solve the coefficients
`c_k` by linear least squares against the relative residual:

`(sum_k c_k lambda_k^r - r^(-p)) / r^(-p)`.

The linear least-squares solve constrains `c_k >= 0`. The target power law is
completely monotone, so this prevents finite-window cancellations from
creating an unphysical long-distance tail when the exponentials are
periodized.

Use SciPy's deterministic bounded least-squares optimizer without random
restarts. Report maximum absolute relative error and RMS relative error over
`r = 1, ..., r_fit`.

## Periodic validation

For `r = 1, ..., L - 1`, reconstruct

`J_tilde_L(r) = sum_k c_k (lambda_k^r + lambda_k^(L-r)) / (1-lambda_k^L)`

and compare it with the exact Phase 1 Hurwitz-zeta coupling. Report maximum
and RMS relative error and preserve every distance-resolved exact value,
approximation, absolute error, and relative error.

## Outputs

The validation command defaults to `L=64`, `sigma=1.75`, `r_fit=8L`, and
`K=8,12,16,20,24`. It writes one CSV profile and one JSON summary per K, plus
an aggregate JSON file. Tests cover deterministic fitting, strict lambda
bounds, periodic symmetry, the analytical formula, output schemas, and
decreasing in-window kernel error as K increases. Periodized errors are
reported independently: finite-window kernel convergence does not
mathematically imply monotone convergence of the infinite geometric image
tail.

## Periodized residual summary

For each K, retain the complete distance-resolved periodic CSV and add three
JSON diagnostics:

- `global_maximum`: maximum relative error, its integer distance `r`, and the
  exact and reconstructed coupling at that distance;
- `short_distance`: maximum and RMS relative errors over `r = 1, ..., 10`;
- `central_region`: maximum and RMS relative errors over the five distances
  `r = L/2-2, ..., L/2+2`.

The default case has even `L=64`. The validation command requires an even
length of at least 20 so both regions have their declared sizes. If periodic
symmetry produces equal global maxima at `r` and `L-r`, the smaller distance
is reported.

## Correlation-length-bound redesign

The first tail-stable redesign preserves the relative-residual fit to the
infinite kernel and the nonnegative coefficient solve. It adds

`a_k = -log(lambda_k) >= alpha/r_fit`,

so no exponential correlation length exceeds `r_fit/alpha`. The study scans
`alpha=0.25,0.5,1.0`, `K=16,24`, and `r_fit=512,1024,2048`, and compares all
18 constrained cells with the six unconstrained NNLS baseline cells.

Each cell records all `lambda_k`, all rates `a_k`, `a_min*r_fit`,
coefficients, kernel maximum/RMS error, and the complete existing periodized
residual summary. The fitting objective contains no periodic Hurwitz data.
