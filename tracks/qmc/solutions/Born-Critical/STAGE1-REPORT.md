# Stage 1 numerical-kernel verification report

## Outcome

Stage 1 is complete. The reusable stochastic and transfer-matrix kernel passed
unit, long-product, restart, and synthetic finite-size-fit verification on a
Slurm compute node.

## Implemented components

| Component | Contract |
|---|---|
| RNG streams | Keyed by `(base_seed, model, L, replica, stream)`; independent of planning/execution order |
| Blocking | Streaming vector observations; only complete blocks enter mean/error estimates |
| Lyapunov QR | Real or complex transfer products; Householder QR; positive `R` diagonal; logged orthogonality error |
| Checkpoint | Atomic compressed NPZ, `allow_pickle=False`; restores RNG, partial block, pending QR product, optional Gaussian state, and metadata |
| Casimir fit | Weighted M0 `[1,L^-2]` or M1 `[1,L^-2,L^-4]`; explicit `phi`/Shannon sign; covariance and fit-condition diagnostics |
| Bootstrap handoff | Every supplied resample is fitted; failed resamples remain `NaN` and are counted |

The solution-specific Casimir fitter is necessary because the repository's
generic polynomial form includes every power of `1/L`, whereas the cylinder
Casimir expansion here requires an explicitly even basis.

## Successful run

| Field | Value |
|---|---|
| Slurm job | `17173` |
| State | `COMPLETED`, exit `0:0` |
| Node | `ws5` |
| Resources | CPU-only, 2 CPUs, 4 GiB, 10-minute limit |
| Elapsed | 5 seconds |
| Python | 3.11.15 |
| NumPy | 2.0.1 |
| Tests | 43 passed |
| Source digest | `c45cd0c0699eec4e4130b058bfcc117b01206c5cb619b564ff7dcd46b968da23` |

Machine-readable evidence:

```text
tracks/qmc/results/born-critical/stage1-tests/job-17173/
├── manifest.json
├── metrics.json
├── qr-stability.svg
├── runner.log
└── unittest.log
```

## Recorded numerical checks

| Check | Result | Required |
|---|---:|---:|
| Maximum exponent difference, QR interval 1/2/5 | `1.4148838350935833e-17` | `<5e-10` |
| Maximum orthogonality error, interval comparison | `1.2119211884042969e-15` | `<1e-10` |
| Long-product length | `100000` layers | `100000` |
| Long product finite | `true` | `true` |
| Long-product maximum orthogonality error | `1.1934897514720433e-15` | `<1e-10` |
| Checkpoint Lyapunov exponent error | `0.0` | exact continuation |
| Checkpoint block error | `0.0` | exact continuation |
| Checkpoint RNG error | `0.0` | exact continuation |
| Synthetic M1 `phi` central-charge error | `6.866729407306593e-14` | within numerical fit tolerance |
| Synthetic M1 Shannon central-charge error | `5.956346527113965e-14` | within numerical fit tolerance |
| M1 whitened design condition number | `15012.734754733669` | `<1e10` |

All declared stage-1 gates passed.

## Stability plot

The returned `qr-stability.svg` plots every finite-product exponent against QR
interval 1, 2, and 5. Its source points are also embedded in `metrics.json`, so
the figure can be regenerated without parsing an image.

## Startup failure retained

Job `17172` failed before Python tests because ws5 does not share ws4's `QC`
Conda environment. The stage-0 assumption that a named user environment was
available on every node was therefore removed.

The corrected Slurm runners now probe, in order, an explicitly requested
environment and then `QC`, `torch`, and `base`, selecting the first environment
that can import NumPy. Job `17173` selected ws5's `torch` environment. The
failure callback successfully returned a `startup-failed` manifest for job
`17172`, validating the operational failure path.

## Scope and next stage

This stage validates generic numerical mechanics, not a physical central
charge. Stage 2 will use these kernels to reproduce the clean critical Ising
Casimir coefficient and test fit-window stability before any disordered
production run.
