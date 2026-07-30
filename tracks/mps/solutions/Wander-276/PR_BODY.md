<!-- wander-artwork -->
![Wander — Issue #276](https://raw.githubusercontent.com/JunkaiWang-TheoPhy/quantum.harness/664506886413b68cdbc5a362a6075c78fd5d2c46/docs/showcase/ranger-archive/assets/missions-v2/07-quantum-geometry-curved-state-space-v2.png)

> **EN** The world seemed flat only because no one had lifted the tablecloth.
>
> **中文** 世界之所以显得平坦，只因从未有人掀起那块桌布。
<!-- /wander-artwork -->

<!-- wander-team -->
## Team

| Field | Value |
|---|---|
| **Team name** | Wander |
| **Members** | Chenxi Wan, Yedi Shen, Junkai Wang |
| **Contact email** | WangTheoPhys@outlook.com |
<!-- /wander-team -->

## Challenge

Addresses #276: **What is the probe of quantum chaos for a degenerate eigenstate subspace?**

This PR gives an executable answer: the probe is the **non-Abelian quantum geometry of the degenerate projector over coupling space**. Exact degeneracy turns the connected energy spectral form factor into an exact baseline, while Berry curvature, a gauge-invariant four-channel response tensor, and Wilson holonomy resolve the internal complexity of the manifold.

## Scientific Advance

| Layer | New capability | Registered result |
|---|---|---|
| Exact spectrum | Exact spectral-flatness reference | \(K_{E,c}=0\) identically |
| Local geometry | Parameter-free finite-\(D\) Jacobi kernel and SFF | Physical curvature tracks the registered Jacobi ramp |
| Matrix elements | Covariance-whitened four-channel tensor | `deformed_geometric_eth` |
| Global topology | Isospectral, fixed-Chern Wilson control | `fixed_chern_deformed_holonomy` |

## Four Innovations

1. **Metric-normalized signature compression** maps the many-body projector response to an exact finite-rank complex-Jacobi process.
2. **Boundary-atom form-factor theory** treats exact \(\lambda=\pm1\) modes algebraically and reaches \(D=800\).
3. **Matrix-element Geometric ETH** measures a gauge-invariant connected four-channel component on the genuine \(N=3,4,5\) sequence.
4. **Fixed-Chern holonomy engineering** tunes relative Wilson transport while preserving every energy, the external gap, and \(C_1\).

These capabilities create a condensed-matter bridge from the Berry-curvature chaos program for degenerate BPS microstates to a local frustration-free bosonic Laughlin parent Hamiltonian.

## Quantitative Evidence

- 20,000 physical tangent pairs with a frozen `12000/4000/4000` train/validation/test split.
- At \(\tau=0.5\), physical \(K_{F,c}=0.502\) and finite-Jacobi \(K_{J,c}=0.501\).
- Four-channel connected excess \(0.15385\to0.10078\to0.08183\) across \(N=3,4,5\).
- Fixed Chern numbers \(C_1=6,10\) with reproducibly shifted Wilson statistics.
- Exact rank sequence through \(D=800\), including 120 atoms at each boundary and connected plateau `0.7`.
- Seven synchronized publication figures and an audited 17-page article.

## Deliverables

- [Harness solution overview](https://github.com/JunkaiWang-TheoPhy/quantum.harness/blob/codex/issue-276-quantum-geometry/tracks/mps/solutions/Wander-276/README.md)
- [Innovation-first research guide](https://github.com/JunkaiWang-TheoPhy/quantum.harness/blob/codex/issue-276-quantum-geometry/tracks/mps/solutions/Wander-276/research/README.md)
- [Markdown technical report](https://github.com/JunkaiWang-TheoPhy/quantum.harness/blob/codex/issue-276-quantum-geometry/tracks/mps/solutions/Wander-276/research/docs/2026-07-30-task05-technical-report.md)
- [17-page article](https://github.com/JunkaiWang-TheoPhy/quantum.harness/blob/codex/issue-276-quantum-geometry/tracks/mps/solutions/Wander-276/research/01_task_folder/task_05/script/output/spectral_silence_and_geometric_chaos_v3.pdf)
- [Release manifest](https://github.com/JunkaiWang-TheoPhy/quantum.harness/blob/codex/issue-276-quantum-geometry/tracks/mps/solutions/Wander-276/research/01_task_folder/task_05/script/output/release_manifest_v1.json)
- [Public research repository](https://github.com/JunkaiWang-TheoPhy/Chaos-of-Quantum-Geometry/tree/codex/task-05-geometric-chaos-baseline)

## Verification

```bash
cd tracks/mps/solutions/Wander-276
bash verify.sh
```

- Release contract: 17/17 checks.
- Quick path: 38/38 tests.
- Complete compact suite: 86 passing tests plus six manifest-activated production tests.
- Article delivery: 25/25 checks across 17 pages and seven figures.
- Article SHA-256: `a75377f76acd78eb3354e186a57933abdf11abbbe5e9a8abd43482ca8c4e05ad`.

## MPS Track Continuation

The exact-kernel calculation supplies the calibration layer for an MPS extension of Issue #276: reproduce the projector response and four-channel invariant at ED-accessible sizes, then scale the same gauge-invariant observables with a tensor-network representation of the degenerate manifold. The next registered targets are \(N=6\), a second exact-degeneracy mechanism, and a locality-based derivation of the connected channel law.

@OkongOyangO, please review the projector-geometry interpretation, the four-channel law, and the fixed-Chern holonomy construction as Wander's ready submission for #276.
