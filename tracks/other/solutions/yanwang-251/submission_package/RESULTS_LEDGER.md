# Results ledger for issue #251

## Counting rule

This ledger counts a result only when it has a distinct mathematical
statement and a defined evidence boundary.  Repeated optimizer failures,
different random seeds, compute volume, and near-zero floating-point values
are not counted.  Under that rule the project has produced 11 results:

- 4 theorem/lemma-level statements;
- 4 exact computer-assisted propositions; and
- 3 mechanism or search-geometry results.

The sign convention is `R=AD-BC`; issue #251 asks for `R>0`.

## A. Theorem/lemma-level statements

### A1. Positive two-terminal replacement is an effective activity

For a two-sum along `g`, the independent-set polynomial factors as a common
positive multiplier times the original polynomial with

```text
y_g -> (I_N^g-I_{N,g})/I_{N,g}.
```

Hence series/parallel extension, subdivision, path bundles, and arbitrary
positive two-terminal replacement cannot reverse the Rayleigh sign.  The
two-sum closure is prior art; the contribution here is its exact use as a
no-go theorem for cardinality-amplifier constructions in #251.

**Evidence:** algebraic proof in `RESEARCH_NOTE.md`, Section 2.
**Boundary:** not claimed as a new proof of general two-sum closure.

### A2. A minor-minimal witness cannot live on one exposed face

After aligning the four target sectors, every nonzero valuation block of a
graphic independent-set face decomposes into basis polynomials of graphic
minors.  These are Rayleigh.  A zero block can be positive only if a smaller
delete/contract minor is already a counterexample.

Therefore a minor-minimal counterexample must use finite-scale interference
between at least two adjacent layers; a single tropical phase cannot be its
first positive mechanism.

**Evidence:** matroid-face reduction in `RESEARCH_NOTE.md`, Section 3.
**Boundary:** this does not prove the sum of several layers nonpositive.

### A3. Three-terminal parallel composition preserves nonpositivity

For the five connectivity weights `(p,q,r,s,t)` on three terminals,

```text
R(x*y) = p_x^2 R(y) + p_y^2 R(x) - 2 p_x p_y s_x s_y.
```

Thus two nonpositive modules cannot compose to a positive module through a
three-terminal parallel interface.  The `n`-copy specialization is

```text
R_n = n p^(2n-2) [R_1-(n-1)s^2].
```

**Evidence:** proof in `RESEARCH_NOTE.md`, Section 4, plus complete symbolic
coefficient verification in `verify_interface_certificates.py`.

### A4. Strict Rayleigh theorem on the symmetric book slice

For `B_r = K3 join independent(r)`, every `r>=1`, every pair of distinct
edges, arbitrary positive designated activities, common core activity `p>0`,
and common spoke activity `q>0`,

```text
Z_e Z_f - Z_ef Z > 0.
```

This includes disjoint edge pairs.  The proof treats all edge-pair orbits by
a five-state transfer matrix and positive decompositions.

**Evidence:** `SYMMETRIC_BOOK_THEOREM.md`; the fast verifier independently
enumerates 222 exact edge pairs for `r=1,2,3,4`.
**Boundary:** the theorem is a two-parameter slice, not the fully multivariate
I-Rayleigh property of the topology.

## B. Exact computer-assisted propositions

### B1. Complete HSW augmentation exclusion

All `2^16-1 = 65,535` nonempty simple augmentations of the HSW core were
enumerated at spoke activity `2897/1000` with common augmentation activity
`r`.  Every coefficient of all 65,535 exact polynomials `R(r)` is
nonpositive.  Among them, 49,768 are simple three-connected graphs and have
`R(r)<0` for every `r>0`.  The sparsest three-connected layer consists of 671
labelled graphs in 11 symmetry classes; those 11 remain coefficientwise
nonpositive when their five new edges receive independent activities.

**Evidence type:** exhaustive exact polynomial census.
**Boundary:** larger augmentations with fully independent new-edge activities
are not all classified by this proposition.

### B2. Two grouped HSW reservoirs have coefficientwise certificates

For the alternating six-cycle latch, all 1,287 nonzero coefficients of the
factored Rayleigh polynomial are positive in the negative-correlation sign
convention.  For the pentagonal-prism reservoir, all 13,870 are positive.
The first tensor was independently reconstructed by modular Vandermonde
interpolation and all `2^21` non-target subsets.  The second used the complete
7,128-point interpolation grid with exact partition DP and off-grid checks.

