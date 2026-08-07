# quantum-harness: ImpuriTree submission workspace

Team ImpuriTree's artifacts for
[QuantumBFS/quantum.harness#81](https://github.com/QuantumBFS/quantum.harness/issues/81)
(purified tensor-network Anderson impurity solver).

| path | content |
|---|---|
| `report.md` | the challenge report (beta = 16 headline results, methods, error budget, status) |
| `tdvp_beta16/` | TDVP2 vs TRIQS/CTSEG comparison at beta = 16 for `U = 2` and `U = 8`: data (`comparison_data.h5`), figure, driver/reference/plot scripts, reproducibility bundle |
| `implicit_logstep/` | production scripts and environment contract for the implicit logarithmic-grid solver (heavy computing; no full data set yet) |
| `beta4_partial/` | beta = 4 working demonstration of the implicit log-step pipeline: partial `G(tau)` points vs a local CTSEG reference |
