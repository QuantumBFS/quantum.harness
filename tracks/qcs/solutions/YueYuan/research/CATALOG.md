# Catalog

## Survey Status

The YueYuan DB-stage survey covers the challenge #113 pipeline: model-based open-loop control, Hessian subspace extraction, noisy query-only calibration, and failure modes under model-device mismatch. Full text was rendered for 9 of 12 references. Three older DOI-only control-landscape papers are retained as metadata-only entries because no open PDF was available through the harness helper.

No entries below are marked `reproduced` yet. Public code repositories are pinned to immutable commit hashes for later validator work; paper-only rows are algorithms or concepts without a project-specific public implementation in this repository.

## Algorithms And Software

| Name | Source | Status | Notes |
|---|---|---|---|
| Low-rank Hessian optimization | [liu_2026_high](../.knowledge/2606.05060_high-fidelity-neutral-atom-gates-leveraging-low-rank-hessian.md) | paper-only | Main methodological anchor. Extract Hessian-sensitive waveform directions, scan only principal coefficients, and interpret rank via coherent/leakage error channels. Rendered full text. |
| Dynamic dimensionality identification | [roslund_2014_dynamic](../.knowledge/10-1103-physrevlett-112-143001.md) | paper-only | Foundational state-space-dimension argument for why the effective search dimension is not the raw control dimension. Metadata-only in KB. |
| Quantum-control Hessian landscape analysis | [shen_2006_quantum](../.knowledge/10-1063-1-2198836.md) | paper-only | Foundational Hessian-rank/landscape reference cited by issue #113. Metadata-only in KB. |
| Adaptive hybrid optimal control (Ad-HOC) | [egger_2014_adaptive](../.knowledge/1402.7193_adaptive-hybrid-optimal-quantum-control-for-imprecisely-char.md) | paper-only | Open-loop gradient optimization followed by closed-loop Nelder-Mead feedback. Use as boundary discipline and noise-floor warning. Rendered full text. |
| Adaptive closed-loop feedback control | [judson_1992_teaching](../.knowledge/10-1103-physrevlett-68-1500.md) | paper-only | Historical source for using experiments as the feedback objective. Metadata-only in KB. |
| CRAB pulse basis | [caneva_2011_chopped](../.knowledge/1103.0855_chopped-random-basis-quantum-optimization.md) | paper-only | Truncated randomized basis for compact controls and direct-search compatibility. Rendered full text. |
| Discrete adjoint quantum control | [petersson_2020_discrete](../.knowledge/2001.01013_discrete-adjoints-for-accurate-numerical-optimization-with-a.md) | paper-only | Structure-preserving integration and exact discrete gradients; use as verification inspiration if generic ODE/JAX integration drifts. Rendered full text. |
| Juqbox.jl | [LLNL/Juqbox.jl](https://github.com/LLNL/Juqbox.jl/tree/3e6279d550afc214f5eccf99ba837cfc1d46b836) | pinned | Public implementation associated with discrete-adjoint quantum-control work. Pinned at `3e6279d550afc214f5eccf99ba837cfc1d46b836`; not built yet. |
| Exact-Hessian GRAPE | [dalgaard_2020_hessian](../.knowledge/2006.00935_hessian-based-optimization-of-quantum-dynamics-under-constra.md) | paper-only | Useful for small-system Hessian checks and second-order optimizer comparisons. Rendered full text. |
| QuOCS | [Quantum-OCS/QuOCS](https://github.com/Quantum-OCS/QuOCS/tree/3d67403cad44ea03450132fec25afa9114b6b2f1) | pinned | Public optimal-control software with dCRAB-style tooling. Pinned at `3d67403cad44ea03450132fec25afa9114b6b2f1`; not built yet. |
| qutip-qoc | [qutip/qutip-qoc](https://github.com/qutip/qutip-qoc/tree/1c188186f750e773c3442036ad5a53fd7c006e39) | pinned | Candidate reference baseline for GRAPE/quantum-control examples. Pinned at `1c188186f750e773c3442036ad5a53fd7c006e39`; not built yet. |
| SchusterLab quantum-optimal-control | [SchusterLab/quantum-optimal-control](https://github.com/SchusterLab/quantum-optimal-control/tree/7d6ce923673e0e625bdc943cd052f4e7d3934e6b) | pinned | Older superconducting-control reference code in the Kelly/GRAPE-TF lineage. Pinned at `7d6ce923673e0e625bdc943cd052f4e7d3934e6b`; not built yet. |
| Glassy optimal-control phase | [day_2018_glassy](../.knowledge/1803.10856_glassy-phase-of-optimal-quantum-control.md) | paper-only | Use later to stress-test the method near hard control-time regimes where local search can become exponentially difficult. Rendered full text. |
| QOC tools for barren-plateau diagnosis | [larocca_2021_diagnosing](../.knowledge/2105.14377_diagnosing-barren-plateaus-with-tools-from-quantum-optimal-c.md) | paper-only | Connects controllability and dynamical Lie algebra dimension to trainability; shelved for theoretical framing. Rendered full text. |
| QNN overparametrization/Hessian rank theory | [larocca_2021_theory](../.knowledge/10-1038-s43588-023-00467-6.md) | paper-only | Supports rank/overparametrization interpretation; shelved until core calibration plot exists. Rendered full text. |

## Reference Implementation Plan

The first validator should implement the minimal benchmark in-tree rather than depending on a large external package:

1. `model.py`: exact small-system propagator with differentiable controls.
2. `oracle.py`: private true-device Hamiltonian, noisy scalar fidelity estimate, query and shot log.
3. `subspace.py`: model Hessian, rank threshold, top-`k` basis, random-subspace baseline.
4. `run_benchmark.py`: identical optimizer settings for full, random, and Hessian searches.
5. `analyze.py`: median query/shot summaries and plots written to `tracks/qcs/results/YueYuan/`.

External pinned packages can be used later for cross-checks, not as a dependency for the first reproducible result.
