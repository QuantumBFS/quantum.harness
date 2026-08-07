# Issue #158 extended public-data analysis protocol

Frozen: 2026-07-29, before running the extended scripts described here.

This is a **retrospectively locked** protocol, not a prospective
preregistration: the public data and earlier exploratory fits had already been
inspected.  Its purpose is to prevent further result-dependent changes while
performing the extended audit.

## Data selection

- Source: Zenodo record `10.5281/zenodo.17206870`, file `data.dat`.
- Model slice: `sigma == 2` and `beta = 1, 2, 4, 8`.
- For each `(beta, L)`, use the row with the largest `N_sample` as the primary
  estimate.  The nine additional equal-length `L=512` runs are reserved for
  the run-to-run covariance audit and are not inverse-variance combined with
  the primary row.
- Primary scalar observable: `M2` with published `M2_err`.
- Joint sensitivity observables: `M2` and `M2_k_min` with their published
  marginal errors.
- Published errors are treated as Gaussian standard errors for the numerical
  sensitivity calculations.  Cross-size independence is an unverified working
  assumption.

## Locked scalar models

Set `ell = log(L)` (lattice spacing and `L0` fixed to one).

Ordered:

1. `O1: M2 = g0 + a1/ell`
2. `O2: M2 = g0 + a1/ell + a2/ell^2`

Logarithmically decaying:

1. `D1: M2 = A ell^(-p)`, `p > 0`
2. `D2: M2 = A ell^(-p) + B ell^(-p-1)`, `p > 0`

The nonlinear exponent is optimized continuously in
`1e-5 <= p <= 2`.  Linear coefficients are obtained by weighted least
squares for each profiled exponent.  Ordered fits are not constrained to
`g0 >= 0`, so a nominal confidence interval for `g0` can be inspected without
boundary bias.

## Fit windows and diagnostics

- Scan `Lmin = 16, 32, 48, 64, 96, 128, 192, 256, 384, 512`, retaining a
  window only when it has at least six data points.
- Report `chi2`, degrees of freedom, reduced `chi2`, AICc, and BIC.
- Treat AICc/BIC comparisons as descriptive if either competing model has a
  goodness-of-fit p-value below `0.05`.
- Refit after dropping the largest one and largest two sizes.  Record signed
  held-out residuals in units of the published marginal error.
- Report both the nominal `g0` standard error and an over-dispersion-scaled
  error multiplied by `sqrt(max(1, chi2/dof))`.

## Synthetic identifiability experiment

- Registered window: `L >= 64`.
- Truth models: best-fitting `O2` and best-fitting `D2` for each beta on the
  registered window.
- Generate 2,000 independent Gaussian replicas per truth and beta using the
  published marginal errors and deterministic seed `1582026`.
- Fit both `O2` and `D2` to every replica.
- For `D2` truth, report:
  - fraction of ordered fits with `g0 > 0`;
  - fraction with nominal lower 95% bound above zero;
  - fraction with over-dispersion-scaled lower 95% bound above zero;
  - fraction for which the ordered model passes a chi-square GOF test at 5%;
  - fraction for which AICc prefers or decisively prefers (`Delta AICc < -6`)
    the ordered model.
- For `O2` truth, report the corresponding rates at which AICc prefers or
  decisively prefers (`Delta AICc > 6`) the decaying model.

## Joint covariance sensitivity

For each size, posit a within-size correlation
`rho = Corr(M2, M2_k_min)`.  Cross-size covariances remain zero.

- Scan constant `rho` over `-0.8, -0.6, -0.4, -0.2, 0, 0.2, 0.4, 0.6, 0.8`.
- Use the registered window `L >= 64`.
- Compare equal-parameter-count joint models:
  - ordered:
    `M2 = g0+a1/ell+a2/ell^2`,
    `M2k = b1/ell+b2/ell^2`;
  - decaying:
    `M2 = A ell^-p+B ell^(-p-1)`,
    `M2k = C ell^(-p-1)+D ell^(-p-2)`.
- Report `Delta AICc = AICc_ordered - AICc_decaying`; positive values favor
  the decaying model within the assumed covariance scenario.
- The scan is a sensitivity analysis, not a substitute for the unpublished
  synchronized bins or jackknife replicas.

## Kernel audit

- At `sigma=2`, evaluate the infinite-lattice/periodic-image axial kernel with
  an exact one-dimensional reduction and high-precision polylogarithms.
- Compare it with the normalized minimum-image kernel at
  `kmin = 2*pi/L`.
- Verify the coefficient
  `pi*c_infinity/2`, convergence of local slopes, `cL-cinfinity = O(L^-2)`,
  and the relative MI/PI difference of order `1/log(L)`.
- Use `sigma=1.875` and `2.125` minimum-image calculations as control points
  for the effective momentum exponent.

## Interpretation rule

The public-data result will be called **numerically unresolved** if reasonable
fit windows/corrections change the preferred scalar model, if all simple
models fail GOF, or if joint preferences materially depend on the assumed
unknown covariance.  The rigorous no-SSB conclusion, if established, is
reported separately from the finite-size identifiability assessment.

## Post-lock source-matched addendum

Added after the first locked run, because a line-by-line check of the paper
source showed that the published ordered ansatz was used in its unexpanded
shifted-log form, with strongly sub-unit fitted `L0` values:

- `OP: M2 = g0 + a/log(L/L0)`;
- equal-parameter-count competitor
  `DP: M2 = A[log(L/L0)]^(-p)`.

These three-parameter models are analyzed separately and labeled
**post-lock/source-matched**.  They do not replace or silently modify the
locked primary comparison.  The profile range is
`-20 <= log(L0) <= log(Lmin)-0.1`, with `1e-5 <= p <= 2`.

The paper's residual construction is also audited using the stated
`b = 149, 175, 152, 154` and fixed `omega=0.4`.  Since its uncertainty depends
on the unavailable `Cov(M2,M2_k_min)`, the residual comparison is repeated for
constant within-size correlations from `-0.8` to `0.8`; the uncertainty in the
data-selected coefficient `b` itself cannot be reconstructed and is not
included.
