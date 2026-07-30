# Wander — Issue #276: Non-Abelian Quantum Geometry as a Chaos Probe

![Quantum geometry over an exactly degenerate manifold](https://raw.githubusercontent.com/JunkaiWang-TheoPhy/quantum.harness/664506886413b68cdbc5a362a6075c78fd5d2c46/docs/showcase/ranger-archive/assets/missions-v2/07-quantum-geometry-curved-state-space-v2.png)

> **EN** The world seemed flat only because no one had lifted the tablecloth.
>
> **中文** 世界之所以显得平坦，只因从未有人掀起那块桌布。

## Team

| Field | Value |
|---|---|
| **Team name** | Wander |
| **Members** | Chenxi Wan, Yedi Shen, Junkai Wang |
| **Contact email** | WangTheoPhys@outlook.com |

## Challenge

This submission addresses [QuantumBFS/quantum.harness#276](https://github.com/QuantumBFS/quantum.harness/issues/276): **What is the probe of quantum chaos for a degenerate eigenstate subspace?**

The executable answer is the **non-Abelian quantum geometry of the degenerate projector over coupling space**. Exact degeneracy makes the connected energy spectral form factor silent, while Berry curvature, the gauge-invariant four-channel response tensor, and Wilson holonomy remain informative.

## Headline Result

The benchmark uses a bosonic Laughlin zero-mode manifold of a Kapit–Mueller parent Hamiltonian. It combines four advances:

1. **Metric-normalized signature compression** maps the many-body projector response to an exact finite-rank complex-Jacobi process.
2. **Boundary-atom form-factor theory** treats exact \(\lambda=\pm1\) modes algebraically and reaches rank \(D=800\).
3. **Matrix-element Geometric ETH** measures a gauge-invariant connected four-channel component on the genuine \(N=3,4,5\) sequence.
4. **Fixed-Chern holonomy engineering** tunes relative Wilson transport while preserving the full spectrum, the gap, and the Chern class.

At \(\tau=0.5\), the physical curvature form factor is \(K_{F,c}=0.502\), compared with the finite-Jacobi value \(K_{J,c}=0.501\). The connected four-channel excess decreases as \(0.15385\to0.10078\to0.08183\). The registered result branches are `deformed_geometric_eth` and `fixed_chern_deformed_holonomy`.

## Deliverables

- [Innovation-first project guide](research/README.md)
- [Task-level reproduction guide](research/01_task_folder/task_05/README.md)
- [Markdown technical report](research/docs/2026-07-30-task05-technical-report.md)
- [17-page article](research/01_task_folder/task_05/script/output/spectral_silence_and_geometric_chaos_v3.pdf)
- [Machine-readable release manifest](research/01_task_folder/task_05/script/output/release_manifest_v1.json)
- [Seven publication figures](research/01_task_folder/task_05/script/output/)
- [Full REVTeX manuscript](research/overleaf_sync/geometric_eth_large_scale/)
- [Public research repository](https://github.com/JunkaiWang-TheoPhy/Chaos-of-Quantum-Geometry/tree/codex/task-05-geometric-chaos-baseline)

## Verification

```bash
cd tracks/mps/solutions/Wander-276
bash verify.sh
```

Verified release state:

- 17/17 public-release contract checks;
- 38/38 focused quick-path tests;
- 86 passing compact-checkout tests plus six production-data tests activated by the manifest-listed arrays;
- 25/25 article-delivery checks across 17 rendered pages and seven synchronized figures;
- article SHA-256 `a75377f76acd78eb3354e186a57933abdf11abbbe5e9a8abd43482ca8c4e05ad`.

## MPS Growth Path

Issue #276 is registered on the MPS track. This exact-kernel package supplies the finite-size calibration layer for a tensor-network extension: reproduce the projector response and four-channel invariants at the ED-accessible sizes, then scale the same gauge-invariant observables with an MPS representation of the degenerate manifold. The preregistered next targets are \(N=6\), a second exact-degeneracy mechanism, and a locality-based derivation of the connected channel law.

## Provenance

The capsule is synchronized from public commit `d0a03ae` of `JunkaiWang-TheoPhy/Chaos-of-Quantum-Geometry`. Compact artifacts are stored in Git; 25 production arrays totaling 447,704,793 bytes are recorded by SHA-256, byte size, and producer command in the release manifest.
