# Wander — Issue #276: Exactly Degenerate Quantum Chaos and Geometric Response

![Quantum geometry over an exactly degenerate manifold](https://raw.githubusercontent.com/JunkaiWang-TheoPhy/quantum.harness/664506886413b68cdbc5a362a6075c78fd5d2c46/docs/showcase/ranger-archive/assets/missions-v2/07-quantum-geometry-curved-state-space-v2.png)

> The spectrum is silent; the geometry is not.

## Team

| Field | Value |
|---|---|
| **Team name** | Wander |
| **Members** | Chenxi Wan, Yedi Shen, Junkai Wang |
| **Contact email** | WangTheoPhys@outlook.com |

## Question and answer

This submission addresses [QuantumBFS/quantum.harness#276](https://github.com/QuantumBFS/quantum.harness/issues/276): what can probe quantum chaos inside an exactly degenerate eigenspace?

Let $P(\lambda)$ be a gapped, exactly degenerate projector, $Q=1-P$, and

$$X_a=Q\,\partial_aP\,P.$$

The matrix-valued quantum geometric tensor

$$\mathcal Q_{ab}=X_a^\dagger X_b$$

gives the metric $g_{ab}=(\mathcal Q_{ab}+\mathcal Q_{ba})/2$ and the non-Abelian Berry curvature $F_{ab}=i(\mathcal Q_{ab}-\mathcal Q_{ba})$. These quantities measure how the protected fiber moves through Hilbert space. They remain defined when every intrafiber energy is identical and ordinary level statistics is silent.

The submission does not identify geometric randomness with chaos by definition. It separates three questions: whether the spectrum is exactly degenerate, whether the projector moves, and whether its gauge-invariant geometric correlations obey a random closure.

## Two-paper result

| Paper | Delivered result | Registered boundary |
|---|---|---|
| **I. _Exactly Degenerate Quantum Chaos: Non-Abelian Quantum Geometry as a Probe_** | A 23-page PRB-style article and 11-page supplement compare Laughlin/FCI parents, Moore–Read clustering, cubic $\mathcal N=2$ SYK cohomology, local lattice supersymmetry, and X-cube controls using one projector-response formalism. | Finite size and mechanism resolved. The centered complete-covariance gate passes only for Moore–Read $N=6$ among the five registered Moore–Read/lattice-SUSY cases. No independent Hamiltonian ensemble or asymptotic scaling law is established. |
| **II. _Geometric Response of Exactly Degenerate Quantum State Bundles_** | An 18-page article and 8-page supplement prove an exact weighted-channel fourth-cumulant identity under explicit assumptions, then test its $N_{\mathrm{eff}}$ specialization with a sealed chiral-index calculation. | The prospective random-channel closure fails. The positive title _The Geometric ETH_ is therefore rejected; the result shows that $N_{\mathrm{eff}}$ alone is insufficient for the registered ensemble. |

Paper I retains the positive operational content of “Geometric ETH”: quantum geometry can carry statistical information under exact degeneracy. Paper II supplies the distinction that the name requires. An exact channel theorem does not imply a universal physical law unless independence, comparable standardized cumulants, and the registered tangent closure survive in the model under study.

## Mechanisms and controls

| Mechanism | Origin of exact degeneracy | Geometric role |
|---|---|---|
| Kapit–Mueller/Laughlin parent | Positive-semidefinite clustering constraints annihilate a zero-mode manifold | Gapped topological parent with stochastic local geometry and fixed-Chern holonomy |
| Moore–Read parent | Three-body clustering constraints | Higher-rank non-Abelian zero modes; the sole positive centered full-$R_4$ case is the registered $N=6$ calculation |
| Cubic $\mathcal N=2$ SYK | Harmonic representatives of supercharge cohomology | Exact/exact-coexact response channels and a sealed rejection of separable covariance nulls |
| Lattice $\mathcal N=2$ SUSY | Independence-complex cohomology | Local, non-FQH cohomological comparison with ranks $2,4,8$; none passes the registered centered gate |
| Periodic X-cube | Commuting stabilizer constraints | Exact counterexample: coefficient changes give $F=0$, while an isospectral orbit gives scalar $F=-I/2$ and zero connected curvature variance |

## Prospective Paper II test

The calculation freezes its estimator, bootstrap, simultaneous development band, control rule, branch rule, and title rule before opening the validation result. For the three registered sizes, the random-channel values are

$$1.2903355,\quad 1.3649631,\quad 1.4814450,$$

all above the frozen simultaneous band

$$[0.4476289,\,1.2352060].$$

The selected branch is `random_channel_failure`. This rejects the combined finite-size specialization; it does not separately determine whether the failure comes from channel dependence, noncomparable channel cumulants, weight–cumulant correlations, finite-rank geometry, or the chosen tangent population.

## Delivered artifacts

- [Paper I main PDF](research/01_task_folder/task_05/script/output/paper1_prb_v13/exactly_degenerate_quantum_chaos_v13.pdf) and [Supplement](research/01_task_folder/task_05/script/output/paper1_prb_v13/exactly_degenerate_quantum_chaos_supplement_v13.pdf)
- [Paper II main PDF](research/01_task_folder/task_05/script/output/geometric_eth_theory_v14/geometric_response_exactly_degenerate_bundles_v14.pdf) and [Supplement](research/01_task_folder/task_05/script/output/geometric_eth_theory_v14/geometric_response_exactly_degenerate_bundles_supplement_v14.pdf)
- [Combined fail-closed manifest](research/01_task_folder/task_05/script/output/two_paper_delivery_v14/two_paper_manifest_v14.json)
- [Reviewer guide](research/docs/2026-08-21-two-paper-reviewer-guide.md)
- [Reproducibility guide](research/docs/2026-08-21-two-paper-reproducibility.md)
- [Submission checklist](research/docs/2026-08-21-two-paper-submission-checklist.md)

The archived main-PDF SHA-256 values are:

- Paper I: `257b1c10e75f7104d4a70afbd3b9c9056e197036a5f4c216f3789af8c513746a`
- Paper II: `45984eed2daa8df1c741a5924287664a3c0b9508389be8681232a91ed54c0d20`

## Verification

From the Quantum Harness repository root:

```bash
bash tracks/mps/solutions/Wander-276/verify.sh
```

The command preserves the v1–v12 checks, runs the Paper I v13 and Paper II v14 test suites, rebuilds the combined audit from frozen evidence, and validates 71 registered v13/v14 source/artifact hashes. One source-repository-only v13 test is intentionally excluded because the historical research-repository Git object is not part of the Harness repository. A [capsule-local SHA-256 manifest](v1_v12_seal_manifest.json) instead freezes all 237 v1–v12 versioned artifacts that were present in the pre-upgrade Wander-276 capsule.

## Claim boundary

Established here: exact-degeneracy mechanisms with informative projector geometry; finite-size, mechanism-dependent geometric statistics; an exact conditional channel-cumulant theorem; and exact controls showing that projector motion alone does not imply chaos.

Not established here: asymptotic or universal Geometric ETH, an independent cross-model ensemble, conventional energy-resolved ETH, thermalization, Lyapunov behavior, real-time chaos, or a black-hole theorem.
