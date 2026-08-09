# Anticommuting D4 Certificate Design

## Objective

Tighten the existing schema-v3 certificate for the fixed benchmark

```text
periodic 12x12 spin-1/2 isotropic Heisenberg model
h_ij = (XX+YY+ZZ)/4
T = 1
operator-norm tolerance = 1e-6
```

without changing its five-copy fourth-order Suzuki circuit, four-matching
fragmentation, or compiled-cost convention.  The immediate target is a
machine-verified candidate at 98 Trotter steps:

```text
candidate groups = 30*98 + 1 = 2941
published groups = 11791
improvement = 11791/2941 = 4.00918055083305...
```

## Evidence and feasibility

At 98 steps the existing certificate gives a degree-four contribution
`1.6100509989613002e-6`.  A discovery-only greedy partition of the concrete
local degree-four defect into pairwise-anticommuting groups of at most ten
Pauli strings reduced this contribution by a factor
`3.108054463616103`.  Leaving every other certified contribution unchanged
then gives the discovery estimate

```text
degree-four contribution: 5.180253492366627e-7
all unchanged contributions: 4.395310649104868e-7
total: 9.575564141471495e-7
```

The `4.2443585852850405e-8` margin is much larger than the existing rational
coefficient-interval widths.  This discovery result is not itself a proof;
the design below converts it into an independently checked certificate.

## Mathematical certificate

Write the exact local right-generator degree-four coefficient as

```text
D4 = sum_j c_j P_j,
```

where every `P_j` is a phase-free Pauli string and every `c_j` is enclosed by
a rational interval.  Partition the indices into disjoint groups `G_a` such
that every pair of distinct Paulis in one group anticommutes.  Since

```text
(sum_{j in G_a} c_j P_j)^2 = (sum_{j in G_a} c_j^2) I,
```

the group has the rigorous bound

```text
||sum_{j in G_a} c_j P_j||
    <= sqrt(sum_{j in G_a} sup(|c_j|)^2).
```

One triangle inequality between groups gives the local certificate

```text
||D4|| <= sum_a sqrt(sum_{j in G_a} sup(|c_j|)^2).
```

Every square root is rounded upward to a rational number.  The optimizer may
use floating point to discover the partition, but the verifier trusts only
the submitted Pauli identifiers, exact symplectic anticommutation checks,
rational coefficient intervals, and outward-rounded square-root witnesses.

## Architecture

### Exact coefficient construction

Refactor the existing leading-E5 calculation so it can return its merged
Pauli coefficient intervals instead of immediately summing their absolute
values.  Canonicalize every local Pauli under translations by the colored
`2x2` unit cell before merging.  Multiplying the homogeneous log coefficient
by five produces the degree-four right-generator coefficient.

The original Pauli-l1 result remains available and remains the bound used for
the degree-five, degree-six, and degree-seven repeated-adjoint estimates.
Only `d4_site` changes in the first implementation.

### Partition discovery

Sort Pauli terms by decreasing interval midpoint magnitude.  Starting with
the largest unused term, greedily add the largest unused term that
anticommutes with every current group member until the configured maximum
group size is reached.  Singleton groups are allowed.  Discovery output is a
deterministic tuple of Pauli-index tuples.

### Proof object

The schema-v3 candidate gains:

```text
d4_norm_method
d4_pauli_terms
d4_anticommuting_groups
d4_group_bounds
d4_cell_norm_upper
```

Pauli terms are stored in binary symplectic form with rational coefficient
interval endpoints.  Group bounds are exact rational outward upper bounds.

### Independent verification

The fast verifier checks:

1. every submitted Pauli term appears exactly once;
2. indices are in range and groups are nonempty;
3. every pair within a group anticommutes exactly;
4. every group bound squares to at least the sum of squared coefficient
   absolute upper endpoints;
5. group bounds sum to the submitted cell bound;
6. the cell-to-site conversion and total-error arithmetic are exact;
7. step 98 meets the tolerance and step 97 does not.

Deep verification regenerates the interval coefficient map and requires it
to equal the proof object before repeating all fast checks.

## Failure containment

The new certificate is accepted only if its exact total at 98 steps is at
most `1e-6`.  If interval inflation removes the discovery margin:

1. increase the maximum anticommuting group size;
2. improve the deterministic clique assignment while retaining exact
   verification; then
3. apply the same certificate to degree five.

At every point the prior 116-step schema-v3 certificate remains a valid
fallback.  No empirical norm is used in the proof path.

## Tests

- Exact unit tests for symplectic anticommutation and outward square roots.
- Partition coverage and corruption-rejection tests.
- A regression test proving the grouped bound is no larger than Pauli-l1.
- A slow regeneration test for the exact D4 interval coefficient map.
- Fast and deep certificate-verifier tests.
- Integer-boundary tests at steps 98 and 97.
- Existing dense `2x2` evolution cross-check updated to step 98.
- Full solution and repository test suites before submission.

## Deferred work

The 5x and 10x programs are intentionally separate:

- 5x: exact right-generator coefficients through degree 10 plus shorter tail
  and finite-cluster norm certificates;
- 10x: matching-phase cycling and a degree-four processor, or an
  interval-certified optimized sixth-order kernel.

Those changes are not required to establish the 4x certificate and will not
be mixed into its first reviewable commit series.
