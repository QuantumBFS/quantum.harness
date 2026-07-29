# Verification instructions for AI reviewers

These instructions apply to every file in this directory.

## Purpose

Act as a skeptical, read-only verifier of the proposed sign-free determinant
construction. Do not treat `results.json`, the prose in `README.md`, or a
successful randomized run as proof by itself. Do not edit the mathematical
claim, the verification code, or recorded results merely to make a check pass.

The submission makes three different kinds of statements. Keep them separate:

1. proved statements about products of exponentials of real tridiagonal
   Metzler matrices;
2. computational evidence and exact finite-dimensional certificates;
3. literature-search and novelty statements, which are explicitly not claims
   of worldwide priority.

## Before running code

State the setup that will be checked:

- real `n`-by-`n` tridiagonal generators;
- nonnegative entries immediately above and below the diagonal;
- arbitrary real diagonal entries;
- arbitrary finite product depth;
- the grand-canonical weight `det(I + P)`;
- open-chain geometry for the interacting realization.

Ask the user to confirm or correct this setup before starting computation, as
required by the repository-level instructions. The default verification is a
small local CPU run and should take only a few seconds.

## Reproduce the computational checks

From the repository root, run:

```bash
python -m pip install -r tracks/qmc/solutions/zhong-guo-ren-neng-fei/requirements.txt
python tracks/qmc/solutions/zhong-guo-ren-neng-fei/verify.py
```

The second command must exit with status zero. Independently inspect the newly
written `results.json`; do not rely only on terminal text. At minimum require:

- `tn_semigroup.samples` equals 8000;
- `tn_semigroup.negative_determinant_count` equals zero;
- `tn_semigroup.determinant_below_one_count` equals zero;
- `tn_semigroup.minor_violation_count` equals zero;
- `tn_semigroup.minimum_checked_minor` is nonnegative up to the declared
  floating-point tolerance;
- the Fock-space trace and one-particle determinant agree to numerical
  precision;
- `exact_closing_edge_counterexample.exact_integer_determinant` equals `-1`;
- all Kramers commutant dimensions equal one;
- all tested Majorana skew-`J2` nullities equal zero.

Re-running the fixed-seed script should not produce an unexplained change in
the tracked `results.json`. A numerical failure is evidence against the
implementation or claim and must be reported, not patched around.

## Audit the proof independently

Check each logical implication in `README.md` rather than only its conclusion:

1. For every exterior-power degree `k`, derive the additive compound
   `A^[k]` and verify that tridiagonality prevents a negative wedge-reordering
   sign on every allowed off-diagonal transition.
2. Verify that an exponential of a Metzler matrix is entrywise nonnegative.
3. Use `C_k(exp(A)) = exp(A^[k])` to conclude that every minor of `exp(A)` is
   nonnegative.
4. Use Cauchy-Binet to check closure under arbitrary finite products.
5. Expand `det(I + P)` as the sum of principal minors, including the empty
   minor, to obtain the lower bound one.
6. Multiply the seven integer shear factors in the boundary counterexample
   directly and recompute `det(I + P) = -1`.

Reject or qualify the theorem if any step silently assumes symmetry, strict
positivity, invertibility of minors, fixed product depth, or periodic boundary
conditions. None of those assumptions belongs to the stated theorem.

## Audit the physical construction

Check the auxiliary-field identity on all four occupations of two neighboring
spinless-fermion sites. Confirm that:

- attractive nearest-neighbor density interaction gives a real Gaussian
  field;
- each field value changes only real diagonal one-body terms;
- open-chain hopping produces nonnegative nearest-neighbor entries in the
  imaginary-time generator under the sign convention stated in `README.md`;
- arbitrary chemical potentials do not spoil the tridiagonal Metzler
  property;
- the conclusion concerns the determinant weight for each auxiliary-field
  configuration, not the absence of every possible algorithmic difficulty.

Do not extend the claim to a periodic chain. The exact directed closing-edge
certificate shows why such an extension requires a separate proof.

## Audit independence from earlier sufficient conditions

Treat this as a family-level question. An individual matrix may satisfy an
older condition even when the full family does not.

Verify separately:

- the nonscalar diagonal-matrix obstruction to a fixed positive-definite
  conformal-orthogonal metric;
- the simultaneous presence of `I` and `-I` in the obstruction to a fixed
  one-sided split-metric cone;
- the scalar commutant of the matrix units in the no-common-Kramers argument;
- the block calculation forcing a proposed fixed Majorana contraction
  structure to vanish.

If a prior construction is found that covers the complete family after an
allowed fixed change of basis, report the exact theorem and source. Do not
infer containment merely from overlap with one-dimensional, bipartite, or
worldline-sign-free models.

## Literature and novelty discipline

The total-nonnegative matrix theory, Vandermonde determinants, and
Karlin-McGregor noncrossing kernels are classical. The submission does not
claim otherwise. A literature search may support the statement that the
specific determinant-QMC formulation was not found, but absence from a search
is not proof of novelty.

Any stronger priority assessment must:

- search current primary literature;
- identify exact theorem statements rather than keyword similarities;
- provide links or bibliographic identifiers;
- classify each result as identical, containing, overlapping, or unrelated;
- state unresolved uncertainty explicitly.

## Verification report

Return a concise report with:

1. `PASS`, `FAIL`, or `INCONCLUSIVE`;
2. separate verdicts for the theorem, implementation, physical mapping,
   independence checks, and novelty search;
3. the first concrete failing equation, file line, or numerical field, if any;
4. commands run and their exit status;
5. remaining claims that require expert or literature review.

A `PASS` means the stated bounded claims survived these checks. It must not be
reported as proof of worldwide publication priority.
