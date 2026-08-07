# R03 candidate card — branch-safe `D4` triality cone

Claimed by: Zibo

Claim date: 2026-07-28

Initial status: `claimed-design`

## Candidate definition

Represent `so(8)` on its vector and two half-spin modules in fixed exact bases.
Intersect the three real Metzler generator cones after fixed transforms. Force
nonzero pairing, two noncommuting roots, and a plaquette/loop support mask.

The physical quantities are the two parity-resolved Spin traces. A
vector-determinant result alone is not considered new.

## Why it may be nonnegative

In each representation, Metzler exponentials and their products are
entrywise nonnegative, hence have nonnegative trace. Simultaneous positivity
would control both actual parity branches without selecting a square root from
the vector determinant.

## Novelty checks

The teammate already proved that the ordinary `D4` simple-root family is in
known split `SO(4,4)`. This proposal must additionally exclude:

- the same split cone under triality;
- a Levi/Borel or one-dimensional root cone;
- number-conserving `gl(4)`;
- Kramers, Majorana reflection, MTR, and open-chain Jordan–Wigner structure.

## Smallest experiment

Build rational/algebraic `8 x 8` Chevalley matrices for all three
representations and compile their off-diagonal inequalities into one LP.
Enumerate triality cycles, Weyl signs, physical real forms, and locality masks.

Success: exact noncommuting pairing rays with a new convention-stable parity
statement and physical route.

Failure: an exact Farkas certificate or symbolic identification with the known
split/Levi/Borel cone.

## Physical route

Simple roots map to hopping and pairing bilinears. Triality is useful only if a
positive HS dictionary produces a local interacting plaquette model. Otherwise
R03 is retained as a branch/reduction theorem, not a challenge solution.
