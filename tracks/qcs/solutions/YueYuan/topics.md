# Autoresearch Topic

## Minimal Hessian-Subspace Calibration Demo

### Problem Statement

Build a reproducible software black-box version of challenge #113: use a differentiable quantum-control model to find a target-gate pulse and extract Hessian principal directions at the model optimum; then treat a perturbed "true device" as a noisy query-only oracle and compare closed-loop calibration in the Hessian subspace against full-parameter search.

### Why Autoresearch Fits

| Criterion | Score | Reason |
|---|---:|---|
| Checkable | 5 | A validator can compute query counts, shot counts, final noiseless true infidelity, and boundary-violation checks without human judgment. |
| Cheap | 5 | A one- or two-qubit exact-propagator benchmark with short pulse vectors should run in minutes locally; larger sweeps can move to HPC. |
| Headroom | 4 | Many attempt variants exist: optimizer family, k schedule, random subspace baseline, perturbation family, shot budget, safety-margin directions, and adaptive subspace repair. |
| Publishable | 3 | The minimal demo is a credible first workshop result; publishability improves if the failure boundary and adaptive repair are added. |

### Key References

- Genyue Liu et al., "High-fidelity neutral atom gates leveraging low-rank Hessian optimization," arXiv:2606.05060.
- D. J. Egger and F. K. Wilhelm, "Adaptive Hybrid Optimal Quantum Control for Imprecisely Characterized Systems," Phys. Rev. Lett. 112, 240503 (2014), arXiv:1402.7193.
- J. Roslund and H. Rabitz, "Dynamic Dimensionality Identification for Quantum Control," Phys. Rev. Lett. 112, 143001 (2014), DOI: 10.1103/PhysRevLett.112.143001.
- Z. Shen, M. Hsieh, and H. Rabitz, "Quantum Optimal Control: Hessian Analysis of the Control Landscape," J. Chem. Phys. 124, 204106 (2006), DOI: 10.1063/1.2198836.
- Mogens Dalgaard et al., "Hessian-based optimization of constrained quantum control," Phys. Rev. A 102, 042612 (2020), arXiv:2006.00935.
- A. G. R. Day et al., "Glassy Phase of Optimal Quantum Control," Phys. Rev. Lett. 122, 020601 (2019), arXiv:1803.10856.
- M. Larocca et al., "Theory of overparametrization in quantum neural networks," Nat. Comput. Sci. 3, 542-551 (2023), DOI: 10.1038/s43588-023-00467-6.

### Metrics

- **Queries to target** (primary): median number of true-device oracle calls needed to reach noiseless true infidelity <= 1e-3; computed over at least 5 random seeds per method and subspace dimension. Cost: minutes for the local two-qubit benchmark. Gaming risks: a noisy estimate can falsely pass; close with a noiseless/high-shot final-fidelity guard.
- **Total shots to target** (primary): oracle calls multiplied by shots per fidelity estimate, using the same stopping threshold. Cost: bookkeeping only once query traces exist. Gaming risks: uneven shot budgets can bias the comparison; close by fixing shot budget per query across compared methods.
- **Final true infidelity** (guard): final candidate pulse must satisfy noiseless true-device infidelity <= 1e-3. Cost: one exact simulator call per reported winner. Gaming risks: using the model fidelity instead of the true-device fidelity; close by making the validator call the private true-device evaluator.
- **Model-device boundary** (guard): closed-loop optimizers may call only a scalar noisy oracle and may not inspect true-device Hamiltonian perturbations or gradients. Cost: static interface check plus runtime query log. Gaming risks: leakage through imports or saved globals; close with a minimal oracle class and tests that attempts cannot access private fields.
- **Baseline fairness** (guard): full search, random-subspace search, and Hessian-subspace search share the same initial pulse, query budget, stopping rule, seeds, and optimizer family where possible. Cost: validator reads run manifests. Gaming risks: intentionally weak baseline; close by requiring a random-subspace control and identical outer optimizer settings.

### Acceptance Gate

User authorization: on 2026-07-27, YueYuan asked Codex to "start automatic research" and set the goal "Use Karpathy's autoresearch scheme to deal with the 113rd challenge." We treat that as approval to start from the recommended topic and this first strict gate.

A solid first research output counts as achieved when:

> On a simulated two-qubit gate with at least one fixed nonzero model-truth perturbation and finite-shot fidelity noise, Hessian-subspace closed-loop search reaches noiseless true infidelity <= 1e-3 with at least 2x fewer median true-device queries than full-parameter search over at least 5 seeds, while passing the guard metrics above. The report must include query count versus k and identify at least one k that succeeds and one too-small k that fails or plateaus.

Red-team closures:

- **Lucky noisy fidelity** — closed by re-evaluating final pulses with noiseless or high-shot true fidelity.
- **Weak full-parameter baseline** — closed by matching optimizer family/settings and including a random-subspace baseline.
- **True-device leakage** — closed by a strict scalar oracle interface and tests that the closed-loop code cannot inspect private true-device parameters.
- **Cherry-picked k** — closed by sweeping k values including 0, 3, 8, 15, 24, and full parameter dimension when the pulse dimension permits.
- **One-seed anecdote** — closed by median and spread over at least 5 seeds.
- **Too-easy model gap** — closed by including at least two perturbation sizes and reporting when the fixed model subspace loses advantage.
