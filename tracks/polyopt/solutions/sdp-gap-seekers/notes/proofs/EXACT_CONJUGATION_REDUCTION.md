# Exact conjugation and real-cone reduction

Status: exact truth gate and solver-free MOF build passed on xH5. This
document does not yet report a new solve.

## Claim

Computational-basis complex conjugation `K` is an antiunitary symmetry of the
fixed Shastry--Sutherland Hamiltonian. On a canonical Pauli word,

```text
K(w) = (-1)^(number of Y factors in w) w.
```

Every unrestricted feasible functional can be averaged with its conjugate.
The average is still feasible and sets every conjugation-odd scalar moment to
zero. Conversely, a conjugation-invariant feasible functional is already
feasible in the V4-reduced relaxation. This preserves feasibility of the
finite relaxation; it does not restrict the physical state class.

## Realification

For one V4 character block, let `D` contain the conjugation sign of every
Pauli-word row. Conjugation invariance gives

```text
M = D conj(M) D.
```

Thus entries joining rows of equal sign are real and entries joining rows of
opposite sign are purely imaginary. Define the exact diagonal phase

```text
P[row] = 1  for a conjugation-even row,
P[row] = i  for a conjugation-odd row.
```

Then `P' M P` is real symmetric and is PSD exactly when `M` is Hermitian PSD.
The cone side dimensions remain

```text
[108,81,81,81] and [109,81,81,81], plus three 1 x 1 gap blocks.
```

The generic MOI Hermitian bridge used by the baseline solve creates 126,525
scalarized semidefinite coordinates for the eight positive blocks. Direct
real cones require 31,807 coordinates for those blocks, plus three scalar gap
coordinates. This is a representation reduction, not constraint dropping.

The exact projection reduces the V4 inventory from 19,108 to 16,660 scalar
moments by removing 2,448 conjugation-odd moments. All three V4-reduced affine
equalities restrict to exact zero on this invariant inventory, so the real
model has normalization plus 11 PSD constraints and no additional affine
equalities.

## Machine truth gates

`ConjugationSymmetryReduction.jl` checks over exact rationals:

1. every Hamiltonian term is invariant under `K`;
2. every one of the 31,810 upper-triangular reduced block coefficients obeys
   the exact conjugation covariance relation;
3. every phase-gauged, conjugation-projected block coefficient is exactly
   real;
4. the complete affine-equality row space is invariant under `K`;
5. the emitted coefficient maps reproduce exactly the conjugation-even
   subset of the V4 moment inventory.

Slurm job `22988221` generated and reloaded both solver-free models from clean
commit `25a8311d12d24b5495c531a9741249180ed28b4f`:

```text
gamma=0:   model SHA-256 0a2c9166eb033a2e782ab91a062491961a5d8139a1b04e80f6f564d1a75a6e14
gamma=1/2: model SHA-256 b50d66a48a45de0f2a25e411ab3dcc6a06f3a99b06626951277ae09686062707
```

Both reload as 16,660 variables and 11 named
`PositiveSemidefiniteConeTriangle` constraints with the declared dimensions.
