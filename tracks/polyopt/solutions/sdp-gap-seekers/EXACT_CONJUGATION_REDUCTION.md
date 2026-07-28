# Exact conjugation and real-cone reduction

Status: implementation awaiting the xH5 exhaustive truth gate. This document
does not report a new solve.

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

The xH5 truth run will fix the remaining exact moment/equality counts and bind
the derived model to deterministic coefficient and assembly hashes.
