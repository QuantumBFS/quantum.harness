# Wander — Issue #276: Chaos in Exactly Degenerate Quantum Manifolds

![Quantum geometry over an exactly degenerate manifold](https://raw.githubusercontent.com/JunkaiWang-TheoPhy/quantum.harness/664506886413b68cdbc5a362a6075c78fd5d2c46/docs/showcase/ranger-archive/assets/missions-v2/07-quantum-geometry-curved-state-space-v2.png)

> **EN** The spectrum is silent; the geometry is not.
>
> **中文** 能谱沉默，几何仍然说话。

## Team

| Field | Value |
|---|---|
| **Team name** | Wander |
| **Members** | Chenxi Wan, Yedi Shen, Junkai Wang |
| **Contact email** | WangTheoPhys@outlook.com |

## Challenge and Answer

This submission addresses [QuantumBFS/quantum.harness#276](https://github.com/QuantumBFS/quantum.harness/issues/276): **What probes quantum chaos inside an exactly degenerate eigenspace?**

The executable answer is the **non-Abelian quantum geometry of the protected projector over coupling space**. If (P(\lambda)) is the degenerate projector and (X_a=(1-P)\partial_aP), then

$$\mathcal Q_{ab}=X_a^\dagger X_b,\qquad g_{ab}=\frac{\mathcal Q_{ab}+\mathcal Q_{ba}}{2},\qquad F_{ab}=i(\mathcal Q_{ab}-\mathcal Q_{ba}).$$

Ordinary level statistics is undefined inside a flat multiplet, but (g), (F), gauge-invariant four-channel contractions, Chern numbers, and Wilson holonomy remain nontrivial.

## Independent Protection Mechanisms

The release no longer rests on one fractional-quantum-Hall example.

| Mechanism | Protected manifold | Exact response structure | Role |
|---|---|---|---|
| Kapit–Mueller/Laughlin parent (H=B^\dagger B) | Frustration-free, gapped zero modes | One-sided response (X=-H_\perp^+B^\dagger\delta BP) | Local topological benchmark, Jacobi curvature, fixed-Chern holonomy |
| Generic cubic (\mathcal N=2) SYK (H=\{Q,Q^\dagger\}) | Charge-resolved harmonic cohomology | Orthogonal exact/coexact response (X=X_-\oplus X_+) | Independent supersymmetric mechanism and sealed covariance test |

Nilpotency gives (X_-^\dagger X_+=0) exactly. The two-sided Hodge decomposition is therefore a physical response-complex structure, not a basis rewrite of the Laughlin calculation.

## Registered Scientific Test

For eight coupling tangents, the code whitens the channel covariance and evaluates the gauge-invariant tensor

$$\mathcal T_{abcd}=\frac1D\operatorname{Tr}(\widehat X_a^\dagger\widehat X_b\widehat X_c^\dagger\widehat X_d).$$

The (N=8,10,12) pilot uses complete disorder realizations as the uncertainty unit. A held-out (N=14) calculation freezes two prediction models before any four-channel outcome is opened:

1. a collapsed separable covariance Gaussian null;
2. an exact/coexact Hodge-resolved separable covariance Gaussian null.

Safe covariates and predictions are SHA-256 sealed. Unsealing is an explicit, separate command and is never launched by the scheduler dependency chain. The seal was independently checked before opening, and the frozen result is:

| $N=14$ sparse sector | Physical median (95% bootstrap) | Collapsed null (97.5% prediction) | Hodge null (97.5% prediction) |
|---|---:|---:|---:|
| Adjacent | 0.301529 [0.291527, 0.312061] | [0.111789, 0.111852] | [0.112344, 0.112513] |
| Central | 0.374993 [0.368980, 0.380473] | [0.111338, 0.111353] | [0.111333, 0.111348] |

Both nulls miss both primary sectors, selecting `cohomological_non_gaussian_class`.

## Claim Boundary

This submission establishes an **independent model/operator class** for protected quantum-geometric chaos and finite-size $N=8$--$14$ four-channel response memory beyond two preregistered separable covariance nulls. It does **not** claim asymptotic Geometric ETH, conventional energy-resolved ETH, real-time chaos, or a thermodynamic-limit theorem. Null rejection does not by itself prove intrinsic non-Gaussianity after matching every entrywise nonseparable covariance.

## Deliverables

- [Research and reproduction guide](research/README.md)
- [Task-level guide](research/01_task_folder/task_05/README.md)
- [Letter source](research/overleaf_sync/cohomological_geometric_eth/main.tex)
- [Supplement source](research/overleaf_sync/cohomological_geometric_eth/supplement.tex)
- [Compiled Letter](research/01_task_folder/task_05/script/output/response_complex_memory_v7.pdf)
- [Compiled Supplemental Material](research/01_task_folder/task_05/script/output/response_complex_memory_supplement_v7.pdf)
- [Exact-data result report](research/01_task_folder/task_05/script/output/susy_hodge_geometric_eth_report_v7.md)
- [Scientific ceiling and literature memo](research/docs/2026-08-01-scientific-ceiling-strategy.md)
- [Public research branch](https://github.com/JunkaiWang-TheoPhy/Chaos-of-Quantum-Geometry/tree/codex/task-05-geometric-chaos-baseline)

## Verification

```bash
cd tracks/mps/solutions/Wander-276
bash verify.sh
```

The verification path checks the exact Hodge identity, analytic controls, pilot-grid completeness, outcome-blind sealing, artifact hashes, frozen branch selection, figure provenance, and byte-exact Letter/Supplement delivery.

## Next Scientific Gate

The finite-size result is designed to expose the next theorem rather than hide it. The two high-ceiling targets are:

- an asymptotic concentration/scaling law for the covariance-controlled response tensor;
- a spatially local nilpotent-supercharge model with a stable zero-mode count, open gap, and moving cohomological projector.

These are journal-ceiling gates, not assumptions built into the current claim.
