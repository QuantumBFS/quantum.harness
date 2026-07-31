# Exact nearest-neighbor control: completed seven-size dataset

This directory freezes the completed part of Slurm array `23025326` for the
strict nearest-neighbor square-lattice Ising control:

\[
H=-\sum_{\langle i,j\rangle}s_i s_j,\qquad
\beta_c=\frac{\log(1+\sqrt{2})}{2},
\]

with periodic boundary conditions, exact Swendsen--Wang/FK updates, and four
independent seeds per lattice size.

## Published cells

This dataset contains exactly 28 completed numerical cells:

| \(L\) | Seeds | Measurement sweeps per seed | Mean \(Q_m\) | Mean \(R_p\) |
|---:|---|---:|---:|---:|
| 64 | 73001, 84002, 95003, 106004 | 200000 | 0.8560859 | 0.0270663 |
| 128 | 73001, 84002, 95003, 106004 | 200000 | 0.8551993 | 0.0231513 |
| 256 | 73001, 84002, 95003, 106004 | 150000 | 0.8561858 | 0.0307917 |
| 512 | 73001, 84002, 95003, 106004 | 100000 | 0.8558562 | 0.0257625 |
| 1024 | 73001, 84002, 95003, 106004 | 50000 | 0.8568208 | 0.0280400 |
| 2048 | 73001, 84002, 95003, 106004 | 20000 | 0.8558951 | 0.0345500 |
| 4096 | 73001, 84002, 95003, 106004 | 5000 | 0.8517651 | 0.0094000 |

The means in this table are unweighted means over the four seeds. Per-seed
estimates, block errors, autocorrelation estimates, and susceptibilities are
stored in each cell's `summary.csv` and `blocks.csv`.

Each cell contains one non-empty `summary.csv`, `blocks.csv`, `metadata.txt`,
and `manifest.json`. The frozen `run_spec.json` records the complete
seven-size plan \(L=64,128,256,512,1024,2048,4096\). The \(L=4096\)
statistics are visibly noisier because the registered budget contains only
5,000 measurement sweeps per seed; these cells are retained without
selection or post-hoc extension.

## Provenance note

The numerical files for all 28 cells were written successfully before a
Python 2.7 text/byte incompatibility caused the original wrapper to exit while
writing manifests. Thus Slurm records the array cells as failed even though
the Julia simulation completed and wrote non-empty summaries, blocks, and
metadata. The numerical evidence was not recomputed or altered.
`scripts/nn_repair_manifests.py` rebuilt manifests deterministically from
those saved files and the frozen run specification. Repository-relative paths
in the published manifests, run specification, and Slurm scripts point to the
registered team directory.
