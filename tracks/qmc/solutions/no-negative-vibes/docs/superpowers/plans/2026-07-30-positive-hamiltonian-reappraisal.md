# Positive Hamiltonian Reappraisal Implementation Plan

> **Execution rule:** work only in `codex/positive-hamiltonian-reappraisal`;
> keep collaborator-owned tensor-square/oddcycle/exterior work read-only.

**Goal:** turn the archived positivity mechanisms into explicit Hamiltonian candidates and
promote only families that are QMC-runnable, physically nontrivial, and not directly covered
by conventional simulation routes.

**Base:** stacked on `work/xianzhi/bottom-up-positive-cones` (PR #7).

## Bootstrap delivered by the draft PR

- [x] Freeze the revised success criterion and ownership boundary.
- [x] Create `docs/POSITIVE_HAMILTONIAN_REAPPRAISAL_LEDGER.md`.
- [x] Start R1 in `docs/ODD_BLOCK_TN_REVIVAL.md`.

## Task 1: Machine-check the ledger contract

**Files**

- Create: `fixtures/positive_hamiltonian_reappraisal.json`
- Create: `oracle/reappraisal_registry.py`
- Test: `tests/test_reappraisal_registry.py`

**Steps**

1. Write a failing test requiring unique candidate IDs, an owner, a current verdict,
   all six gate fields, evidence paths, and an explicit `next_falsifier`.
2. Implement a small standard-library loader/validator; do not add dependencies.
3. Encode every row of the Markdown ledger in JSON.
4. Verify:

   ```bash
   cd tracks/qmc/solutions/no-negative-vibes
   python3 -m pytest tests/test_reappraisal_registry.py -q
   ```

## Task 2: Make R1 a scalable explicit family

**Files**

- Create: `oracle/odd_block_tn_reappraisal.py`
- Test: `tests/test_odd_block_tn_reappraisal.py`
- Update: `docs/ODD_BLOCK_TN_REVIVAL.md`

**Steps**

1. Test a deterministic `L`-site constructor
   `B=P_C3 diag(X_0,X_1,X_2)` using products of positive bidiagonal TN factors.
2. Test fixed-partition membership, transpose closure and the existing determinant certificate.
3. Build the small-Fock
   `H_L=-sum_a q_a[Gamma(B_a)+Gamma(B_a)^dagger]`;
   test Hermiticity, number conservation and a nonzero interaction body order above two.
4. Add contractive and Kac-normalized parameterizations and report `||H_L||/L` for small `L`.
5. Re-run the exact crossed-partition `-2` counterexample as a boundary test; never claim
   independent local routes are safe.

## Task 3: Conventional-method exclusion harness for R1

**Files**

- Create: `oracle/conventional_exclusion.py`
- Test: `tests/test_conventional_exclusion.py`
- Create: `docs/CONVENTIONAL_METHOD_EXCLUSION_PROTOCOL.md`

**Steps**

1. Implement exact occupation-basis local phase-gauge feasibility for small systems.
2. Return an explicit frustrated sign cycle when no stoquastic gauge exists.
3. Check quadratic/matchgate closure by extracting occupation Möbius coefficients.
4. Check conserved one-body/static-sector projectors via exact commutants.
5. Record JW/worldline/SSE conclusions only to the strength proven by these witnesses.

## Task 4: R1 QMC minimum working example

**Files**

- Create: `oracle/odd_block_tn_qmc.py`
- Test: `tests/test_odd_block_tn_qmc.py`
- Create: `docs/ODD_BLOCK_TN_QMC_MWE.md`

**Steps**

1. Enumerate continuous-time oriented vertex words at small `L`.
2. Compare determinant-word weights with exact Fock traces.
3. Measure expansion order and one route-resolved density correlator.
4. Demonstrate polynomial single-particle cost without constructing `2^(3L)` matrices.
5. Stop if the only extensive normalization collapses to a trivial vacuum/identity limit.

## Task 5: Reappraise R2 and R3

**Files**

- Create: `docs/FIXED_LINF_HAMILTONIAN_AUDIT.md`
- Create: `docs/RECIPROCAL_PARABOLIC_HAMILTONIAN_AUDIT.md`
- Extend: `fixtures/positive_hamiltonian_reappraisal.json`

**Steps**

1. For fixed weighted `l_infinity`, construct Hermitian vertices and test whether the
   contraction condition permits finite-density noncommuting dynamics.
2. For reciprocal-parabolic generators, prove a Hermitian embedding or write an exact no-go
   showing that the triangular decoration disappears from the physical trace.
3. Apply the same six gates; do not run broad scans before the analytic audit.

## Task 6: Model-level literature audit

**Files**

- Create: `docs/POSITIVE_HAMILTONIAN_LITERATURE_MATRIX.md`
- Update: `docs/POSITIVE_HAMILTONIAN_REAPPRAISAL_LEDGER.md`

**Steps**

1. Search by the explicit Hamiltonian terms, symmetry, geometry and QMC vertex—not by
   “positive matrix” alone.
2. Record nearest known model, known solver, exact overlap and remaining gap.
3. Downgrade candidates with a direct known solver; cite primary sources.

## Task 7: Promotion decision

**Files**

- Create: `docs/POSITIVE_HAMILTONIAN_PROMOTION_REPORT.md`

A candidate is promoted only if all six gates are supported. Otherwise preserve the strongest
valid lower-level result and its stopping certificate. The report must distinguish:

- `QNC-primary`;
- `sign-free-but-conventional`;
- `Hamiltonian-valid-physics-open`;
- `math-only`;
- `falsified`;
- `collaborator-owned`.
