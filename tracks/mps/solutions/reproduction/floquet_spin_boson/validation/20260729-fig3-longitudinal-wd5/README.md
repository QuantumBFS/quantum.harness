# Fig. 3 longitudinal validation checkpoint

This directory records a deliberately partial validation result for Fig. 3 of
Mickiewicz, Link, and Strunz, *Exact Floquet Dynamics of Strongly Damped
Driven Quantum Systems* (arXiv:2511.08754v3). It is not a claim that the full
figure has been reproduced.

## Setup

- Hamiltonian:
  `H(t)=Ωσx/2+εd cos(ωd t)σx+σz⊗Σλgλ(bλ+bλ†)+Σλωλbλ†bλ`
- `Ω=1`, `εd=1`, `ωd=5`, `α=0.05`, `ωc=2.5`, and zero temperature.
- Time step target `dt=π/60`; the exact period grid used 24 steps.
- UniformTEMPO compression tolerance `1e-10`; achieved bond dimension
  `χ=279`.
- Ordered augmented-space correlation window: 4096 lag steps.
- Reference: author data from Zenodo record 19593671.

## Result

The longitudinal continuous heat-current spectrum visually overlaps the
Zenodo curve in `fig3_checkpoint.png`. The blank transversal panels are
intentional: that point had not yet passed the strict tail gate when this
checkpoint was recorded.

| Diagnostic | Value | Gate | Status |
|---|---:|---:|---|
| `|λ0−1|` | `1.10e-8` | `1e-6` | pass |
| right residual | `1.13e-14` | `1e-10` | pass |
| left residual | `1.72e-14` | `1e-10` | pass |
| `C(0)` error | `5.82e-9` | `1e-8` | pass |
| correlation tail norm | `4.86e-5` | `1e-4` | pass |
| correlation tail mean | `4.30e-6` | `1e-5` | pass |
| correlation tail slope | `2.12e-9` | `1e-5` | pass |
| reference maximum error | `1.38e-4` | comparison only | recorded |
| reference RMSE | `1.63e-5` | comparison only | recorded |

Point runtime was 102.87 seconds. The two-point 4096-lag attempt used about
1.50 GB peak resident memory and 578.56 seconds total.

## Re-run

From the repository root:

```bash
PROJ=tracks/mps/solutions/reproduction/floquet_spin_boson
OUT=tracks/mps/results/fig3-longitudinal-wd5
OPENBLAS_NUM_THREADS=1 JULIA_NUM_THREADS=1 \
  julia --project="$PROJ/envs/current" "$PROJ/scripts/reproduce_fig3.jl" \
  --parallel none --reference-dir /path/to/zenodo/fig_3 \
  "$PROJ/validation/20260729-fig3-longitudinal-wd5/config.toml" "$OUT"
```

Large raw correlations, the steady-state checkpoint, cached influence
functionals, and the Zenodo archive remain gitignored.
