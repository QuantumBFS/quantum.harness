# Exact V4 reduction truth contract

Status: exact solver-independent equivalence checks. This file reports no SDP
feasibility result and no bulk-gap bound.

## Claim

For every fixed rational `gamma`, the reduced SDP is feasible if and only if
the unreduced finite relaxation is feasible. The reduction changes the
coordinate representation, not the basis/order relaxation.

The claim has three ingredients.

## 1. Centered/scalar congruence

For every nonidentity canonical Pauli word `w`, the one-symbol basis contains

```text
b_w = w
s_w = zeta(w) I.
```

Replace `b_w` by the centered row

```text
c_w = b_w - s_w.
```

Together with the unchanged identity and scalar rows, this is an invertible
integer triangular basis transformation. Exact state-polynomial
multiplication gives

```text
<c_u,c_v> = <b_u,b_v> - <s_u,s_v>
<c_u,s_v> = 0.
```

Therefore the original `703 x 703` positive matrix is congruent to independent
`351 x 351` centered and `352 x 352` scalar blocks. PSD is preserved in both
directions by the invertible congruence.

The truth test reconstructs all four terms of every centered entry and checks
them against the reduced formula. It also checks every centered/scalar cross
entry as an exact zero polynomial.

## 2. Gap facial reduction

The gap basis has four rows whose operator part is identity:

```text
I, zeta(X)I, zeta(Y)I, zeta(Z)I.
```

Their full `4 x 4` gap block is identically zero. For a Hermitian PSD matrix,
a zero diagonal forces its entire row and column to vanish. Hence the original
`7 x 7` condition is equivalent to:

```text
the remaining 3 x 3 bare-(X,Y,Z) block is PSD;
every removed-to-retained cross entry is exactly zero.
```

The implementation retains the latter as real linear equalities. It does not
silently discard the cross entries.

## 3. V4 Reynolds projection

Let `V4` be the global spin rotations by pi about the x, y, and z axes. Every
Pauli word is an eigenvector of this action with one of four sign characters.
The Heisenberg Hamiltonian terms have the trivial character.

For any feasible state-polynomial functional `L`, define

```text
L_bar(p) = (1/4) sum_(g in V4) L(g p).
```

The basis is closed under `V4`, and every normalization, stationarity, and gap
constraint is equivariant. Thus the matrices of `L_bar` are averages of
congruent PSD matrices and remain PSD. Conversely, an invariant feasible
functional is already feasible in the original relaxation. Restricting to the
invariant quotient therefore preserves feasibility exactly.

This averages the state-polynomial functional, not the physical state:

```text
L_bar(zeta(a) zeta(b))
  = (1/4) sum_g omega_g(a) omega_g(b),
```

which is generally not the product of expectations in the mixed state
`omega_bar`. The reduction therefore does not impose a symmetric physical
KMS state.

## Machine truth gates

For the Shastry-Sutherland point `L=1, d=2, g=4/5, gamma=1/2`, the tests require:

```text
source moments:             74,602
V4-invariant moments:       19,108
eliminated characters:      55,494

source positive cone:          703
centered V4 blocks: 108, 81, 81, 81
scalar V4 blocks:   109, 81, 81, 81
gap V4 blocks:        1,  1,  1
facial equalities:              3
```

The invariant inventory is independently reconstructed from every reduced
matrix coefficient and equality, then required to equal the filtered source
inventory exactly.

At the analytic `g=0` dimer point:

```text
gamma=1:   all reduced equalities are exact zero and all blocks are PSD;
gamma=1.1: the reduced gap minimum is -0.1.
```

These checks use exact rational state-polynomial coefficients. Floating point
is used only to read eigenvalues of matrices already evaluated in the exact
dimer functional.

Run the complete suite with:

```bash
julia --project=julia-env \
  tracks/polyopt/solutions/sdp-gap-seekers/test/runtests.jl
```
