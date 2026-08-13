# Exterior-Cone Throughput Loop Prelaunch Amendment

Date: 2026-07-29

Status: binding amendment to
`2026-07-29-exterior-cone-throughput-loop.md`.

## Why this amendment exists

The arbitrary-depth exterior-cone theorem passed adversarial review, but the
first protocol draft mixed a useful numerical fit with an exact certificate
and repeated the same direct scan once per transform family. It also omitted
scale from candidate identity and sent BdG atoms through a determinant oracle
that cannot fix the Spin-lift sign. Those defects would create false theorem
claims or waste about three quarters of the first-stage work.

The scientific candidate is therefore the exact finite atom alphabet, not a
floating generator template. The clauses below override conflicting text in
Tasks 2--9. Task 1's NumPy certificate remains a numerical screen; an
arbitrary-depth theorem requires exact atoms and exact replay.

## Frozen boundaries

- Do not implement or continue `classify_r01_fixture`.
- Do not modify the frozen determinant, Spin-trace, high-precision, R01, or
  generic parameter-scan infrastructure.
- Do not touch the organizer-facing branch or PR #178.
- Fix every candidate before sampling words.
- Stop on the first stable negative or complex weight.
- Record every valid success, failure, and operational boundary in Markdown.

## Exact candidate identity

Task 2 stores the finite propagators themselves:

```text
candidate card
  = exact rational atom matrices
  + ordered exact factorization
  + transpose orbit
  + common positive rational orbit coefficient
  + magnitude tier
  + support/locality declaration
  + finite-real-microword witness
```

Every rational is encoded canonically as:

```json
{"numerator": -3, "denominator": 5}
```

The denominator is positive, numerator and denominator are coprime, and zero
is `0/1`. Cards contain no floats. Canonical compact sorted JSON of the whole
card is hashed for `candidate_id`. Changing magnitude, coefficient, factor
order, transpose pairing, support, or atom alphabet changes the id.

Runtime `scipy.linalg.expm(scale*A)` must not define a mathematical candidate.
Floating arrays are a one-way projection of the exact card for the frozen
numerical oracles. A future scale scan creates new cards and a new protocol;
there is no external float scale Cartesian axis in Stage 1.

Task 2 exposes:

```python
def candidate_card(*, template: str, seed: int) -> dict[str, object]
def candidate_id(card: Mapping[str, object]) -> str
def exact_atoms_from_card(card: Mapping[str, object]) -> tuple[sp.ImmutableMatrix, ...]
def float_atoms_from_card(card: Mapping[str, object]) -> tuple[np.ndarray, ...]
def exact_factorizations_from_card(
    card: Mapping[str, object],
) -> tuple[tuple[dict[str, object], ...], ...]
def candidate_structure_audit(card: Mapping[str, object]) -> dict[str, object]
```

Allowed exact primitives are rational shears `I+qE_ij`, positive rational
diagonals, positive odd-cycle blocks, and ordered microwords of two through
six such factors. The partner of `B=F_r...F_1` is constructed exactly as
`B^T=F_1^T...F_r^T`; it is never randomized independently. Each transpose
orbit has one strictly positive rational coefficient.

## First-tranche templates and count

The nine templates are:

```text
exact3-oddcycle-shear-pair
exact3-diagonal-oddcycle-pair
exact4-shear-loop-pair
exact4-graded-shear-pair
exact4-block-shear-pair
exact4-diagonal-loop-pair
exact5-shear-loop-pair
exact5-oddcycle-block-pair
exact6-graded-shear-pair
```

Each uses seeds `0..255`. The exact dimension allocation is:

| N | templates | candidates |
|---:|---:|---:|
| 3 | 2 | 512 |
| 4 | 4 | 1024 |
| 5 | 2 | 512 |
| 6 | 1 | 256 |
| total | 9 | 2304 |

The first determinant protocol has no `N=8` and no BdG template. Pure
odd-monomial/P0 examples remain explicit known-reduction controls and cannot
be discovery promotions.

Every discovery card is exactly transpose closed, invertible with positive
determinant, connected on its declared support, and contains a noncommuting
pair plus a loop, odd-cycle route, cross-block edge, or degree-three feature.

## One transform search per candidate

