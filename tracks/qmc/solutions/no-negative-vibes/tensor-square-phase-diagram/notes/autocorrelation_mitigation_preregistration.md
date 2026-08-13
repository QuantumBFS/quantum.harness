# Stage 4 autocorrelation-mitigation pre-registration

Date: 2026-07-29

## Motivation and frozen hypothesis

The completed Stage 4 production run has 81 autocorrelation-cap early stops.
The worst monitored mode is `hs_q_a` or `hs_q_b` in 48 of those replicas,
whereas `q_combined` is worst in only one.  The current sampler updates all
channels on one imaginary-time slice at a time.  The frozen hypothesis is that
long-wavelength imaginary-time modes of an individual auxiliary-field channel
are therefore mixed inefficiently.

The sole proposed change is an optional pCN proposal for one complete channel
history at a time,

`phi'_c = sqrt(1-s^2) phi_c + s eta`, with frozen `s = 0.1`.

It is reversible with respect to the Gaussian auxiliary-field prior, so the
Metropolis ratio remains the fermion determinant ratio.  The original local
proposal remains active.  The new proposal is disabled by default and has
separate acceptance counters.

## Ordered validation

1. **m=3 ED validation.**  At
   `(beta,dt,t,g_B/g_A,mu,V)=(2,0.1,0.5,1,0,0.15)`, run four paired-seed
   replicas per sampler, with 240 warmup sweeps, 800 measurement sweeps and
   `measure_every=2`.
2. **One Stage 4 A/B point only.**  If and only if step 1 passes, test the
   previously censored half-filled point
   `(m,beta,dt,t,g_B/g_A,mu)=(8,8,0.2,0.5,0.25,0)` with two paired-seed
   replicas per sampler, 240 warmup sweeps, 640 measurement sweeps and
   `measure_every=2`.
3. Do not change `s`, budgets, monitored observables, or thresholds in response
   to the measured order signal.  Do not rerun the completed 675-point Stage 3
   grid or the completed Stage 4 production grid.

All runs use independent processes and one BLAS thread.

## Frozen gates

The m=3 gate passes only if:

- both samplers have total acceptance in `[0.05,0.995]`;
- the block proposal acceptance is in `[0.05,0.995]`;
- direct sign, determinant identity and density stability audits remain healthy;
- every pre-registered monitored autocorrelation estimate is finite and at
  least `0.5`;
- energy, density and `q_combined` agree with ED within 3 aggregate standard
  errors for both samplers;
- energy, density, `q_a_sq`, `q_b_sq` and `q_combined` agree between samplers
  within 3 combined standard errors.

Failure stops the block updater.  It is not used for a physics conclusion.

At the Stage 4 A/B point, numerical stability and acceptance use the same
windows.  The five observables above must agree within 2 combined standard
errors.  The efficiency decision uses the median across replicas of the worst
pre-registered Stage 4 integrated-autocorrelation time:

- `ADVANCE`: all audits pass and the median worst tau falls by at least 25%;
- `INCONCLUSIVE`: all audits pass and tau falls, but by less than 25%; permit
  one longer confirmation at this same point and scale only;
- `STOP`: any audit or observable-consistency gate fails, or median worst tau
  does not fall.

CPU and wall time, including CPU seconds per fixed-budget effective sample,
will be reported separately.  They do not alter the frozen mixing gate, but
must be considered before allocating a broader production budget.

This A/B test is an algorithm audit, not evidence for a phase.  Even an
`ADVANCE` result only permits re-auditing already ranked candidates with
unchanged physics gates.
