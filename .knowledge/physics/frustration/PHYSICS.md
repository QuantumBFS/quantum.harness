# Frustration

Diagnose frustration in a specific model: identify its source, what it costs computationally, and how it constrains method choice.

## Diagnose

Infer the diagnostic framing from the user's prompt and propose it for ratification.

**Canonical framing:** "You're asking about frustration in [model on lattice]. I'll classify the source (geometric / interaction / fermionic / boundary-induced), assess method constraints (sign problem, DMRG geometry bias), and recommend what's computable."

Do not ask 4 questions. Propose the framing; let the user correct if wrong.

## Evidence to gather

- **Classical degeneracy**: count the classical ground-state manifold for the model on the given lattice. Macroscopic degeneracy → strong geometric frustration (e.g., kagome, pyrochlore Heisenberg).
- **Sign problem indicator**: for Hubbard / t-V, attempt to identify a Marshall sign / bipartite-decomposition argument. If none exists, QMC has a sign problem.
- **DMRG cylinder convergence**: bond dimension required to converge grows much faster on frustrated lattices; document.
- **Order-parameter competition**: compute structure factors at multiple candidate ordering wavevectors. Multiple comparable peaks → competition.
- **Variational ansatz sensitivity**: in literature, several distinct ansatzes (different SL types, VBS, ordered) give close-by energies → strong frustration / contested ground state.

## Cross-checks

| Competing explanation | Test that rules it out |
|---|---|
| "Just hard," not frustrated | Show a specific source of degeneracy or sign problem; without one, the difficulty may be size or accuracy, not frustration. |
| Geometric vs interaction frustration | Set non-geometric couplings to default values; does the frustration persist? |
| Boundary / finite-size artifact | Run multiple boundary conditions; if frustration vanishes with PBC vs OBC, it was finite-size. |

## Interpretation rules

- Frustration is a *diagnosis*, not a method recommendation. Once classified, route to the method appropriate for the regime.
- For QMC sign problems: do not promise sign-free QMC without explicit verification of the sign condition for the specific Hamiltonian and basis.
- For DMRG on frustrated 2D: cylinder geometry biases the answer; report multiple geometries when possible.
- A frustrated ground state is not automatically a spin liquid — also call `spin-liquid` for that hypothesis.

## Method-choice implications

| Frustration source | Implication |
|---|---|
| Geometric (triangular, kagome, pyrochlore) | DMRG cylinder + ED; QMC blocked. VMC/NQS via NetKet for variational comparison (`skills/method-vmc/SKILL.md`). |
| Interaction (J1-J2 near `0.5`) | DMRG with multiple geometries + ED on small clusters; literature debate active. |
| Fermionic sign | Constrained-path AFQMC (with bias discussion) or variational routes. |
| Boundary-induced | Compare PBC and OBC; if frustration only at OBC, it's not intrinsic. |

## Model hooks

`heisenberg` (triangular, kagome, pyrochlore), `j1-j2`, `t-v`, `hubbard` (with `t'`), `t-j`. Common downstream call: `spin-liquid` when the question is about an exotic non-magnetic ground state; `criticality` when frustration tunes a transition.