Delete `transform_family` from the protocol axes. For each grade, search one
ordered union:

```text
signed/permutation/Hodge
  -> block-Hadamard/Klein
  -> sparse unimodular
  -> direct-sum/tensor compositions
```

Different grades may choose transforms from different source libraries. A
candidate receives one structure audit, one direct-word screen, and one
manifest. The manifest records the selected source library per grade. Thus
the Stage 1 count is `9*256=2304`, not `9*4*256=9216`.

## Numeric versus exact certificate

The Task 1 NumPy result is named `numeric-cone-fit`. Task 3 adds:

```python
def exact_common_transform_certificate(
    exact_atoms,
    exact_transform_library,
) -> dict[str, object] | None
```

It reconstructs exact compounds and verifies every entry of every
`T_k^{-1} wedge^k(B_s) T_k` is real and nonnegative using rational arithmetic
or a declared exact algebraic field. The certificate records atom hashes,
basis order, transforms, exact solve/inverse witnesses, field, and exact
entry signs. A numeric fit is never serialized as an exact theorem.

An exact certificate is promoted immediately to novelty and physical audit.
It is not subjected to survivor percentiles, `sigma_min` ranking, or long
random scans. Run only a small direct determinant regression against the
frozen oracle.

## Exact-first and mixed-word order

The screening order is:

```text
exact card construction
  -> orbit/structure/physical sanity
  -> cheap known-reduction flags
  -> union-transform numeric prefilter
  -> exact exterior-certificate replay
  -> exact pass: unconditional promotion
  -> otherwise exhaustive shallow mixed words
  -> otherwise 64-history adversarial/random screen
  -> otherwise 1024 and 16384 pressure stages
```

Before random histories, enumerate lexicographically all words of depths
`2,3,4` containing at least two distinct atom indices. Repeated
single-atom words are removed. Cyclic or transpose-reversal deduplication is
allowed only after a test proves weight preservation. The first stable
negative/complex weight stops the candidate; uncertain values are rebuilt
from the exact card and replayed at high precision.

After the exhaustive gate, the 64-history order is alternating noncommuting
pairs, commutator-like/transpose-mismatch words, then hash-seeded mixed words.

## Induced-cone quotient

For every exact grade-1 transform in the union that makes all atoms
nonnegative, directly test all compounds. If all are nonnegative, label the
candidate `known-induced-tn`.

When comparing an independently chosen `T_k` with `wedge^k(T_1)`, quotient
positive-monomial automorphisms of the orthant. If

```text
(wedge^k T_1)^(-1) T_k
```

is a positive diagonal scaling times a ray permutation, the two transforms
define the same simplicial cone. `noninduced-within-library` is only a finite
library result, not a complete novelty proof.

## Separate BdG/Spin loop

`exterior-cone-throughput-v1` accepts only real number-conserving atoms.
BdG/Majorana candidates belong to `exterior-spin-throughput-v1`, whose primary
oracle is `oracle.majorana.spin_trace_weight` or an exact Fock/Spin trace.
`det(I+D)` is only a square-identity cross-check and cannot select the
continuous Spin-lift sign.

## Terminal status and promotion

Manifests distinguish at least:

```text
rejected-structure
rejected-negative
rejected-complex
uncertain-high-precision
survivor-no-certificate
survivor-numeric-cone-fit
exact-exterior-certificate
known-reduction-control
operational-error
```

`exact-exterior-certificate` is promoted unconditionally.
`survivor-numeric-cone-fit` remains research evidence but cannot support a
theorem. Top-percentile ranking applies only to numerical survivors without
an exact certificate.

## Launch gate

Do not launch 76 shards until tests prove:

- all 2304 cards are deterministic and unique;
- dimension counts are `512/1024/512/256`;
- every card is float-free and exactly replayable;
- magnitude tier and coefficient orbit affect the hash;
- no runtime float exponential defines an atom;
- transform libraries form one ordered union;
- numeric and exact certificate statuses are separate;
- the shallow exhaustive mixed-word gate is active;
- induced audits quotient positive-monomial cone automorphisms;
- BdG is absent from the determinant protocol;
- exact-pass promotion is unconditional;
- every card has exactly one owner under
  `int(candidate_sha256[:16],16) mod 76`.
