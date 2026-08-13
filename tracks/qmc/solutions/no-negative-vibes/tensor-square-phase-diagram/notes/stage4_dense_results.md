# Stage 4 dense-scan and m=10 sentinel results

Date: 2026-07-29

This note reports the pre-registered Stage 4 experiment without changing its
thresholds after seeing the samples. A statistical early stop is not a
no-go result for the model.

## Frozen hypotheses and falsifiers

The half-filled hypothesis was that the Stage 3 enhancement band contains a
collective staggered/channel mode. It required a replicated size and cooling
trend plus an independent susceptibility, Binder, structure-factor, or
correlation-length diagnostic. The competing-channel hypothesis required
matched `+mu` and `-mu` chains with identical budgets and size-enhanced
collective diagnostics. Every production replica had to reach ESS at least 40
under the frozen acceptance, sign, density, and determinant-stability audits.

The numerical-only m=10 rescue rule was recorded before that run: select at
most one `beta=4` half-filled region only if all four replicas of every
`m=4,6,8` endpoint pass, the same two-sigma/five-percent size gate passes,
the size sequence is monotone within errors, and an independent diagnostic
also passes. This rule cannot release a thermodynamic phase claim.

## Pilot and production audit

- Pilot: 180/180 replicas complete, zero early stops, zero errors, and one
  common source revision `84fc08b`. Provenance validation released 44 cells
  and stopped 46 cells at the pilot autocorrelation budget gate.
- Production: 176 requested replicas across the 44 released cells. There were
  95 ESS-passing replicas, 81 autocorrelation-cap early stops, and zero worker
  errors.
- Strict cell audit: 15/44 cells had all four production replicas pass; 29/44
  had at least one capped replica. The passing cells are on the `beta=4`
  half-filled slice; no full low-temperature or matched competition candidate
  retained the required endpoint coverage.
- Numerical stability stayed healthy: minimum direct sign `+1`, maximum
  direct/structured log-weight error `1.14e-13`, acceptance range
  `[0.483, 0.739]`, and minimum passing-replica ESS `40.03`.
- Candidate update: `SURVIVE=0`, `EXTEND=0`, `STOP=21`. All 21 stops are
  statistical-only because the audited long-chain grid is incomplete; none is
  a physical no-go conclusion.

## Numerical-only m=10 sentinel

The sole released point was

```text
g_B/g_A = 0.25
t/g_A   = 0.5
mu/g_A  = 0
beta g_A = 4
m = 10
```

The healthy `m=4,6,8` source sequence passed the unchanged size and independent
diagnostic gates. The initial m=10 budget was derived from the worst healthy
`m=8` autocorrelation time (`tau_int=15.84`): 634 warmup sweeps and 2536
measurement sweeps, followed by the ordinary production re-audit and dynamic
extension up to the frozen cap.

Two of four m=10 replicas passed ESS and stability; two reached the
autocorrelation cap. There were no determinant or worker errors. Across the
two passing replicas:

- acceptance was `0.392-0.405`, direct sign remained `+1`, and maximum
  log-weight error was `1.71e-13`;
- `Q_combined(m=10)=2.9168(90)` versus the four-replica
  `Q_combined(m=8)=2.3603(42)`, a `23.6%` increase (`z=55.9`);
- the staggered structure factor increased by `24.6%` (`z=10.2`);
- `xi/m` increased by `25.1%` (`z=22.9`);
- channel-A susceptibility did not increase significantly, channel-B
  susceptibility remained below the strict two-sigma gate, and Binder
  behavior was mixed.

The large raw size trend is reproducible in two healthy m=10 chains, but the
pre-registered four-replica m=10 cell audit fails. It is therefore not valid
phase evidence.

## First finite-size judgement

**达到早停；当前信号按有限尺寸或普通 crossover 处理，不支持继续
Stage 5 的相主张。**

The observed `m=4,6,8,10` increase is consistent with an extensive or
finite-size crossover and cannot be separated from a thermodynamic collective
effect while half of the m=10 replicas and all required `beta=8` endpoints
remain autocorrelation-censored. No m=12 expansion is released. Literature
novelty review and PRL packaging are not started because the scaling gate was
not met.

## Reproducible artifacts

- `results/stage4_20260729/pilot/aggregate/`
- `results/stage4_20260729/production/aggregate/`
- `results/stage4_20260729/m10/aggregate/`
- `results/stage4_20260729/production/aggregate/figures/`

Large checkpoints, progress logs, and raw chains remain on the approved
compute machines and are excluded from Git.
