# Fig. 2 transient reproduction

This checkpoint reproduces both panels of Fig. 2 in Mickiewicz, Link, and
Strunz, *Exact Floquet Dynamics of Strongly Damped Driven Quantum Systems*
(arXiv:2511.08754v3).

## Setup

- Hamiltonian:
  `H(t)=Ωσx/2+εd cos(ωd t)σz+σz⊗Σλgλ(bλ+bλ†)+Σλωλbλ†bλ`.
- `Ω=1`, `εd=1`, `α=0.05`, `ωc=2.5`, and zero temperature.
- Initial state `|↑z><↑z|`; observable `⟨σz(t)⟩`.
- Frequencies `ωd/Ω=2.5` and `10`; 3820 samples through `Ωt=200`.
- Target time step `dt=π/60`, with exact commensurate period grids.
- UniformTEMPO compression tolerance `1e-10`; achieved `χ=279`.
- Reference curves are the author data from Zenodo record 19593671.

## Result

The strict UniformTEMPO curves overlap the author exact curves to below
`3e-4` maximum absolute error. The comparison plot also preserves the paper's
main physical observation: Redfield–Magnus strongly overestimates the
long-time oscillations, especially at the lower drive frequency.

| `ωd/Ω` | maximum exact-reference error | RMSE | Redfield maximum error |
|---:|---:|---:|---:|
| 2.5 | `2.3485e-4` | `4.7350e-5` | `6.9204e-1` |
| 10 | `2.7806e-4` | `6.0748e-5` | `2.9383e-1` |

The run took 54.42 seconds with 1.46 GB maximum resident memory. Influence
functional construction used 38.70 seconds and propagation used 8.58 seconds.

## Re-run

From the repository root:

```bash
PROJ=tracks/mps/solutions/reproduction/floquet_spin_boson
OUT=tracks/mps/results/fig2-strict
OPENBLAS_NUM_THREADS=1 JULIA_NUM_THREADS=1 \
  julia --project="$PROJ/envs/current" "$PROJ/scripts/reproduce_fig2.jl" \
  "$PROJ/validation/20260730-fig2/config.toml" \
  /path/to/zenodo/fig_2 "$OUT"
```

Raw transient curves and the Zenodo archive remain gitignored.
