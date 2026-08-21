# Phase 7 minimal validation report

## Chi validation

| sigma | max |Delta R_xi| | signs unchanged | bracket unchanged | accepted |
|---:|---:|:---:|:---:|:---:|
| 1.70 | 2.925e-06 | True | True | True |
| 1.75 | 3.029e-06 | True | True | True |
| 1.80 | 3.066e-06 | True | True | True |
| 2.00 | 3.653e-06 | True | True | True |

All tested endpoint shifts are below `1e-4`, and the broad crossing brackets retain their sign structure.

## Provisional gap scaling

| sigma | broad Gamma_x | Delta(32) | Delta(64) | gap-based pairwise z_eff | status |
|---:|---:|---:|---:|---:|---|
| 1.75 | 1.567904 | 0.167840 | 0.099970 | 0.747529 | provisional_chi128_rerun_requested |
| 1.80 | 1.535385 | 0.156477 | 0.092582 | 0.757137 | provisional_chi128_rerun_requested |
| 2.00 | 1.428411 | 0.126538 | 0.075237 | 0.750067 | provisional_chi128_rerun_requested |

The gap-based pairwise effective dynamical exponents are provisional because
every tested L=64 odd endpoint state exceeds the preregistered variance and
discarded-weight flags. Six selective chi=128 odd reruns are requested but
were not started.

No K=32, L=128, or Gamma-refinement calculation was run.
