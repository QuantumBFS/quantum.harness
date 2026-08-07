# Learning-Induced MIT Effective Central Charge Design

## Objective

Extend the learning-induced metal–insulator transition study with two
independent estimates of the effective central charge:

1. an exploratory entanglement-entropy estimate based on chord-length scaling;
2. a Casimir-amplitude estimate cross-validated by an independently fitted
   space–time anisotropy.

The work must preserve the existing frozen result, generate a separate
`learning-mit-production-v2-*` result, update the standalone English and
Chinese reports, and update the English and Chinese integrated reports.
Exploratory numerical estimates remain visible even when strict scientific
claim gates fail, but their failed gates must be stated explicitly.

## Scientific Interpretation

The reports distinguish three quantities:

- the existing per-size diagnostic coefficient `c`, which must not be renamed
  or silently treated as a universal central charge;
- the entanglement estimate \(c_{\mathrm{eff}}^{S}\), extracted from
  chord-length scaling and extrapolated in system size;
- the Casimir estimate \(c_{\mathrm{eff}}^{C}\), obtained by dividing the
  fitted product \(c_{\mathrm{eff}}\alpha\) by an independently estimated
  anisotropy \(\alpha\).

Agreement between the last two estimators is a cross-check, not a fitting
constraint. Parameters must not be tuned to force agreement.

## Entanglement-Entropy Estimator

For every DIII angle and system width, define

\[
x(\ell,L)=\log\!\left[\frac{L}{\pi}
\sin\left(\frac{\pi\ell}{L}\right)\right].
\]

In source code and rendered reports the implicit multiplication must appear
unambiguously as
`log((L / pi) * sin(pi * ell / L))`.

Fit the central interval \(\ell/L\in[1/4,3/4]\) to

\[
S(\ell,L)=b+\frac{c_{\mathrm{eff}}^{S}(L)}{3}x(\ell,L)
+\frac{q}{L^2}\cos\left(\frac{2\pi\ell}{L}\right).
\]

For each angle, extrapolate the per-size estimates with

\[
c_{\mathrm{eff}}^{S}(L)=c_{\mathrm{eff}}^{S}(\infty)+a/L^2.
\]

Compare constant, logarithmic, squared-logarithmic, mixed, and Page-corrected
models using the project’s existing model-weight machinery. A numerical
entanglement estimate may be shown as exploratory even when the logarithmic
model is not dominant, but the model weights and that limitation must be
reported.

## Casimir and Anisotropy Estimator

At the selected DIII candidate angle, fit

\[
\gamma_1(L)=f_\infty L
-\frac{\pi(c_{\mathrm{eff}}\alpha)}{6L}
+\frac{a}{L^3}.
\]

The direct fit result is \(c_{\mathrm{eff}}\alpha\). Estimate the scaling
dimension \(\Delta\) from spatial parity correlations and the temporal gap
\(g\) from the leading Lyapunov exponents, then compute

\[
\alpha=\frac{gL}{2\pi\Delta},
\qquad
c_{\mathrm{eff}}^{C}
=\frac{c_{\mathrm{eff}}\alpha}{\alpha}.
\]

Anisotropy must be positive and stable across declared size windows before
the Casimir result can receive `candidate` status. The fit must expose the
raw widths, observations, fitted values, residuals, covariance diagnostics,
and correction model.

## Candidate Selection

The strict candidate is selected only when adjacent sampled DIII angles carry
opposite metal and insulator classifications under the existing phase
classifier. The strict candidate angle is the sampled point nearest the
midpoint of that bracket; an equal-distance tie selects the smaller angle.

If no strict bracket exists, select an exploratory pseudo-critical interval
as the adjacent angle pair with the largest absolute finite-difference change
in the predeclared phase-evidence score. Ties are resolved by choosing the
pair with the smaller midpoint. The exploratory angle is the sampled point
nearest that midpoint. This deterministic fallback may produce numerical
fits but can never satisfy the strict bracket gate.

## Monte Carlo Production v2

All physical sampling remains in Rust. The only random-number generator for
physical and diagnostic streams is `Xoshiro256PlusPlus`, with deterministic
seed derivation that separates stage, angle, width, stream, and observable.
Python validates frozen data, performs fitting and bootstrap analysis, makes
plots, and renders reports; it does not evolve Monte Carlo trajectories.

The existing frozen run is retained byte-for-byte. The new run is written to
a distinct `learning-mit-production-v2-*` directory with its own manifest,
hashes, status, and stable-output pointer.

### Stage 0: Existing-Data Exploration

Run the entanglement estimator on the existing frozen data to establish an
exploratory baseline and prioritize the new scan. No new Monte Carlo streams
are generated in this stage.

