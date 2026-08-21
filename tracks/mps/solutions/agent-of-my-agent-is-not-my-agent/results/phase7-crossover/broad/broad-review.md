# Phase 7 broad-pass review

## Crossing table

The table uses only the approved even-sector `K=24`, `chi=64`, `L=32,64`
broad pass. `Gamma_x` is a linear interpolation of
`R_xi(32)-R_xi(64)` between the two broad-grid endpoints. The quoted
resolution is half the `0.05` broad spacing; it is not a statistical error
bar.

| sigma | crossing bracket | D_left | D_right | broad Gamma_x | resolution | status |
|---:|---:|---:|---:|---:|---:|---|
| 1.50 | [1.75, 1.80] | -0.017058 | +0.027204 | 1.769270 | 0.025 | bracketed |
| 1.60 | [1.65, 1.70] | -0.035680 | +0.024106 | 1.679840 | 0.025 | bracketed |
| 1.70 | [1.55, 1.60] | -0.087422 | +0.002895 | 1.598397 | 0.025 | bracketed |
| 1.75 | [1.55, 1.60] | -0.021260 | +0.038113 | 1.567904 | 0.025 | bracketed |
| 1.80 | [1.50, 1.55] | -0.059229 | +0.024463 | 1.535385 | 0.025 | bracketed |
| 1.90 | [1.45, 1.50] | -0.047089 | +0.035310 | 1.478574 | 0.025 | bracketed |
| 2.00 | [1.40, 1.45] | -0.050880 | +0.038662 | 1.428411 | 0.025 | bracketed |

There are no unresolved sigma cases on the broad grid and no multiple
crossings. These are finite-size broad-grid estimates, not
thermodynamic-limit critical fields.

## Numerical-quality flags

All 210 cells completed and wrote independent checkpoints, summaries, and
logs. The preregistered exploration checks flagged 99 cells:

- 90 relative-variance flags;
- 75 discarded-weight flags;
- 19 sweep-cap flags;
- no invalid second-moment observable flags.

A cell can carry more than one flag. Every crossing interval contains at
least one flagged endpoint state, primarily the `L=64` state. Consequently,
the crossing trend is visible but selective `chi=128` validation at the
crossing endpoints should be reviewed before treating the interpolation
shifts as resolved physics.

No `chi=128`, refinement-grid, odd-sector, gap, or `z_eff` calculation was
started.

## Runtime and artifacts

The four-worker local campaign completed in approximately 84.3 minutes with
zero execution failures.

- `rxi-broad.csv`: all 210 raw crossing observables and convergence metrics;
- `broad-review.csv`: machine-readable crossing table;
- `quality-flags.json`: every selective-validation flag;
- `decisions/`: one deterministic broad-grid decision record per sigma;
- `cells/`: logs, HDF5 checkpoints, checkpoint metadata, and summaries.
