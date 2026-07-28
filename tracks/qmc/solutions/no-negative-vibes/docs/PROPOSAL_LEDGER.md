# Proposal ledger

Updated: 2026-07-28

This file is the index of research claims on `work/zibo/representation-cones`.
Every substantive new direction receives an ID and a candidate card before
computation. Status changes must cite a commit, protocol, experiment ID, or
exact certificate.

| ID | Proposal | Owner | Falsifiable prediction | Initial status | Card |
|---|---|---|---|---|---|
| R01 | Overlapping Klein/Fock circuit cone | Zibo | A six-mode two-plaquette global transform admits a cross-cluster quadratic BdG cone with two noncommuting rays | `claimed-design` | [R01](candidates/R01_OVERLAPPING_KLEIN_FOCK.md) |
| R02 | Klein–Spinor positive local HS cone | Zibo | A four-mode interacting target gate has a positive branch/Gram decomposition on a finite small-time interval | `claimed-design` | [R02](candidates/R02_KLEIN_SPINOR_HS.md) |
| R03 | Branch-safe `D4` triality cone | Zibo | Simultaneous vector/half-spin positivity gives branch information not exhausted by known split `SO(4,4)` | `claimed-design` | [R03](candidates/R03_D4_TRIALITY.md) |

## Status vocabulary

- `claimed-design`: hypothesis and stopping rule are committed, no experiment;
- `running`: a versioned protocol has started;
- `falsified`: exact counterexample or exact infeasibility certificate;
- `known-reduction`: proved equivalent to a known sign-free mechanism;
- `numerical-survivor`: bounded scan has no counterexample;
- `proof-candidate`: arbitrary-depth proof route is explicit;
- `physical-candidate`: positive local HS mapping is explicit;
- `challenge-ready`: novelty, proof, physical mapping, and reproduction close.

## Change rule

Do not delete failed proposals. Mark their terminal status, link the evidence,
and summarize the transferable lesson in `EXPERIMENT_LOG.md`. Reserve
directions from the design require a new row and card before implementation.
