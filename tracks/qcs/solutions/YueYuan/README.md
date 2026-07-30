# YueYuan: Hessian-guided sim-to-real quantum gate calibration

**Submission entry points:** [judge-facing result](SUBMISSION.md) |
[exact reproduction](research/attempts/attempt-004/REPRODUCE.md) |
[detailed report](research/attempts/attempt-004/REPORT.md)

## Team

| | |
|---|---|
| **Team name** | YueYuan |
| **Members** | 原钺 |

## Challenge

| Row | |
|---|---|
| **Challenge** | Determine whether a low-dimensional control subspace extracted from the Hessian of a differentiable quantum-device model can reduce the noisy black-box queries and measurement shots required to calibrate a target quantum gate, and identify when model-device mismatch causes the reduced subspace to fail. |
| **Catalog issue** | Addresses #113 - "Sim-to-Real for Quantum Gates," released by Lei Wang, Institute of Physics, Chinese Academy of Sciences. |
| **Track** | `tracks/qcs/` - our call: issue #113 names quantum control and differentiable programming rather than a repository folder. We place it under QCS because our primary artifact will be a differentiable quantum-dynamics simulator, Hessian-subspace extraction, and software black-box closed-loop optimization; real-hardware calibration is an optional extension. |

## Initial Plan

1. Start from the differentiable quantum-control notebook linked in issue #113.
2. Build a clean model/device boundary: the differentiable model is inspectable, while the true device is query-only and returns noisy finite-shot fidelity estimates.
3. Extract the model Hessian principal directions at the open-loop optimum.
4. Compare closed-loop derivative-free optimization in the Hessian subspace against full-parameter search.
5. Report queries-to-target and shot counts versus subspace dimension, model-truth gap, and random seed.

## First Milestone

Produce the minimal headline demo for a simulated two-qubit gate:

- open-loop model optimization,
- top-`k` Hessian subspace extraction,
- perturbed query-only true device,
- noisy closed-loop optimizer,
- query-count comparison between full search and Hessian-guided subspace search.

## Current Autoresearch State

The survey/database phase and validator gate are complete. The executable validator now lives in `research/validator/`, with public development instances in `research/benchmark/dev/` and a sealed gitignored holdout split under `research/benchmark/private/`.

Attempt 001 started the run stage with a local rank-15 surrogate candidate. Attempt 002 added a toy two-qubit dynamics path under `research/attempts/attempt-002/`: exact unitary propagation, CZ infidelity, finite-difference Hessian geometry, and exact final checks. The public dev validator accepted attempt 002 with score `3.031578947368421`.

Attempt 003 now replaces deterministic query formulas with a pure-NumPy noisy-oracle simplex optimizer under `research/attempts/attempt-003/`. The public dev validator accepts attempt 003 with score `2.4615384615384617`.

Attempt 004 implements the full checklist path: JAX differentiable one-qubit and two-qubit dynamics, open-loop model optimization, Hessian/HVP checks, a strict query-only finite-shot device, sealed optimizer/scorer separation, pulse-distorted software true-device tests, model-only/full/random/Hessian/adaptive/device-informed baselines, multi-axis sweeps, generated figures, Slurm scripts, and a short report.

The moderate sealed black-box holdout sweep has now completed on CPU: 48/48 task shards, 240 method records, 120 summary groups, dev and holdout splits, and medium/large/pulse-distortion software true-device variants. Results still do not claim real hardware, but they substantially tighten the software black-box evidence.
