# Clock Monte Carlo cross-check protocol

Locked before the 16-cell production array.

## Purpose and scope

This is an implementation-independent thermodynamic cross-check of the
Fukui-Todo/FK production sampler. It compares `Qm` and
`chi = L^2 <m^2>`. Clock local updates do not construct FK clusters and
therefore do not measure or validate `Rp`.

## Correctness gates

1. On a fixed `L=4` configuration, compare 200,000 one-spin proposals from
   the clock sampler and an explicit factorized-Metropolis implementation.
   Their acceptance probabilities must agree within six binomial standard
   errors.
2. Require `sum_j J_ij = 4` to floating-point precision.
3. At `sigma=1.875`, run two seeds at `L=64,128` with 50,000 thermalization
   and 300,000 measurement sweeps. Proceed only if both seeds are visibly
   mixed and the combined `Qm` and `chi` agree with FK within three combined
   standard errors. If block errors are unreliable, increase sampling rather
   than weakening this gate.

## Production grid

- `sigma = 1.875, 2.0`
- `L = 64, 128, 256, 512`
- two independent seeds per point, 16 cells total
- thermalization sweeps by size: `50k, 100k, 200k, 300k`
- measurement sweeps: `1,000,000` per cell
- 50 raw blocks per cell

The production analysis reports per-seed results, block errors, maximum
autocorrelation time, and standardized Clock-minus-FK differences. Failed
cells are rerun only with identical parameters and remain documented.
