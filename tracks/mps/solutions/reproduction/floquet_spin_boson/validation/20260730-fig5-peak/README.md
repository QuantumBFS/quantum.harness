# Fig. 5 strict peak checkpoint

This checkpoint validates the longitudinal and transversal total heat current
at `ωd=1.25Ω`, the maximum of the transversal author curve in Fig. 5 of
Mickiewicz, Link, and Strunz, *Exact Floquet Dynamics of Strongly Damped
Driven Quantum Systems* (arXiv:2511.08754v3).

It is not a claim that all 191 paper frequencies have been recomputed.

## Setup

- Hamiltonian:
  `H(t)=Ωσx/2+εd cos(ωd t)σν+σz⊗Σλgλ(bλ+bλ†)+Σλωλbλ†bλ`.
- Longitudinal drive uses `σν=σx`; transversal drive uses `σν=σz`.
- `Ω=1`, `εd=1`, `ωd=1.25`, `α=0.05`, `ωc=2.5`, and zero temperature.
- Target time step `dt=π/60`; the exact period grid has 96 steps.
- UniformTEMPO compression tolerance `1e-11`; achieved `χ=506`.
- Ordered augmented-space correlation window: 8192 lag steps.
- Total current includes both the continuous spectrum and discrete weights.
- Reference: author data from Zenodo record 19593671.

## Result

| Drive | Our total current | Zenodo | Absolute error |
|---|---:|---:|---:|
| longitudinal | `0.0921381474` | `0.0921056612` | `3.2486e-5` |
| transversal | `0.0878251053` | `0.0878074041` | `1.7701e-5` |

| Diagnostic | Longitudinal | Transversal | Gate |
|---|---:|---:|---:|
| `C(0)` error | `6.57e-10` | `2.00e-9` | `1e-8` |
| tail norm | `6.73e-6` | `7.09e-6` | `1e-4` |
| tail mean magnitude | `2.76e-7` | `6.25e-7` | `1e-5` |
| tail slope magnitude | `1.12e-10` | `2.77e-10` | `1e-5` |
| energy-balance error | `9.47e-4` | `6.43e-4` | `1e-3` |

Both points pass every configured gate. The combined run took 5072.81 seconds
(84.55 minutes) with 1.50 GB maximum resident memory.

At the measured single-core rate, the complete 191-frequency × two-drive scan
would require roughly eleven days before convergence-axis repeats. It remains
a cluster production task.

## Re-run

```bash
PROJ=tracks/mps/solutions/reproduction/floquet_spin_boson
OUT=tracks/mps/results/fig5-peak
OPENBLAS_NUM_THREADS=1 JULIA_NUM_THREADS=1 \
  julia --project="$PROJ/envs/current" "$PROJ/scripts/reproduce_fig5.jl" \
  --parallel none --resume --reference-dir /path/to/zenodo/fig_5 \
  "$PROJ/validation/20260730-fig5-peak/config.toml" "$OUT"
```

Raw correlations, steady states, cached influence tensors, and the Zenodo
archive remain gitignored.
