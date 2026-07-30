# Fig. 3 transversal validation checkpoint

This directory records the strict transversal `ωd=1Ω` validation point for
Fig. 3 of Mickiewicz, Link, and Strunz, *Exact Floquet Dynamics of Strongly
Damped Driven Quantum Systems* (arXiv:2511.08754v3). Together with the
longitudinal `ωd=5Ω` checkpoint in the neighboring
`20260729-fig3-longitudinal-wd5` directory, it provides one validated point
for each drive direction. It is not a claim that the full six-point figure
has been reproduced.

## Setup

- Hamiltonian:
  `H(t)=Ωσx/2+εd cos(ωd t)σz+σz⊗Σλgλ(bλ+bλ†)+Σλωλbλ†bλ`
- `Ω=1`, `εd=1`, `ωd=1`, `α=0.05`, `ωc=2.5`, and zero temperature.
- Time step target `dt=π/60`; the exact period grid used 120 steps.
- UniformTEMPO compression tolerance `1e-10`; achieved bond dimension
  `χ=279`.
- Ordered augmented-space correlation window: 8192 lag steps.
- Reference: author data from Zenodo record 19593671.

## Result

The transversal continuous heat-current spectrum visually overlaps the
Zenodo curve in `fig3_checkpoint.png`. That image includes the previously
validated longitudinal `ωd=5Ω` point for context; the other four paper
frequencies remain intentionally absent.

| Diagnostic | Value | Gate | Status |
|---|---:|---:|---|
| `|λ0−1|` | `1.99e-8` | `1e-6` | pass |
| right residual | `1.56e-14` | `1e-10` | pass |
| left residual | `9.74e-13` | `1e-10` | pass |
| `C(0)` error | `7.76e-9` | `1e-8` | pass |
| correlation tail norm | `2.47e-5` | `1e-4` | pass |
| correlation tail mean | `2.03e-6` | `1e-5` | pass |
| correlation tail slope | `6.30e-10` | `1e-5` | pass |
| reference maximum error | `1.44e-4` | comparison only | recorded |
| reference RMSE | `1.15e-5` | comparison only | recorded |

The point calculation took 973.98 seconds. End-to-end process wall time was
989.06 seconds, with a maximum resident set size of 1,459,437,568 bytes and no
swap.

## Re-run

From the repository root:

```bash
PROJ=tracks/mps/solutions/reproduction/floquet_spin_boson
OUT=tracks/mps/results/fig3-transversal-wd1
OPENBLAS_NUM_THREADS=1 JULIA_NUM_THREADS=1 \
  julia --project="$PROJ/envs/current" "$PROJ/scripts/reproduce_fig3.jl" \
  --parallel none --resume --reference-dir /path/to/zenodo/fig_3 \
  "$PROJ/validation/20260730-fig3-transversal-wd1/config.toml" "$OUT"
```

Large raw correlations, the steady-state checkpoint, cached influence
functionals, and the Zenodo archive remain gitignored.