**Evidence type:** two independent exact tensor reconstructions.
**Boundary:** the certificates cover the stated grouped activities; a witness
on either topology would have to break those symmetries.

### B3. Complete `3^18` four-terminal double-bridge tensor

The full signed tensor has 387,420,489 coefficient slots and 701,310 nonzero
coefficients: 267,288 positive and 434,022 negative.  Every positive exponent
has an exact negative-support midpoint certificate.  Hence no positive
monomial is an exposed vertex.  Three complete binary normal families,
`{-1,0}^18`, `{0,1}^18`, and `{-1,1}^18`, each contain `2^18` directions and
contain no positive exposed face.

**Evidence type:** exact forest tensor, 361,154,511 midpoint checks, and exact
face sums.  The raw tensor SHA-256 is
`53c492ce8a1cfa63f0d3b4a934fff0314ce09d24b05a11e58d10f556a6201eba`.

**Boundary:** convex-hull containment is not a global nonpositivity proof; the
natural midpoint SONC certificate class is itself insufficient.

### B4. Complete local tangent exclusion around 337 exact zeros

A deduplicated bank of 337 exact-zero disjoint-target graphs was obtained from
5,760 legal small-module compositions.  Every one of 44,152 missing-edge
pairs and 221,404 missing-edge triples has a coefficientwise nonpositive first
nonzero tangent form.  Arbitrarily asymmetric positive ratios inside those
two- or three-edge perturbations therefore cannot bifurcate to `R>0`.

**Evidence type:** exact integer forest totals and complete tangent tensors.
**Seed-bank SHA-256:**
`0f5b58898b963abbb8d808a54d1e19bcc5e98bcb8a065e235bcf1a7e1ef13339`.
**Boundary:** this is a complete statement for the defined seed bank, not all
zero points of the graphic-signature cone.

## C. Mechanism and search-geometry results

### C1. Four terminals are the first interface width permitting abstract escape

Two positive integer 15-state signatures are each nonpositive for every
disjoint perfect matching, yet their exact composition has reversed gaps

```text
1,134,803,118; 413,278,037; 74,494,526.
```

Together with A1 and A3, this establishes the interface-width split: scalar
reduction at width two, nonpositive closure at width three, and exact ambient
escape at width four.

**Evidence:** exact standard-library verifier and `RESEARCH_NOTE.md`, Section
5.
**Boundary:** the two signatures are not claimed graph-realizable.

### C2. Real graph signatures show numerical full local rank and a singular wall

Real four-terminal graph modules with numerical projective Jacobian rank 14
were found; this is the full dimension of the normalized 15-state signature
simplex.  This is strong evidence against a simple local dimension
obstruction.  Continuation toward the abstract positive signatures
nevertheless encounters a rapidly ill-conditioned fold/caustic.

**Evidence type:** exact enumeration of forest feature vectors, floating SVD
rank diagnostics, and numerical continuation.
**Boundary:** neither the rank observation nor the singular wall on tested
paths is promoted to a theorem.  An exact nonzero Jacobian minor would be
needed to certify rank 14 algebraically.

### C3. Exact atlas audit sharply identifies the first priority layer

Using the classical reductions that a minor-minimal counterexample is
three-connected and that the smallest simple weighted candidate has at least
eight vertices, the exact coefficient atlas covers every non-isomorphic
three-connected simple graph on 4--9 vertices with `q=m-2<=12`, together with
named cores: 251 cores, 11,407 target-pair orbits, and 5,805 orbits with at
least one positive exact coefficient.  A coverage audit recovered 94 named
orbits omitted by the first loader.  In the minimal eight-vertex cubic
three-connected layer, the complete positive-coefficient priority set is four
cores and 23 target-pair orbits.

**Evidence type:** exact nauty graph/isomorphism generation, automorphism
quotients, and coefficient tensors.
**Boundary:** the four-core/23-orbit statement concerns that minimal cubic
layer, not every possible eight-vertex graph or every weight vector.

## What is deliberately not promoted as a result

- the number of random starts or optimizer evaluations;
- floating-point values near zero;
- a failed search with no completeness statement; or
- unfinished W5 and full-atlas campaigns.

These remain steering evidence only and do not inflate the 11-result count.
