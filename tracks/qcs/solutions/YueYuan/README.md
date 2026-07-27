# YueYuan: Hessian-guided sim-to-real quantum gate calibration

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
