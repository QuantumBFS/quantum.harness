# Stage 4 channel-reflection sampler pre-registration

Date: 2026-07-29

## Frozen hypothesis and proposal

The completed autocorrelation diagnosis shows that full auxiliary-field channel
means, rather than `q_combined`, dominate the Stage 4 early stops.  A distinct
falsifiable hypothesis is that the local sampler remains trapped for long
periods in opposite-sign sectors of a channel history.

For one channel at a time, propose the parameter-free involution

`phi'_c(tau) = -phi_c(tau)` for every imaginary-time slice.

The standard-normal auxiliary-field prior is exactly invariant under this
reflection, and the forward and reverse proposals are identical.  The
Metropolis ratio is therefore only the fermion determinant ratio.  Local
time-slice pCN updates remain active.  The previously stopped
`temporal_block_scale=0.1` proposal is disabled.

The reflection proposal has no tunable scale or selected temporal mode.  It is
attempted once per channel per sweep and has separate acceptance, checkpoint,
timing and provenance fields.

## Ordered validation

1. **m=3 ED gate.**  At
   `(beta,dt,t,g_B/g_A,mu,V)=(2,0.1,0.5,1,0,0.15)`, run four paired-seed
   replicas per arm, with 240 warmup sweeps, 800 measurement sweeps and
   `measure_every=2`.
2. **One censored Stage 4 A/B point.**  If and only if the m=3 aggregate is
   `PASS`, run
   `(m,beta,dt,t,g_B/g_A,mu)=(8,8,0.2,0.5,0.25,0)` with two paired-seed
   replicas per arm, 240 warmup sweeps, 640 measurement sweeps and
   `measure_every=2`.
3. The Stage 4 runner must consume a same-revision m=3 PASS artifact and bind
   its digest into every chain fingerprint.
4. Do not change budgets, seeds, observables or gates after results are seen.
   Do not combine this proposal with the failed fixed-scale temporal block.

All numerical work uses independent processes, one BLAS thread, at most 14 WSL
workers or 62 CPU workers.

## Frozen gates

The m=3 gate passes only if:

- total and reflection acceptance are each in `[0.05,0.995]`;
- direct sign is positive, maximum determinant log-weight mismatch is
  `<=1e-6`, and sampled density remains in `[-1e-7,1+1e-7]`;
- every monitored autocorrelation estimate is finite and at least `0.5`;
- energy, density and `q_combined` agree with ED within 3 aggregate standard
  errors in both arms;
- energy, density, `q_a_sq`, `q_b_sq` and `q_combined` agree between arms
  within 3 combined standard errors.

Any failure stops reflection updates before Stage 4.

At the single Stage 4 A/B point, use the same numerical windows.  All five
observables must agree within 2 combined standard errors.

- `ADVANCE`: all audits pass and median worst tau falls by at least 25%;
- `INCONCLUSIVE`: all audits pass and tau falls by less than 25%; permit one
  longer confirmation at this exact point with no algorithm change;
- `STOP`: an audit or consistency gate fails, reflection acceptance fails, or
  median worst tau does not fall.

CPU and wall time per effective sample are reported separately and must be
considered before any broader allocation.  An `ADVANCE` result is only an
algorithm release; it is not evidence for a phase.
