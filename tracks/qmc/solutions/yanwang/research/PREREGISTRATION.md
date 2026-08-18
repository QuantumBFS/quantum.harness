# Preregistered Analysis and Acceptance Gate

Status: **draft-for-review**

Version: `yanwang148-prereg-v1`

Production state: **locked**

This document must be frozen by commit and SHA-256 before high-statistics
production manifests are generated. A later amendment requires a new version,
an explanation written before opening affected production results, and a
separate analysis label. Amendments may not replace an inconvenient result.

## Estimands

\[
\theta_\triangle=h_c^\triangle/J,\qquad
\theta_\hexagon=h_c^\hexagon/J,\qquad
R=\theta_\triangle/\theta_\hexagon,\qquad
\Delta=R-\sqrt5 .
\]

No prior, fit penalty, initialization, plotting reference line, or stopping
rule may favor \(\sqrt5\). It is absent from field estimation and enters only
after the frozen \(R\) record exists.

## Production prerequisites

Production remains blocked until all are true:

1. the B0–B3 baseline reproduction gate passes for both lattices;
2. two QMC routes with independent code paths pass the ED fixtures;
3. the synthetic FSS benchmark has correct 68% and 95% interval coverage
   within predeclared Monte Carlo tolerance;
4. exact production size, field, beta, seed, sweep, wall-time, and resource
   manifests are committed;
5. this document, all accepted analysis variants, exclusion rules, and the
   one-command analysis entry point are frozen;
6. the validator's negative controls pass;
7. production output paths are separate from pilot paths.

## Primary observable and fit

The baseline-reproduction and production-primary estimator is the Binder
ratio of the space--imaginary-time averaged magnetization:

\[
Q_L^{\mathrm{st}}
=\frac{\langle \bar m^2\rangle^2}{\langle \bar m^4\rangle},
\qquad
\bar m=\frac{1}{\beta N}\int_0^\beta d\tau
       \sum_i\sigma_i^z(\tau).
\]

Its fit-record estimator ID is `spacetime_binder_q`. Attempt 009 passed its
ED/QMC and literal beta*h=L validation gates, so this estimator is authorized
for the low-statistics published-baseline grid. It remains blocked from final
production until all baseline, finite-size, and independent-route gates pass.
Attempt 008 stopped at a fail-closed old-Git scheduler provenance check
before any scientific command ran.

The equal-time Binder ratio, estimator ID `equal_time_binder_q`, is measured
on the same Markov chains as a diagnostic. It is not interchangeable with the
primary estimator and is not an independent computational route. If
\(\xi_L/L\), estimator ID `second_moment_xi_over_L`, passes its independent
estimator validation before the freeze, it is a confirmatory observable, not
a replacement chosen after seeing the ratio.

Every fit command and fit record must select an estimator ID explicitly.
There is no generic or default `binder` alias.

The primary joint finite-size fit for each lattice is

\[
Q_L(h)=Q^\star+a_1x+a_2x^2+b_1L^{-\omega}
       +c_1xL^{-\omega},\quad
x=(h-h_c)L^{1/\nu},
\]

with external fixed \(\nu=0.629971\) and \(\omega=0.82968\). Their quoted
literature uncertainties are propagated in a sensitivity bootstrap.
Generalized least squares uses the resampling covariance of all fields
derived from a common chain or reweighting source.

The exact production \(L\) roster and field windows will be frozen after
pilot timing and crossing studies. They may not be changed because of the
observed direction of \(\Delta\).

## Predeclared analysis variants

All variants are run automatically and reported:

1. increase \(L_{\min}\) by one and by two roster steps;
2. decrease \(L_{\max}\) by one roster step;
3. omit `c1*x*L^-omega`;
4. add the frozen second correction term when degrees of freedom remain at
   least four; literal-2002 reproduction uses the paper's \(L^{d-2y_h}\)
   term, while a separately labelled modern sensitivity fit may use
   `b2*L^(-2*omega)`;
5. use historical \(\omega=0.815\);
6. vary \(\nu,\omega\) jointly within their external uncertainties;
7. use each frozen inner/outer field window;
8. use each frozen beta multiplier;
9. leave out each size once;
10. leave out each seed group once;
11. double the initial thermalization discard;
12. repeat with block sizes \(10\tau_{\rm int}\) and
    \(20\tau_{\rm int}\);
13. fit pairwise crossing drifts as an independent analysis of the same
    observable.

