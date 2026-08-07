# Track A locked analysis record

Locked before the full production array is submitted.

## Primary data

All 96 cells are retained. Each sigma uses L=64,128,256,512, beta offsets
-0.002, 0, +0.002 around the published beta_c, and two independent seeds.
No cell is excluded because its estimate is inconvenient. Operationally failed
cells are rerun with the same parameters and identified in the log.

## Aggregation and crossings

Seed estimates are combined with inverse-variance weighting when block
variances are finite, otherwise with equal weighting. For each adjacent
L and 2L pair, Rp(beta) and Qm(beta) crossings use a straight-line fit over
the three preregistered beta points. A crossing outside the sampled interval is
reported as unresolved rather than extrapolated.

## Critical finite-size curves

Rp, Qm, and chi are evaluated at the central published beta_c. Eta is secondary
and is estimated from chi = a L^(2-eta), first using all four sizes and then
after dropping L=64.

## Competing correction models

For Rp(L) and Qm(L), fit both:

1. Power correction: O(L) = O_inf + a L^(-omega), with omega > 0.
2. Marginal/log correction: O(L) = O_inf + a/log(L/L0), with 0 < L0 < 64.

Compare Gaussian-likelihood AICc and BIC using block standard errors. Repeat
both models after dropping L=64. Fits with fewer data points than free
parameters are marked underdetermined, not ranked.

## Conclusion rule

A thermodynamic claim is allowed only if the preferred scenario and sign of
the inferred Rp limit are stable under both correction models and removal of
L=64. Otherwise the Track A conclusion is `inconclusive at school-scale
sizes`, as required by Issue #86.
