# Exact nearest-neighbor control: completed partial snapshot

This directory freezes the completed part of Slurm array `23025326` for the
strict nearest-neighbor square-lattice Ising control:

\[
H=-\sum_{\langle i,j\rangle}s_i s_j,\qquad
\beta_c=\frac{\log(1+\sqrt{2})}{2},
\]

with periodic boundary conditions, exact Swendsen--Wang/FK updates, and four
independent seeds per lattice size.

## Published cells

This snapshot contains exactly 12 completed cells:

| \(L\) | Seeds | Measurement sweeps per seed | Mean \(Q_m\) | Mean \(R_p\) |
|---:|---|---:|---:|---:|
| 64 | 73001, 84002, 95003, 106004 | 200000 | 0.8560859 | 0.0270663 |
| 128 | 73001, 84002, 95003, 106004 | 200000 | 0.8551993 | 0.0231513 |
| 256 | 73001, 84002, 95003, 106004 | 150000 | 0.8561858 | 0.0307917 |

The means in this table are unweighted means over the four seeds. Per-seed
estimates, block errors, autocorrelation estimates, and susceptibilities are
stored in each cell's `summary.csv` and `blocks.csv`.

Each cell contains one non-empty `summary.csv`, `blocks.csv`, `metadata.txt`,
and `manifest.json`. The frozen `run_spec.json` records the full seven-size
plan; only \(L=64,128,256\) are included in this partial publication because
the larger cells were still running when it was made.

## Provenance note

The numerical files were written successfully before a Python 2.7
text/byte incompatibility caused the original wrapper to exit while writing
the first manifests. The numerical evidence was not recomputed or altered.
`scripts/nn_repair_manifests.py` rebuilt manifests deterministically from the
saved summaries and frozen run specification. Repository-relative paths in
the published manifests, run specification, and Slurm scripts point to the
registered team directory.
