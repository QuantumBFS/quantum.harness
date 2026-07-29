# Clean Ising Production Expansion Design

**Date:** 2026-07-29  
**Challenge:** Quantum Harness issue #122  
**Team:** 卧龙凤雏

## Context

The first 33-point production run gave an exact transfer-matrix estimate
`c = 0.499316`, but the Monte Carlo route failed the predeclared integration
and fit-window stability gates. Increasing the sampling depth to 12,800
measurement sweeps reduced the Monte Carlo uncertainty and produced
`c = 0.472374` with a 95% interval `[0.443518, 0.501508]`, but exposed a
33/17-point integration shift of `0.023083`, larger than the bootstrap
standard error `0.014706`.

The failed result directories remain immutable diagnostic evidence. The next
production run changes physical-size and quadrature resolution rather than
weakening any acceptance threshold.

## Approved Production Contract

- Simulate every even circumference from `L = 4` through `L = 20`:
  `4, 6, 8, 10, 12, 14, 16, 18, 20`.
- Keep the torus length at `M = 8L`.
- Use 65 uniformly spaced coupling points from `K = 0` through `K_c`, giving
  64 Simpson intervals.
- Compare the primary 65-point integration with its nested 33-point subset.
- Keep four independent replicas, 200 burn-in sweeps, 12,800 measurement
  sweeps, and 320-sweep blocks.
- Keep `rand_xoshiro 0.8.1` `Xoshiro256++`, deterministic seed derivation,
  bootstrap seed, fit model, primary `L_min = 6` window, diagnostic
  `L_min = 4, 8` windows, and every scientific acceptance gate unchanged.

## Data Flow and Reporting

Rust remains responsible for the exact transfer-matrix calculation and all
Monte Carlo sampling. Python validates the expanded raw records, performs
the nested 65/33-point Simpson integrations, propagates block-bootstrap
uncertainty through the finite-size fits, and regenerates the same six plots
and self-contained HTML report.

Output uses a new timestamped result directory. Existing failed runs are
never overwritten or removed. The report labels the nested grids from the
manifest rather than hard-coding `17` and `33`.

## Verification and Failure Handling

Contract tests must reject any production configuration other than the
approved widths, 64 intervals, and sampling depth. Analysis tests must prove
that the nested-grid selector uses every second point and reports the actual
grid sizes. The full Rust and Python suites run before production.

The projected Monte Carlo wall time is about four minutes, based on the
measured 48.17-second run scaled by the number of lattice sites and coupling
points. The existing 600-second runtime gate remains unchanged. A scientific
gate failure still produces a complete report with an explicit failure
verdict and finalized total runtime.
