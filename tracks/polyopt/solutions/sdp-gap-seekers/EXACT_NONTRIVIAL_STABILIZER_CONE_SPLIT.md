# Exact nontrivial-character stabilizer cone split

## Scope

This reduction applies to the unrestricted Shastry--Sutherland
`L=2,d=2` state-polynomial relaxation after the exact V4, conjugation,
anti-diagonal spatial, and global spin-axis quotients. It does not identify
different nontrivial V4 characters. That stronger identification was tested
previously and rejected because it was not coefficientwise exact after the
combined spatial/spin quotient.

## Exact row theorem

Fix one nontrivial V4 character. Its stabilizer inside the S3 axis-permutation
quotient has order two. On every retained spatial-parity row space this
stabilizer is an exact signed involution `T`, so the integer row basis splits
into its `T=+1` and `T=-1` eigenspaces.

The moment functional has already been averaged under this stabilizer. For
one plus row `u` and one minus row `v`, covariance gives

```text
B(u,v) = B(Tu,Tv) = B(u,-v) = -B(u,v).
```

Hence every plus/minus coefficient must vanish exactly, and the original PSD
matrix is congruent to the direct sum of the two eigenspace matrices. At row
degree two the plus eigenspace is the off-diagonal spin `l=2` component; the
minus eigenspace contains spin `l=1`. This interpretation is not needed for
the block-diagonalization proof.

## Structural L=2 gate

SCNet job `118189732`, source commit `b61e331`, proved the signed-involution
structure without constructing coefficient matrices. For each of the three
nontrivial characters, the centered plus/minus and scalar plus/minus blocks
split as

```text
975 = 490 + 485
900 = 460 + 440
650 = 315 + 335
600 = 310 + 290.
```

The 6-side and 3-side gap blocks are entirely in the minus eigenspace. Each
positive plus dimension equals the corresponding already-retained
S3-standard `l=2` dimension. Matching dimensions do not authorize deletion or
congruence of those cones; continuous-spin congruence is a separate future
gate.

If all within-character cross coefficients replay as zero, retaining both
eigenspace cones changes the exact PSD inventory from 4,446,492 to 2,540,067
packed entries and lowers the maximum side from 975 to 490. It retains all
three V4 characters and every `l=1` and `l=2` cone.

## Required coefficient gate

Before the split formulation is hashed or solved, the implementation must:

1. reconstruct the same unrestricted model and exact quotient;
2. rebuild the signed involution and both integer eigenspace bases;
3. verify all 1,906,425 plus/minus entries are exactly zero;
4. record the per-block comparison counts and exact result; and
5. independently construct and fingerprint the split cone coefficients.

SCNet job `118189871`, source commit `49bd9ea`, is the coefficient gate. A
solver status, matching dimension, or floating residual cannot replace it.

## Passing coefficient result

Job `118189871` completed in 28:58 with 6,016,104 KiB peak process RSS. All
1,906,425 cross entries were exactly zero, including 237,650/202,400 centered
and 105,525/89,900 scalar entries per nontrivial character. Its runmeta
SHA-256 is
`ad7ba185507b80404b3056ae220e0346e110a256b4acaa501f93f4e35a96de7b`.

The stabilizer split is therefore authorized. The next independent gate is a
build-only fingerprint of every retained split-cone coefficient after the
separate exact SO(3) rank-four moment projection.
