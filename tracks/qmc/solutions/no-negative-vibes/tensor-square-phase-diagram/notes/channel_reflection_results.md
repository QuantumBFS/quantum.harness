# Stage 4 channel-reflection result

Date: 2026-07-29

## Decisions

- Mandatory `m=3` ED gate: **PASS**.
- Single censored `m=8,beta=8` Stage 4 A/B gate: **STOP**.
- Stage 5 release: **not granted**.

Source revision for both runs:
`db0d1144a3ae954b4276137e9d6094340cb76e5f`.

## m=3 independent validation

Four paired-seed replicas per arm used 240 warmup sweeps, 800 measurement
sweeps and `measure_every=2`.

| Audit | Local control | Channel reflection | Frozen gate |
|---|---:|---:|---:|
| Energy | `-5.69539(184)` | `-5.69203(148)` | compare with ED |
| Energy vs ED `|z|` | `0.200` | `0.021` | `<=3.0` |
| Combined Q vs ED `|z|` | `0.393` | `0.012` | `<=3.0` |
| Total acceptance | `0.759-0.770` | `0.703-0.712` | `[0.05,0.995]` |
| Reflection acceptance | disabled | `0.136-0.153` | `[0.05,0.995]` |
| Direct sign | `+1` | `+1` | positive |

All sampler-to-sampler observables pass; the largest displacement is only
`0.545 sigma`.  The parameter-free proposal therefore passes its independent
method and numerical gate.

## Single m=8, beta=8 A/B

The same-revision m=3 PASS digest was bound into the CPU-run manifest and every
chain fingerprint.  Two paired-seed replicas per arm used the frozen 240/640
warmup/measurement budget and `measure_every=2`.

| Audit | Local control | Channel reflection | Result |
|---|---:|---:|---|
| Combined Q | `2.38340(153)` | `2.37109(132)` | consistent, `0.610 sigma` |
| Energy | `-41.9237(408)` | `-41.9507(600)` | consistent, `0.372 sigma` |
| Median worst tau | `25.937` | `28.211` | reflection worsens by `8.77%` |
| Minimum fixed-budget ESS | `5.83` | `4.98` | insufficient for physics |
| Total acceptance | `0.747-0.749` | `0.625-0.630` | healthy |
| Reflection acceptance | disabled | `0.0413-0.0509` | one replica below `0.05` |
| CPU seconds/effective sample | `12.91` | `23.46` | reflection is `1.817x` |
| Direct sign | `+1` | `+1` | healthy |
| Maximum log-weight error | `1.71e-13` | `1.71e-13` | healthy |

All five two-arm observables pass the frozen 2-sigma consistency gate; the
largest displacement is `0.992 sigma`.  This shows no detectable bias at the
fixed budget, but it does not rescue the candidate: one reflection acceptance
is below the frozen minimum, the median worst tau increases instead of
decreasing by 25%, and cost per effective sample is substantially worse.

## Consequence and residual uncertainty

The channel-reflection hypothesis is rejected as an autocorrelation remedy for
the targeted low-temperature large-size point.  No longer run, extra seed,
different threshold or broader reflection scan is authorized.  The low ESS
means this A/B experiment is an algorithm stop, not a physics no-go and not a
statement about the thermodynamic phase.

The unchanged values of `Q_combined` remain compatible with the previously
reported finite-size/crossover interpretation.  They are not promoted to
Stage 5 because neither arm provides the required healthy large-size
statistics.

Small artifacts are under
`results/stage4_20260729/channel_reflection/`.  Raw checkpoints and logs remain
off Git.
