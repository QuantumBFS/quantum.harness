## Team

| | |
|---|---|
| **Team name** | JOE |
| **Members** | Bei Qiao (乔北), Institute of Physics, Chinese Academy of Sciences (IOP) |

## Challenges

| Row | |
|---|---|
| **Challenge A** | Addresses #15 — construct an exchange-antisymmetric, SO(3)-equivariant neural quantum state for the ν = 1/3 chiral graviton and compute the gap Δ = E(L=2) − E(L=0). |
| **Challenge B** | Addresses #121 — search for new physically realizable matrix classes with provably nonnegative determinantal-QMC weights. |
| **Relationship** | These are two independent research workstreams pursued by the same team. They share the `qmc` track and this registration PR, but no scientific dependence between them is claimed. |
| **Proposer** | Both challenges were released by Lei Wang, Institute of Physics, Chinese Academy of Sciences. |
| **Track** | `qmc` — #15 uses Variational Monte Carlo / Neural Quantum States; #121 concerns sign-problem-free Quantum Monte Carlo. |

## Working repository

The two workstreams are maintained separately in the team repository:

- Repository: https://github.com/Joe-Nor/JOE-Harnessing-Quantum-2026
- Live work branch:
  https://github.com/Joe-Nor/JOE-Harnessing-Quantum-2026/tree/agent/majorana-semigroup-detailed-proof

## Interim submission — 2026-07-30

This is a reviewable intermediate snapshot, not a claim that both challenges
are complete. The registration PR is ready for interim review, and later
results may be added to this same PR before the final deadline.

| Workstream | Current status | What remains open |
|---|---|---|
| Required paper reproduction | Reproducible CPMC package completed at this snapshot; 19 tests passed. | The package reproduces the selected Figure 4(a) target, not every result in the paper. |
| Challenge #15 | The strict antisymmetric, LLL-preserving, \(SO(3)\)-equivariant construction and an \(N=4\) ED/VMC validation loop are complete. | Thermodynamic-limit extrapolation, helicity separation, and production large-\(N\) training remain open. |
| Challenge #121 | A local \(PGL(2,7)\) HS identity with 49 non-identity Gaussian fields plus the identity term has an exact proof and exhaustive finite-group validation. | Active hopping has exact negative-weight counterexamples, so a new sign-free propagating lattice model has not yet been obtained. |

The immutable source snapshot is
[`e98148a54b35`](https://github.com/Joe-Nor/JOE-Harnessing-Quantum-2026/tree/e98148a54b35b9bdb7ad0b2672f027790a0f1603).
It contains all three deliverables:

1. **Required QMC paper reproduction — CPMC-Lab**
   - [Reproduction report and commands](https://github.com/Joe-Nor/JOE-Harnessing-Quantum-2026/tree/e98148a54b35b9bdb7ad0b2672f027790a0f1603/reproductions/qmc-cpmc-lab)
   - Independent Python CPMC, exact-diagonalization references, the paper's
     16-site Figure 4(a) calculation, convergence scans, and an unmodified
     official MATLAB-package cross-check.
   - Revalidated at this snapshot: 19 tests passed.

2. **Challenge #15 — chiral-graviton NQS**
   - [Human-readable reviewer guide](https://github.com/Joe-Nor/JOE-Harnessing-Quantum-2026/blob/e98148a54b35b9bdb7ad0b2672f027790a0f1603/challenges/15-chiral-graviton/REVIEWER_GUIDE.md)
   - [Reproduction guide](https://github.com/Joe-Nor/JOE-Harnessing-Quantum-2026/blob/e98148a54b35b9bdb7ad0b2672f027790a0f1603/challenges/15-chiral-graviton/REPRODUCIBILITY.md)
   - Strict antisymmetry, LLL degree, and \(SO(3)\) equivariance; finite-size
     ED and VMC; symmetry, Fock-oracle, and operator-span validation.
   - Revalidated at this snapshot: 84 project tests and 61 independent
     Stage-1 Fock-oracle tests passed.

3. **Challenge #121 — sign-free hunter**
   - [Human-readable results overview](https://github.com/Joe-Nor/JOE-Harnessing-Quantum-2026/blob/e98148a54b35b9bdb7ad0b2672f027790a0f1603/challenges/121-sign-free-hunter/RESULTS_OVERVIEW.md)
   - [Reproduction guide](https://github.com/Joe-Nor/JOE-Harnessing-Quantum-2026/blob/e98148a54b35b9bdb7ad0b2672f027790a0f1603/challenges/121-sign-free-hunter/REPRODUCIBILITY.md)
   - The current flagship result is a proved local discrete \(PGL(2,7)\)
     Hubbard--Stratonovich identity. Exact hopping counterexamples are
     included, so this snapshot does not claim a completed sign-free lattice
     model.

Large-system and thermodynamic-limit claims remain open in both challenges.
Those limitations are stated explicitly in the linked reviewer documents.
