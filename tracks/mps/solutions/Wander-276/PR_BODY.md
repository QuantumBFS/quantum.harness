<!-- wander-artwork -->
![Wander — Issue #276](https://raw.githubusercontent.com/JunkaiWang-TheoPhy/quantum.harness/664506886413b68cdbc5a362a6075c78fd5d2c46/docs/showcase/ranger-archive/assets/missions-v2/07-quantum-geometry-curved-state-space-v2.png)

> **EN** The spectrum is silent; the geometry is not.
>
> **中文** 能谱沉默，几何仍然说话。
<!-- /wander-artwork -->

## Team

| Field | Value |
|---|---|
| **Team name** | Wander |
| **Members** | Chenxi Wan, Yedi Shen, Junkai Wang |
| **Contact email** | WangTheoPhys@outlook.com |

## Challenge

Addresses #276: **What probes quantum chaos inside an exactly degenerate eigenspace?**

This PR gives an executable answer: the probe is the **non-Abelian quantum geometry of the protected projector over coupling space**. Exact degeneracy silences internal level statistics, while the response amplitudes (X_a=(1-P)\partial_aP) generate the quantum metric, Berry curvature, gauge-invariant four-channel tensors, and global holonomy.

## Scientific Advance

| Layer | Result |
|---|---|
| Exact geometry | (\mathcal Q_{ab}=X_a^\dagger X_b), with metric and Berry curvature as its symmetric and antisymmetric parts |
| Independent mechanism | Generic cubic (\mathcal N=2) SYK supplies a charge-resolved cohomological BPS manifold independent of the Kapit–Mueller/Laughlin parent |
| Exact structure | Nilpotency produces orthogonal exact/coexact response branches (X=X_-\oplus X_+), (X_-^\dagger X_+=0) |
| Sealed test | The complete $N=8,10,12$ pilot and separately sealed, held-out $N=14$ four-channel test reject both registered separable covariance nulls |
| Controls | Decomposable-supercharge curvature atoms and a one-sided Laughlin Gaussian-null regression |

The new scientific question is sharper than “is the Hamiltonian chaotic?” It asks whether the protected response tensor is controlled by registered two-point covariance data, or whether gauge-invariant four-point memory survives after that matching.

## Outcome-Blind Protocol

The held-out calculation freezes two parameter-free prediction models before opening the outcome sidecars: a collapsed separable covariance null and an exact/coexact Hodge-resolved separable covariance null. Complete disorder realizations—not tangent entries or tensor components—are the uncertainty unit. No scheduler dependency invokes unsealing; seal validation and scoring require a separate explicit action.

**Final held-out verdict:** independent seal validation passed before explicit unsealing, and the frozen branch is `cohomological_non_gaussian_class`.

| $N=14$ sparse sector | Physical median (95% bootstrap) | Collapsed null (97.5% prediction) | Hodge null (97.5% prediction) |
|---|---:|---:|---:|
| Adjacent | 0.301529 [0.291527, 0.312061] | [0.111789, 0.111852] | [0.112344, 0.112513] |
| Central | 0.374993 [0.368980, 0.380473] | [0.111338, 0.111353] | [0.111333, 0.111348] |

Both primary physical intervals are disjoint from both sealed prediction intervals. The prediction JSON was frozen at SHA-256 `fc300dc7e4bdc1be157919e458ac868d3468533cce31108f23c9fba4f7e9f102`; the independently recomputable inference artifact is `177643e07fc6cf210362fc1077070bd1f0ba316b6805042a626de3f96c55a627`.

## Claim Boundary

- Established: an independent supersymmetric protection mechanism, exact Hodge-resolved response identity, analytic controls, and finite-size $N=8$--$14$ response memory beyond both frozen separable covariance-null families.
- Not established: asymptotic Geometric ETH, thermalization, real-time chaos, or a thermodynamic-limit theorem.
- The selected null-rejection branch means memory beyond the frozen separable Hodge/collapsed covariance models; it does not prove non-Gaussianity relative to every possible entrywise covariance model.

## Deliverables

- [Harness solution overview](https://github.com/JunkaiWang-TheoPhy/quantum.harness/blob/codex/issue-276-quantum-geometry/tracks/mps/solutions/Wander-276/README.md)
- [Research and reproduction guide](https://github.com/JunkaiWang-TheoPhy/quantum.harness/blob/codex/issue-276-quantum-geometry/tracks/mps/solutions/Wander-276/research/README.md)
- [Letter source](https://github.com/JunkaiWang-TheoPhy/quantum.harness/blob/codex/issue-276-quantum-geometry/tracks/mps/solutions/Wander-276/research/overleaf_sync/cohomological_geometric_eth/main.tex)
- [Supplement source](https://github.com/JunkaiWang-TheoPhy/quantum.harness/blob/codex/issue-276-quantum-geometry/tracks/mps/solutions/Wander-276/research/overleaf_sync/cohomological_geometric_eth/supplement.tex)
- [Compiled Letter](https://github.com/JunkaiWang-TheoPhy/quantum.harness/blob/codex/issue-276-quantum-geometry/tracks/mps/solutions/Wander-276/research/01_task_folder/task_05/script/output/response_complex_memory_v7.pdf)
- [Compiled Supplemental Material](https://github.com/JunkaiWang-TheoPhy/quantum.harness/blob/codex/issue-276-quantum-geometry/tracks/mps/solutions/Wander-276/research/01_task_folder/task_05/script/output/response_complex_memory_supplement_v7.pdf)
- [Machine-generated result report](https://github.com/JunkaiWang-TheoPhy/quantum.harness/blob/codex/issue-276-quantum-geometry/tracks/mps/solutions/Wander-276/research/01_task_folder/task_05/script/output/susy_hodge_geometric_eth_report_v7.md)
- [Scientific ceiling and literature memo](https://github.com/JunkaiWang-TheoPhy/quantum.harness/blob/codex/issue-276-quantum-geometry/tracks/mps/solutions/Wander-276/research/docs/2026-08-01-scientific-ceiling-strategy.md)
- [Public research branch](https://github.com/JunkaiWang-TheoPhy/Chaos-of-Quantum-Geometry/tree/codex/task-05-geometric-chaos-baseline)

## Verification

```bash
cd tracks/mps/solutions/Wander-276
bash verify.sh
```

The final verifier checks exact identities, controls, the complete pilot and held-out grids, the seal state machine, every compact hash, frozen branch recomputation, figure provenance, byte-exact Letter/Supplement PDFs, and 43 focused v7 tests.

@OkongOyangO, please review the protected-response interpretation, the exact/coexact identity, and the outcome-blind four-channel test as Wander's Issue #276 submission.
