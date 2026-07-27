# Autoresearch Topic Candidates

Project: YueYuan challenge #113, "Sim-to-Real for Quantum Gates"

Stage: topic selection. No topic or acceptance gate is confirmed yet.

## Domain

Differentiable quantum optimal control for gate calibration, using a cheap model to extract Hessian-sensitive control directions and a noisy query-only "true device" to test closed-loop calibration cost.

## Grounding References

- Genyue Liu et al., "High-fidelity neutral atom gates leveraging low-rank Hessian optimization," arXiv:2606.05060, 2026. https://arxiv.org/abs/2606.05060
- D. J. Egger and F. K. Wilhelm, "Adaptive Hybrid Optimal Quantum Control for Imprecisely Characterized Systems," PRL 112, 240503, 2014. https://arxiv.org/abs/1402.7193
- J. Roslund and H. Rabitz, "Dynamic Dimensionality Identification for Quantum Control," PRL 112, 143001, 2014. https://doi.org/10.1103/PhysRevLett.112.143001
- Z. Shen, M. Hsieh, and H. Rabitz, "Quantum Optimal Control: Hessian Analysis of the Control Landscape," J. Chem. Phys. 124, 204106, 2006. https://pubmed.ncbi.nlm.nih.gov/16774318/
- Mogens Dalgaard et al., "Hessian-based optimization of constrained quantum control," PRA 102, 042612, 2020. https://arxiv.org/abs/2006.00935
- A. G. R. Day et al., "Glassy Phase of Optimal Quantum Control," PRL 122, 020601, 2019. https://arxiv.org/abs/1803.10856
- M. Larocca et al., "Theory of overparametrization in quantum neural networks," Nature Computational Science 3, 542-551, 2023. https://doi.org/10.1038/s43588-023-00467-6
- JAX autodiff cookbook, Hessian-vector products and forward-over-reverse autodiff. https://jax.readthedocs.io/en/latest/notebooks/autodiff_cookbook.html

## Candidate Table

Scores: 1 = poor, 5 = strong. "Cheap" means one scored attempt can run locally in minutes.

| Candidate | Checkable | Cheap | Headroom | Publishable | Riskiest assumption |
|---|---:|---:|---:|---:|---|
| A. Minimal Hessian-subspace calibration demo | 5 | 5 | 4 | 3 | The model Hessian's top directions still improve noisy black-box search after realistic model-device perturbations. |
| B. Failure boundary versus model-truth gap | 5 | 4 | 5 | 4 | A simple perturbation parameter epsilon produces a meaningful subspace-rotation failure mode rather than an artifact of the toy simulator. |
| C. Shot-noise and optimizer comparison | 5 | 4 | 4 | 3 | Query-count differences will reflect intrinsic dimension reduction, not arbitrary optimizer hyperparameter tuning. |
| D. d^2 - 1 invariant across system sizes | 4 | 3 | 4 | 4 | Single- and two-qubit toy systems are controllable and over-resourced enough that the predicted rank is visible, while three-qubit tests may be too expensive. |
| E. Adaptive subspace re-estimation from device data | 4 | 3 | 5 | 5 | A device-data subspace update can be estimated with fewer extra queries than the fixed-subspace method saves. |

## Recommendation

Start with **A. Minimal Hessian-subspace calibration demo**.

Reason: it is the smallest machine-checkable claim behind issue #113. It can produce the first PR result quickly: a query-count comparison between full-parameter closed-loop optimization and reduced Hessian-coordinate optimization on a simulated query-only device.

Then extend in order:

1. B: sweep model-truth gap epsilon to find when A fails.
2. C: add finite-shot noise and compare optimizers.
3. D: check d^2 - 1 across d = 2 and d = 4.
4. E: attempt adaptive subspace repair only if fixed-subspace failure is clear.

## Draft Metrics For Candidate A

These are proposed, not confirmed.

- **Queries to target** (primary): median number of true-device black-box fidelity queries required to reach true infidelity <= 1e-3; compute over at least 5 random seeds for each method and subspace dimension k.
- **Total shots to target** (primary or co-primary): number of true-device queries multiplied by shots per fidelity estimate; same stopping threshold.
- **Final true infidelity** (guard): final noiseless true-device infidelity must be <= 1e-3 for a reported success, so a noisy lucky estimate cannot count.
- **Model-device boundary** (guard): closed-loop code may call only the scalar noisy device oracle and may not differentiate through, inspect, or reuse true-device internals.
- **Baseline fairness** (guard): full-parameter and Hessian-subspace optimizers must share the same initial pulse, query budget, shot budget, stopping threshold, random seeds, and optimizer family where possible.

## Draft Acceptance Gate For Candidate A

Not user-confirmed yet.

A solid first research output would be:

> On a simulated two-qubit gate with at least one fixed nonzero model-truth perturbation and finite-shot fidelity noise, Hessian-subspace closed-loop search reaches noiseless true infidelity <= 1e-3 with at least 2x fewer median true-device queries than full-parameter search over at least 5 seeds, while passing the guard checks above. The report must include query count versus k and identify at least one k that succeeds and one too-small k that fails or plateaus.

## Gate Red Team

Potential hacks and planned closures:

- **Lucky noisy fidelity**: a method appears to hit target due to finite-shot noise. Closed by re-evaluating the final pulse with a high-shot or noiseless true fidelity guard.
- **Weak baseline**: full search is implemented badly, inflating the apparent advantage. Closed by using the same derivative-free optimizer family and tuned comparable budgets for both methods, plus reporting a random-subspace baseline.
- **Leaking true model**: the reduced search accidentally uses true-device gradients or internals. Closed by a strict oracle interface and tests that true-device parameters are private to the oracle.
- **Cherry-picked k**: only the best subspace dimension is reported. Closed by sweeping k values including 0, 3, 8, 15, 24, and full parameter dimension.
- **One-seed anecdote**: the result is not stable. Closed by reporting median and spread over at least 5 seeds.
- **Toy gap too easy**: epsilon is so small that any warm start works. Closed by including at least two perturbation sizes and showing where the advantage weakens.
