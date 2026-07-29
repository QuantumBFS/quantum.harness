# Oddcycle completion audit for Challenge #121

Audit target: [Quantum Harness issue #121, “Sign-problem free hunter”](https://github.com/QuantumBFS/quantum.harness/issues/121).

This document audits the oddcycle result against the issue objectives and
verification plan.  It does not use “the theorem is proved” as a synonym for
“the challenge is complete.”

## Status vocabulary

- **proven**: the requirement has exact or theorem-backed evidence in the
  repository and a focused replay path.
- **partial**: material evidence exists, but at least one stated acceptance
  condition is still open.
- **missing**: no deliverable currently closes the requirement.

## Executive verdict

**Overall status: partial.**

The mathematical core is complete: a genuine continuum alphabet of
independently chosen matrices is proved strictly sign-free at every product
depth.  A fixed member also has an exact positive-coefficient auxiliary-field
realization as a Hermitian, number-conserving, interacting five-mode transfer.

The two challenge-level blockers are:

1. the novelty filter is not complete against the full Wei-2024/Majorana
   conditions and possible known fermion-bag or loop equivalences;
2. there is no public-endgame manuscript, MathOverflow draft, or arXiv note.

A connected-lattice or simple local two-body realization would materially
strengthen the physics, but the repository already contains a minimal
interacting cluster realization.

## Requirement-by-requirement audit

| Challenge requirement | Status | Current evidence | What remains |
|---|---|---|---|
| Determinant oracle with correct product order and stable sign classification | **proven** | `oracle/weights.py`; `tests/test_weights.py` checks factor order, positive/negative/zero controls, conditioning, and overflow | Nothing for the base oracle |
| Split-orthogonal theorem anchors, including the other components of \(O(n,n)\) as negative/zero controls | **proven** | `fixtures/exact_certificates.json`; `tests/test_exact_fixtures.py`; `tests/test_weights.py`; the \(O(1,1)\) values are explained in `docs/FOUNDATIONS.md` | A formal proof assistant version is optional, not required for the present result |
| Semigroup-cone positive controls | **proven** | `tests/test_frontier_candidates.py` samples known split/factorization semigroups; `tests/test_az_semigroup_cones.py` checks structural residuals and known positive BDI/AII/CII controls; `docs/FOUNDATIONS.md` records the theorem | These validate the harness; they are not a new theorem claim |
| State-of-the-art map: split orthogonal, Kramers, Majorana, semigroup, pseudo-unitary, and AZ prior art | **proven** | `docs/FOUNDATIONS.md`, `docs/AZ_TENFOLD_RESULTS.md`, `docs/ORGANIZER_DIRECTION_AUDIT.md`, and `docs/LITERATURE_GAP_2026.md` | Keep citations current during paper writing |
| Written reduction checklist for candidate novelty | **proven** at project level | `docs/CANDIDATE_CARD.md` explicitly checks split, Majorana, Kramers, contraction semigroups, flavor doubling, pseudo-unitary phase mechanisms, and physical DQMC origin | The checklist still has unresolved entries for this particular oddcycle family; see the novelty row below |
| A precisely defined structured generator set | **proven** | `docs/SYMMETRIC_ODDCYCLE_INTERVAL_FAMILY.md` defines \(\mathcal A_I=\{B(z),B(z)^{\mathsf T}:99/100\le z\le101/100\}\), with \(z\) chosen independently at every time slice | Nothing for the definition |
| Strict positivity for arbitrary depth | **proven** | `oracle/symmetric_oddcycle_interval_family.py` and `tests/test_symmetric_oddcycle_interval_family.py`; exact finite-depth interval enumeration covers 8,190 nonempty words through depth 12, and exact block/norm tails cover every larger depth | Nothing for the stated interval theorem |
| Human-readable proof, not only numerical survival | **proven** | `docs/SYMMETRIC_ODDCYCLE_INTERVAL_FAMILY.md` gives the finite-depth, grade-\((3,4)\), and low-sector arguments; `docs/SYMMETRIC_ODDCYCLE_CONES.md` gives the fixed-point proof and intermediate exact lemmas | A paper-quality reorganization is still needed for publication |
| Massive randomized survival protocol with dimensions, depths, seeds, and sample counts | **partial** | The project has documented large baseline protocols, including `protocols/classical-groups-v1/` and `protocols/frontier-semigroups-v1/`; the oddcycle route has stronger exact enumeration and an all-depth theorem | There is no clean, dedicated oddcycle randomized protocol/report.  Exact proof removes scientific dependence on such a scan, but issue #121 explicitly asks for the sampling protocol to ship with the claim |
| Exact physical DQMC weight for a fixed oddcycle member | **proven** | `oracle/symmetric_oddcycle_physical.py`, `tests/test_symmetric_oddcycle_physical.py`, and `docs/SYMMETRIC_ODDCYCLE_PHYSICAL.md` prove \(\operatorname{Tr}_{\mathcal F}\Gamma(W)=\det(I+W)\), \(T=19I+\Gamma(B)+\Gamma(B)^{\mathsf T}\succ0\), and \(H=-\log(T/21)\) Hermitian | The construction is a five-mode cluster and is not claimed local |
| Nonnegative Hubbard–Stratonovich/auxiliary-field prefactor | **proven** | The normalized three-field coefficients are exactly \((19,1,1)/21\); identity letters delete from determinant words, so every configuration has a positive scalar prefactor times a strictly positive determinant | Nothing for the fixed transfer |
| The auxiliary matrices are exponentials of bilinears | **proven** | The exact characteristic-polynomial gate excludes the nonpositive real axis, so the real principal \(A=\operatorname{Log}B\) exists and \(\Gamma(B)=e^{d\Gamma(A)}\); transpose compatibility supplies \(A^{\mathsf T}\) | Individual auxiliary propagators are non-Hermitian; the paired transfer and resulting \(H\) are Hermitian |
| The physical Hamiltonian is genuinely interacting | **proven** | The exact Gaussian consistency condition fails: \(T_0T_2-\wedge^2T_1\) has 58 nonzero entries and first entry 42 | An explicit normal-ordered coupling table is useful for a paper but not needed to prove non-Gaussianity |
| Physical realization of the complete continuum alphabet | **partial** | `docs/SYMMETRIC_ODDCYCLE_INTERVAL_FAMILY.md` proves every \(B(z)\) has a real logarithm and points to the transpose-paired inverse construction | No single exact uniform \(c\), normalized field measure, and interacting-transfer certificate has yet been frozen for all \(z\in I\) |
| A natural connected-lattice or local two-body model | **missing** | The fixed construction defines a valid interacting five-mode cluster model | Supply a connected-lattice embedding with an all-word alphabet theorem, or state clearly in the paper that the result is a cluster realization |
| Grand-canonical versus fixed-filling scope | **proven limitation** | `docs/SYMMETRIC_ODDCYCLE_PHYSICAL.md` states that the theorem is for the full Fock trace; fixed-particle traces can be negative | Do not claim canonical, fixed-filling, arbitrary chemical-potential, or doped-lattice sign freedom without a new theorem |
| Exclusion of fixed split-orthogonal and standard one-particle Kramers mechanisms | **proven** | `oracle/oddcycle_novelty_filter.py`, `tests/test_oddcycle_novelty_filter.py`, and `docs/ODDCYCLE_NOVELTY_FILTER.md`: \(\det B=8\), invariant-bilinear nullity zero, odd dimension, and scalar common commutant | Nothing for these two mechanisms |
| Exclusion of obvious block, diagonal-gauge, and totally-nonnegative reductions | **proven** | The generated algebra has rank 25, a negative directed cycle product survives diagonal gauges, and \(B\) has nonreal spectrum | Nothing for the listed reductions |
| Exclusion of the full Wei-2024 contraction/Majorana mechanisms and known physical equivalents | **partial** | `docs/ODDCYCLE_NOVELTY_FILTER.md` lists the exact exclusions already obtained | Still required: the 10-Majorana lift, fixed complex-basis Majorana reflection positivity, the full Wei-2024 inequalities, irreducible cone-preserving equivalences, and a focused literature-equivalence audit |
| Full reporting: generator, dimensions, depths, counts, exact verifier, rerun instructions | **partial** | Definitions, exact counts, witness margins, code, and focused tests are present in the three oddcycle documents and their oracle/tests | Add one versioned oddcycle protocol or one-command replay that emits a machine-readable summary; record runtime/software provenance; link it from the entry page |
| Public endgame: MathOverflow or arXiv-ready manuscript | **missing** | The theorem, physical construction, and novelty notes provide source material | Write the paper/MO draft, complete references, separate theorem from computational certificate, and obtain collaborator review |

## What can be claimed now

The repository can already support the following statement:

> The independently varying continuum alphabet
> \(\mathcal A_I=\{B(z),B(z)^{\mathsf T}:z\in[0.99,1.01]\}\) has
> \(\det(I+W)>0\) for every finite word.  At \(z=1\), the theorem gives an
> exact three-valued positive auxiliary-field decomposition of a Hermitian,
> number-conserving, interacting five-mode transfer.

It should **not** yet be advertised as a new class beyond all known
Majorana/semigroup mechanisms.  That sentence depends on the unresolved
novelty checks above.

## Minimum closure plan

1. **Novelty blocker.**  Perform the 10-Majorana generator-level audit against
   Majorana reflection positivity and the full Wei-2024 contraction
   inequalities, including fixed complex orthogonal basis changes.
2. **Reproducibility bundle.**  Add one command that runs the four focused
   suites—baseline controls, interval theorem, physical transfer, and novelty
   filter—and writes one machine-readable summary with commit and runtime.
3. **Paper.**  Draft a short note organized as: continuum-alphabet theorem;
   exact computer-assisted lemmas; positive auxiliary-field realization;
   novelty audit; limitations.
4. **Physics strengthening, if feasible.**  Either freeze a uniform continuum
   transfer or construct a connected-lattice embedding.  This is valuable for
   publication strength, but should not delay the novelty audit.

## Proposed entry-page changes (not applied)

### Minimal `README.md` change

Add four rows near the top of the quick-entry table:

1. “Challenge #121 completion audit” → `docs/ODDCYCLE_CHALLENGE_AUDIT.md`
2. “Oddcycle continuum all-depth theorem” →
   `docs/SYMMETRIC_ODDCYCLE_INTERVAL_FAMILY.md`
3. “Interacting physical transfer” →
   `docs/SYMMETRIC_ODDCYCLE_PHYSICAL.md`
4. “Oddcycle novelty boundary” → `docs/ODDCYCLE_NOVELTY_FILTER.md`

Do not call the result `challenge-ready` until the broad novelty row is
closed.

### Minimal `START_HERE.md` change

Prepend a compact “current main result” block:

- exact independently varying interval alphabet in dimension five;
- strict positivity at every depth;
- exact interacting five-mode auxiliary-field transfer at \(z=1\);
- overall challenge status still **partial** because broad novelty and public
  endgame remain open.

Then place the four documents above at the start of the reading order and
replace the stale next-step list with the four-item minimum closure plan from
this audit.  Keep historical scan documents below them; do not delete the
negative-result record.
