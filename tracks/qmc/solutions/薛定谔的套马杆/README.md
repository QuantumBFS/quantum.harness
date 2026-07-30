## Team

| | |
|---|---|
| **Team name** | 薛定谔的套马杆 |
| **Members** | Gui-Xin Liu, ShangTech University; Hao-Yu Lu, Hong Kong University |

## Challenge

| Row | |
|---|---|
| **Challenge** | Can finite-size QMC of the normalized two-dimensional long-range Ising model distinguish whether long-range universality ends at σ*=7/4 or σ*=2, beyond conclusions that depend on a single correction fit? |
| **Catalog issue** | `Addresses #86` — “Where does long-range universality end? Three adversarial tests of the σ*=7/4 vs 2 dispute,” released by Kun Chen, Institute of Theoretical Physics, Chinese Academy of Sciences. |
| **Track** | `tracks/qmc/` — the team selected Track A, whose prescribed core calculation is classical Monte Carlo. |

## Implementation

The reproducible implementation is in [`long_range_ising_fk/`](long_range_ising_fk/):

- Fukui–Todo/Poisson-event FK cluster Monte Carlo with wrapping observables;
- an independent factorized-Metropolis Clock implementation;
- locked power-law and marginal/log correction analyses;
- Slurm production jobs, tests, bilingual reports, and frozen raw-data escrow.

The frozen base production contains 96/96 successful cells. The large-size
cutoff snapshot contains 36 completed cells with central data through
$L=2048$, and the independent Clock production contains 16/16 completed
cells. The defensible conclusion is that the finite-size behavior is
reproduced, while thermodynamic discrimination between
$\sigma_*=7/4$ and $\sigma_*=2$ remains inconclusive.

## Run and inspect

From the repository root:

```bash
SOLUTION="tracks/qmc/solutions/薛定谔的套马杆/long_range_ising_fk"
julia --project="$SOLUTION" "$SOLUTION/test/runtests.jl"
sbatch "$SOLUTION/jobs/production_20260727.sbatch"
```

- [English report](long_range_ising_fk/reports/track_a_report_en.md)
- [中文报告](long_range_ising_fk/reports/track_a_report_zh.md)
- [Locked base analysis](long_range_ising_fk/locked_analysis.md)
- [Locked extension analysis](long_range_ising_fk/locked_extension_analysis.md)
- [Frozen-data manifest](long_range_ising_fk/data_manifest.md)