A variant is accepted only if it converges, has at least four degrees of
freedom, finite well-conditioned covariance under the frozen threshold,
goodness-of-fit \(p\ge0.05\), and passed synthetic coverage for that model
class. These rules are value-independent. Rejected variants remain in the
robustness table.

## Chain and run quality gates

A production chain is eligible only if:

- the scheduler reports normal completion and all artifact hashes match;
- no nonfinite sample or negative sign is observed;
- warmup is at least \(50\max\tau_{\rm int}\), estimated conservatively from
  pilot and production diagnostics;
- post-warmup bin length is at least \(10\max\tau_{\rm int}\);
- each cell aggregates at least 2,000 effective samples for both \(m^2\) and
  \(m^4\), with at least four independent seeds and at least 200 effective
  samples per seed;
- first/second-half drift is compatible at two-sided \(p\ge0.01\);
- doubling the warmup discard does not shift \(Q\) by more than two combined
  standard errors;
- the beta-convergence check at the frozen larger beta shifts \(Q\) by less
  than one quarter of its target statistical error, or the larger beta is
  adopted for all production cells before unblinding.

Runs may be excluded only for these predeclared technical failures, corrupted
artifacts, duplicate seeds, or a documented scheduler/hardware failure.
Distance from \(\sqrt5\) is never an exclusion reason.

## Seeds and stopping

Seeds are deterministic:

`uint64(SHA256("yanwang148-v1|campaign|lattice|L|h|replica")[0:16])`.

The full seed roster is generated and committed before submission. Production
uses fixed sweeps and resources; there is no precision or central-value
optional stopping. If a whole frozen campaign misses the precision target, it
is reported and a separately preregistered extension may be run without
discarding the first campaign.

## Statistical and systematic uncertainty

For each primary quantity:

- `sigma_stat` is the standard deviation of a joint blocked bootstrap that
  resamples independent chains and autocorrelation-safe bins and refits every
  bootstrap draw.
- `sigma_sys` is the largest absolute shift from the frozen primary estimate
  among all accepted predeclared analysis variants.
- `sigma_total = sqrt(sigma_stat^2 + sigma_sys^2)`.

The ratio is recomputed inside every joint bootstrap draw. The triangular and
honeycomb production chains are statistically independent; any shared
external exponent draw is shared between them. `sigma_R_sys` is the maximum
shift over accepted **joint** variants, preserving cancellation or
reinforcement rather than propagating the two field envelopes independently.

Reports must display all three components. The symbol \(\sigma_R\) in the
verdict gate means `sigma_R_total`.

## Precision gate

All must pass:

- \(\sigma_{\triangle,\mathrm{total}}\le1.8\times10^{-5}\);
- \(\sigma_{\hexagon,\mathrm{total}}\le8.0\times10^{-6}\);
- \(\sigma_{R,\mathrm{total}}\le1.2\times10^{-5}\);
- independent-route critical fields agree within two combined total standard
  deviations for each lattice;
- every accepted joint analysis variant is reported and satisfies the
  verdict-specific robustness clause below.

The field limits are exactly five times smaller than the respective 2002
quoted uncertainties.

## Frozen verdict

After the precision and independence gates:

- **Evidence against the conjecture** if
  \(|\Delta|\ge10\sigma_R\), every accepted joint variant has
  \(|\Delta_v|\ge8\sigma_{R,v}\), and both independent computational routes
  give the same sign of \(\Delta\).
- **Conjecture survives this numerical test** if
  \(|\Delta|\le2\sigma_R\) and
  \(\sigma_R\le1.2\times10^{-5}\), and every accepted joint variant satisfies
  \(|\Delta_v|\le2\sigma_{R,v}\).
- **Inconclusive** in every other case, including a failed precision,
  baseline, independence, robustness, or quality gate.

“Survives” is not a proof of exact equality. “Evidence against” is a numerical
finding under the stated model and finite-size analysis.

## Blinding and opening procedure

Pilot, synthetic, ED, timing, and diagnostic data are visible. Final
production analysis runs in two stages:

1. `analyze --blind` writes per-lattice diagnostic residuals, fit health, QC,
   and uncertainty budgets but withholds \(h_c\), \(R\), \(\Delta\), and any
   plot centered on \(\sqrt5\).
2. Once all gates except the unknown central values pass, the freeze commit
   and artifact hashes are recorded. `analyze --open <freeze-commit>` performs
   the single authorized opening and emits the immutable verdict record.

The opening command aborts on a dirty worktree, a hash mismatch, an unlisted
run, or an unfrozen preregistration.