### Stage 1: DIII Locator Scan

- \(\theta/\pi=0.45\)
- \(\phi/\pi=0.16,0.18,0.20,0.22,0.24,0.26,0.28,0.30,0.32\)
- \(L=8,12,16,20,24,28,32\)
- four independent streams per parameter point
- 16 burn-in periods per width
- 64 measurement periods per width
- eight measurement periods per block

A benchmark forecasts the complete scan before production begins. Task
ordering is deterministic: large widths in the exploratory candidate region
precede equally sized tasks farther from the candidate region.

### Stage 2: Adaptive Refinement

If Stage 1 produces a strict bracket, refine the two bracket endpoints and
their midpoint. Otherwise refine the deterministic exploratory interval
defined above.

- retain all seven widths;
- increase coverage to eight independent streams per point;
- increase measurement length to 96 periods per width;
- reuse only completed streams whose schema, exact task configuration, seed,
  and SHA-256 digest all match.

## Runtime Policy

- target runtime: 3600 seconds;
- ordinary-task stop: 3300 seconds;
- hard stop for new scientific work: 5100 seconds;
- finalization reserve: 300 seconds;
- the additional scientific reserve may be used only to complete candidate
  large-width streams or independent streams declared before the run;
- a partial stream never enters an estimator;
- complete, hash-valid streams remain usable after a time stop.

## Uncertainty and Diagnostics

Both estimator chains use a hierarchical bootstrap that first resamples
independent streams and then resamples blocks within each selected stream.
Every numerical result includes:

- a point estimate and 95% bootstrap interval;
- angle, size window, independent-stream count, and effective block count;
- chi-square per degree of freedom;
- residuals and covariance condition number;
- sensitivity to removing the smallest size;
- relevant competing-model weights;
- bootstrap failure fraction.

The reports compare \(c_{\mathrm{eff}}^{S}\) and
\(c_{\mathrm{eff}}^{C}\) using their combined uncertainty. The comparison
passes when
\[
\left|c_{\mathrm{eff}}^{S}-c_{\mathrm{eff}}^{C}\right|
\leq 1.96\sqrt{\sigma_S^2+\sigma_C^2},
\]
where each \(\sigma\) is the standard deviation of its hierarchical bootstrap
distribution. The comparison must be reported even when it fails.

A fit is stable only when its covariance condition number is at most
\(10^{10}\), its bootstrap failure fraction is at most 5%, and removing the
smallest size changes the estimate by no more than the combined 95%
uncertainty of the two size windows. An anisotropy estimate is stable only
when every declared window is positive and the range of window estimates
divided by their median is at most 25%.

## Claim States

Each result has exactly one of these states:

- `candidate`: the DIII transition is strictly bracketed; at least five
  widths contribute; every selected size has at least four independent
  streams and the selected data contain at least 32 complete blocks; the
  Casimir and anisotropy fits satisfy the stability definitions above;
  \(\alpha>0\); and the two effective-central-charge estimates pass the
  combined-uncertainty comparison above;
- `exploratory`: a numerical estimate and interval exist, but at least one
  strict gate fails; all failed gates are listed;
- `unavailable`: fewer than four valid widths contribute, the design matrix
  is unidentifiable, or the bootstrap failure rate prevents an interval.

An exploratory value is displayed, never substituted for a universal
constant, and never described as confirmation of a DIII universality class.

## Report Changes

Update the standalone English and Chinese HTML/PDF reports and both integrated
reports with:

- an effective-central-charge summary table;
- chord-length fits;
- \(c_{\mathrm{eff}}^{S}(L)\) finite-size extrapolation;
- Casimir fit and residuals;
- anisotropy window stability;
- a comparison of the two central-charge estimators;
- a machine-readable and human-readable gate table;
- a prominent explanation that exploratory values are not final universal
  constants.

English and Chinese reports must communicate the same numbers, intervals,
status, caveats, and provenance. Existing three-model benchmark cards remain
unchanged.

## Validation

Development follows test-driven development. Tests cover:

- chord-length construction and coefficient normalization;
- finite-size extrapolation;
- deterministic strict and exploratory candidate selection;
- hierarchical bootstrap stream/block resampling;
- Casimir and anisotropy calculations;
- singular and ill-conditioned fits;
- claim-state transitions and complete failed-gate lists;
- report content in both languages;
- HTML structure and embedded artifacts;
- PDF rendering and visual inspection;
- result manifests, SHA-256 verification, and stable-output consistency;
- Rust replay determinism and exclusive use of `Xoshiro256PlusPlus`.

Before completion, rerun all Rust tests, learning-MIT Python tests, integrated
report tests, frozen-manifest audits, HTML audits, and PDF render checks.
