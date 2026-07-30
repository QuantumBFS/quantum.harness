# Exact SO(3) `l=2` cone-congruence gate

## Purpose

The exact nontrivial-character stabilizer split retains four discrete pieces
of each continuous-spin `l=2` multiplicity space: one S3-standard cone in the
trivial V4 character and one stabilizer-plus cone in each of the three
nontrivial V4 characters. Their dimensions agree, but dimension agreement is
not a coefficient proof and does not authorize removing a PSD constraint.

The direct 38-cone solve reached 509,850,832 KiB before iteration zero. The
next decision-relevant question is therefore whether these four cones become
the same affine PSD matrix after the already-proved exact SO(3) rank-four
moment projection.

## Fail-closed test

For each positive family and spatial parity, the implementation:

1. erases spin-axis labels from every underlying state-polynomial row while
   retaining sites, state-symbol grouping, operator support, spatial parity,
   and exact integer combination coefficients;
2. requires a unique bijection from every nontrivial stabilizer-plus row to
   the S3-standard multiplicity row with the same spin-blind signature;
3. reconstructs both affine matrix entries exactly;
4. applies `T_xxxx = T_xxyy + T_xyxy + T_xyyx` entrywise; and
5. compares every mapped upper-triangle polynomial exactly.

There are 12 target blocks and 940,050 mapped triangle entries at `L=2,d=2`.
Equal, sign-opposite, and unmatched entries are counted separately. Only
940,050 equal entries with zero opposite and zero unmatched entries set the
truth result to exact. Cone removal is guarded by that exact result and is
disabled in the truth-only jobs.

If the gate passes, removing the three duplicate `l=2` copies per group would
change the retained inventory from 2,540,067 to 1,600,017 packed entries while
keeping the maximum side 490. This is an exact formulation hypothesis until
the coefficient job passes; it is not feasibility or spectral-gap evidence.
