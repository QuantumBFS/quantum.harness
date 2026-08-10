# Weak Self-Dual Central-Charge Verification Design

**Date:** 2026-07-29

**Team:** 卧龙凤雏

**Challenge:** [QuantumBFS/quantum.harness#122](https://github.com/QuantumBFS/quantum.harness/issues/122)

**Primary reference:** [Wang et al., arXiv:2502.14034v4](https://arxiv.org/abs/2502.14034)

## Goal

Reproduce the effective Casimir central charge of the weak Kramers-Wannier
self-dual critical point,

\[
c_{\mathrm{eff}} = 0.447(1),
\]

using the Born-correlated measurement ensemble of the decohered toric-code /
monitored-Majorana construction. Monte Carlo sampling and Gaussian-fermion
evolution will run in Rust with Xoshiro256++; Python will only analyze data and
produce plots and the report.

This benchmark is intentionally limited to the central charge. Reproducing the
full Lyapunov spectrum and the vortex scaling dimensions is deferred.

## Physical Model

The simulation is performed at the exactly self-dual measurement angle
\(\theta=\pi/4\). The spacetime-isotropic couplings are

\[
\beta=\beta'=\ln(1+\sqrt 2),
\]

so the anisotropy factor in the conformal finite-size correction is
\(\alpha=1\).

The system is a long cylinder with even periodic circumference \(L\) and
length \(L_y\gg L\). A chain of \(2L\) Majorana modes undergoes alternating
weak measurements of the neighboring-Majorana parities corresponding, in the
spin representation, to \(X_j\) and \(Z_jZ_{j+1}\). For a measurement of
\(i\gamma_a\gamma_b\), the outcome \(s=\pm1\) is sampled conditionally:

\[
P(s\mid\Gamma)=
\frac{1+s\tanh(\beta)\langle i\gamma_a\gamma_b\rangle_\Gamma}{2}.
\]

The covariance matrix is updated after every sampled outcome. This sequential
state-conditioned sampling is essential: replacing it with independent random
bonds would change the replica limit and simulate a different universality
class.

Trajectories are classified by their Wilson loop \(W\). The central-charge
estimator uses the \(W=+1\) vacuum sector, as in the reference calculation.
Electric- and magnetic-vortex densities are recorded as a self-duality
diagnostic; they are not separate benchmark targets.

## Selected Numerical Approach

The selected approach is Gaussian Majorana evolution with direct sequential
Born sampling. It is preferred over hybrid tensor-network Monte Carlo because
it represents Gaussian trajectories exactly, avoids tensor-network truncation,
and directly supplies the stabilized Lyapunov estimator requested by the
challenge.

For each circumference:

1. Initialize a pure Gaussian state and its \(2L\times2L\) covariance matrix.
2. Apply alternating layers of onsite and bond weak measurements.
3. Compute each conditional probability from the current covariance matrix.
4. Draw the outcome with `rand_xoshiro::Xoshiro256PlusPlus`.
5. Apply the analytic Gaussian covariance update.
6. Periodically QR-orthogonalize the evolved Majorana modes and accumulate the
   logarithmic norm changes.
7. Form the vacuum many-body Lyapunov exponent, retaining all normalization
   constants and recording the Wilson-loop sector.
8. Emit raw trajectory and block estimates for analysis.

The finite-width estimator is fitted to

\[
\gamma_1(L)=
f_\infty L-\frac{\pi c_{\mathrm{eff}}}{6L}+\frac{a}{L^3}.
\]

The bulk coefficient \(f_\infty\), central charge, and leading correction are
fitted jointly. Additional correction models are used only for stability
analysis.

## Software Boundary

The solution will live under
`tracks/qmc/solutions/卧龙凤雏/weak-self-dual/` and follow the layout of the
existing clean-Ising and Nishimori benchmarks.

### Rust responsibilities

- Xoshiro256++ random-number generation and reproducible stream seeding
- Conditional Born sampling
- Gaussian covariance and Majorana-mode evolution
- QR stabilization and Lyapunov accumulation
- Wilson-loop and vortex diagnostics
- Burn-in, blocking, and raw CSV/JSON output
- Small-system exact-enumeration oracle

### Python responsibilities

- Input validation and aggregation
- Autocorrelation and effective-sample-size diagnostics
- Block-bootstrap uncertainty propagation
- Finite-size fits and model-stability analysis
- Tables, plots, summary JSON, and offline HTML report

Python must not generate disorder, perform Monte Carlo updates, or replace any
part of the physical simulation.

## Validation Strategy

Validation is completed before production:

1. **Probability normalization:** both outcomes are finite, non-negative, and
   sum to one at every update.
2. **Exact enumeration:** short, small-width trajectory probabilities,
   covariance observables, Shannon quantities, and sector weights match an
   explicit enumerator.
3. **Gaussian invariants:** the covariance matrix remains antisymmetric and
   pure within numerical tolerance.
4. **Gauge invariance:** gauge-equivalent outcome configurations produce equal
   physical observables.
5. **Clean limit:** an all-positive trajectory matches clean-Ising transfer
   evolution.
6. **Self-duality:** at \(\theta=\pi/4\), electric- and magnetic-vortex
   densities agree within uncertainty.
7. **Reproducibility:** identical configurations and seeds produce
   byte-identical raw output.

Tests will cover the covariance update, conditional probabilities, boundary
bond, Wilson-loop classification, QR accumulation, exact enumeration, parsing,
bootstrap fitting, and report-data consistency.

## Production Protocol

The initial production grid uses even widths

\[
L=6,8,\ldots,30,
\]

with \(L=32\) reserved as a large-width stability check. Each width begins at
\(L_y=100L\), with an explicit burn-in discarded before measurement. Multiple
independent RNG streams are used per width. Runs are extended when
autocorrelation, effective sample size, or fit stability is inadequate.

Each run records:

- complete configuration and code version
- master seed and derived stream identifiers
- circumference, cylinder length, and discarded burn-in
- blockwise Lyapunov/free-energy estimates
- Wilson-loop counts and retained-sector sample counts
- electric- and magnetic-vortex densities
- timing, numerical-stability counters, and convergence diagnostics

No production result is silently discarded. Invalid values or failed
invariants stop the affected run with a diagnostic containing its seed and
location.

## Statistical Analysis

Uncertainty is estimated by resampling independent streams and autocorrelation-
aware blocks. The primary fit uses all accepted widths and the \(L^{-3}\)
correction. Robustness checks include:

- increasing \(L_{\min}\)
- excluding the largest width or adding \(L=32\)
- omitting the correction term
- adding the next odd inverse-power correction
- changing burn-in and block length

The analysis reports parameter covariance, bootstrap confidence intervals,
residuals, goodness of fit, effective sample sizes, and the complete family of
fit-window estimates. The final interval is statistical; systematic spread
from accepted fit variants is reported separately and must not be hidden by
the bootstrap error bar.

## Acceptance Gates

The benchmark passes only when:

- all exact and invariant-based validation tests pass;
- electric- and magnetic-vortex densities agree within their joint
  uncertainty;
- every included width satisfies the configured effective-sample-size gate;
- residuals show no unresolved monotonic width dependence;
- the estimate remains statistically stable under the documented fit
  variations;
- the final 95% interval contains \(0.447\);
- the target 95% half-width is at most \(0.01\).

A failed gate remains visible in the report and triggers either additional
sampling or an explicit failed benchmark result.

## Deliverables

The solution will provide:

- Rust source, tests, and locked dependencies
- Python analysis and tests
- reproducible `Makefile` and `run.sh` entry points
- documented quick-validation and production configurations
- raw CSV/JSON data and processed summary files
- plots for finite-size scaling, residuals, fit-window stability,
  autocorrelation/ESS, and self-duality
- a self-contained offline HTML report with methods, data, uncertainty,
  diagnostics, and an explicit pass/fail conclusion

## Deferred Work

The following are outside this benchmark:

- full single- and many-particle Lyapunov spectra
- vortex and excitation scaling dimensions
- boundary entanglement coefficients
- scans away from \(\theta=\pi/4\)
- comparison with anisotropic or continuous weak-measurement realizations
