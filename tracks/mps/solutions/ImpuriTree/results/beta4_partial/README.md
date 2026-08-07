# beta = 4 implicit log-step working demonstration (partial)

- `gtau-XX.csv`: finished `G(tau)` points from the Snellius implicit
  log-step run (5 of 17 at snapshot time; run ongoing), full provenance
  columns included.
- `ctseg_beta4_u2.npz`: local TRIQS/CTSEG reference (8 replicas x 100k
  cycles); its per-bin high-frequency noise is accepted — the comparison
  demonstrates the pipeline works, it is not an error quantification.
- `beta4_u2_gtau_partial_vs_ctseg.png`: house-style comparison figure.
