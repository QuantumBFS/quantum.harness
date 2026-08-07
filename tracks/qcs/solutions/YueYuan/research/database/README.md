# Benchmark Database

This directory contains structured inputs for the YueYuan autoresearch validator and run loop. Generated traces, CSV files, and figures must be written under `tracks/qcs/results/YueYuan/`, which is outside git by workshop convention.

## Schema

`benchmark_plan.json` contains:

- `instances`: model/device families to run.
- `methods`: optimizer/search-space definitions to compare.
- `oracle_contract`: fields every query log must expose.
- `metrics`: quantities used by the acceptance gate.

The database is hand-curated from challenge #113 and the rendered knowledge base in `../../.knowledge/`. It is a plan database, not generated data.

## Provenance

- The `d^2 - 1` target-rank invariant and model/device boundary come from challenge #113 and the low-rank Hessian/control-landscape references.
- The noisy closed-loop optimizer contract follows the Ad-HOC and closed-loop feedback-control references.
- The pulse-basis choices follow CRAB and discrete-adjoint control references.
- The failure sweeps are motivated by the low-rank Hessian paper's Hamiltonian-error experiment and the challenge issue's model-truth-gap section.
