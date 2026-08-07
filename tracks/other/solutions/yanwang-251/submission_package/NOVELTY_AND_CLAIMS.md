# Novelty and claim boundary

## Principal contribution

The principal contribution is an interface-width explanation for repeated
failure modes in the weighted arboreal-gas negative-correlation problem.
Two-terminal positive networks reduce to a scalar effective activity;
three-terminal parallel composition has an exact nonpositivity-preserving
identity; but four-terminal partition signatures admit an exact positive
crossover.  Thus four terminals are the first boundary width at which global
connectivity information is algebraically capable of reversing the sign.

The second contribution is the exposed-face obstruction: after target
valuations align the four sectors, every nonzero valuation block of a graphic
independent-set face is a direct sum of graphic-minor basis measures and is
Rayleigh.  A zero valuation block can be positive only if a smaller
delete/contract minor is already a counterexample.  Hence a minor-minimal
witness must be an interior, finite-scale interference effect rather than a
single exposed monomial phase.

## What is standard and is not claimed as new

- Closure of I-Rayleigh matroids under direct and two-sums is known.  The
  effective-activity formula is included because it gives a concrete no-go
  statement for cardinality-amplifier gadgets in issue #251.
- Real stability/Rayleighness of weighted basis measures of graphic minors is
  standard.  The contribution is their use in the aligned-sector
  exposed-face reduction.
- Small-graph and series-parallel I-Rayleigh results are prior work and are
  not counted as results of this submission.

## Claims supported by complete exact arithmetic

- The three-terminal composition identity is verified on a basis of the
  five-dimensional signature space and proved algebraically in the note.
- The two displayed four-terminal signatures are positive integer vectors,
  are individually nonpositive for every disjoint perfect matching, and have
  strictly positive composition gaps for all three matchings.
- The symmetric-book theorem has an algebraic transfer proof; the bundled
  direct forest enumerator provides an independent finite regression.

## Explicit non-claims

- The abstract four-terminal signatures are not claimed to be realizable by
  positive-weight graph modules.
- The submission does not prove a universal inequality for disjoint edges.
- It does not provide a finite graph satisfying `Z_ef Z > Z_e Z_f` and
  therefore does not pass the original success gate of issue #251.
- This repository submission is not itself a claim of journal-level novelty.
  A specialist MathSciNet/zbMATH search and expert review remain appropriate
  before external publication.

## Position relative to PR #213

PR #213 by @Osgood001 establishes a universal theorem for adjacent edges via
real stability of star marginals, closing the adjacent-edge branch.  This
submission advances the unresolved disjoint-edge branch: it proves structural
no-go results at interface widths two and three, demonstrates exact sign
reversal at width four in the ambient signature cone, and isolates graphic
realizability as the remaining barrier.  The two submissions address
different parts of issue #251 and should be evaluated on their own claims.
