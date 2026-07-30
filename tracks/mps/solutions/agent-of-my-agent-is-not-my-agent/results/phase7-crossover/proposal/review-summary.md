# Phase 7 crossover exploration proposal

## Planned scope

- `sigma = 1.50,1.60,1.70,1.75,1.80,1.90,2.00`
- common broad grid `Gamma = 1.20:0.05:1.90`
- `L = 32,64`, `K=24`, `chi=64`, even sector
- 210 broad cells
- exact-zero MPO pruning and HDF5 checkpointing
- no approximate MPO compression or automatic Gamma expansion

The common Gamma-grid hash is
`b7e5ad646ade0460faa7bfa9b94bda7dadc54a1fea28389e9ce3ef4463ad5817`.
The proposal contains no HDF5 state and has not run a DMRG cell.

## Exponential-fit preparation

Each sigma has an independently regenerated `K=24`, `alpha=0.5`,
`r_fit=2048` fit. The maximum relative errors are:

| sigma | infinite kernel | periodized L=32 | periodized L=64 |
|---:|---:|---:|---:|
| 1.50 | 2.405e-7 | 2.904e-5 | 8.218e-5 |
| 1.60 | 2.291e-7 | 1.349e-6 | 3.901e-6 |
| 1.70 | 2.706e-7 | 3.748e-7 | 9.497e-7 |
| 1.75 | 3.810e-7 | 2.286e-6 | 8.284e-6 |
| 1.80 | 4.096e-7 | 2.164e-6 | 8.181e-6 |
| 1.90 | 4.455e-7 | 1.498e-6 | 5.915e-6 |
| 2.00 | 4.228e-7 | 1.088e-6 | 4.274e-6 |

The larger `sigma=1.50` periodized residual remains below `1e-4` but should
be retained in the Hamiltonian-level uncertainty table. It does not trigger
an automatic K increase.

## Local resource estimate

Measured `chi=128` L32/L64 sector timings were scaled by `(64/128)^3`.
The conservative memory bound was scaled by `(64/128)^2`.

| stage | maximum new cells | central serial wall time |
|---|---:|---:|
| broad even-sector scan | 210 | 2.81 h |
| fixed refinement interiors | 56 | 0.75 h |
| targeted odd-sector gaps | 28 | 0.38 h |
| **combined** | **294** | **3.94 h** |

The preregistered two-times safety estimate is 7.87 serial wall-hours.
Estimated peak memory is 0.325 GiB per `chi=64` cell; this is a scaling
estimate, not a new measured peak. The broad stage is reviewed independently
before refinement or gap work is generated.

## Review gate

No scan should start until the common grid, 210 commands, fit residuals, and
resource estimate are accepted. After broad results exist, each sigma is
classified as uniquely bracketed, unresolved, ambiguous, or incomplete.
Only a unique measured bracket generates the fixed `0.01` refinement grid.
