# Exact spin-axis involution reduction

## Scope

This is a further exact representation change of the already-proved
conjugation-real, V4-reduced Challenge 88 finite SDP. It does not change the
Hamiltonian, local-consistency window, unrestricted KMS state class,
polynomial degree, target gamma, or any constraint of the finite relaxation.

The generator is the global π spin rotation about the axis
`(x+z)/sqrt(2)`:

```text
S(X) = Z,  S(Z) = X,  S(Y) = -Y,  S² = identity.
```

It is unitary and commutes with computational-basis conjugation on the Pauli
word space. The isotropic Shastry--Sutherland Hamiltonian is invariant under
it term by term after summing the three spin components of every bond.

## Invariant moments

For a canonical Pauli word `w`, write

```text
S(w) = s(w) w',  s(w) = (-1)^(number of Y factors).
```

The action on a scalar state moment is multiplicative. Therefore an
S-invariant functional obeys

```text
x_k = s(k) x_S(k).
```

Every two-element orbit supplies one representative variable. A fixed moment
with `s(k)=-1` is exactly zero. The implementation constructs this signed
orbit quotient over the complete 16,660-moment conjugation-even inventory and
checks closure and `S²=identity` exactly.

This restriction preserves feasibility in both directions. A feasible
unrestricted functional can be averaged with its S transform. Conversely,
the signed-orbit coordinates reconstruct an S-invariant functional in the
original finite relaxation.

## PSD congruence

The V4 character map is

```text
(r_x, r_y) -> (r_x xor r_y, r_y).
```

Thus the trivial and Y character blocks are stable, while the X and Z
character blocks are exchanged.

On a stable block, S is a signed permutation matrix `R` with `R²=I`. Exact
integer columns

```text
e_i + s_i e_j,  e_i - s_i e_j
```

for a two-row orbit, together with signed fixed rows, form an invertible
congruence that separates the `+1` and `-1` eigenspaces. Invariant
coefficients make the off-diagonal eigenspace block exactly zero. The two
exchanged character blocks are exact signed-permutation congruences, so one
PSD representative is sufficient.

No orthonormalization or floating-point coefficient transformation is used.
All new block entries are formed over exact rationals before JuMP, MOF, or a
solver sees them.

For the degree-2 nine-site row inventory, the only fixed words are identity,
the nine single-Y words, and the 36 YY words. Hence the stable block splits
are:

| source block | exact split |
|---|---:|
| centered trivial, side 108 | 72 + 36 |
| scalar trivial, side 109 | 73 + 36 |
| centered Y, side 81 | 36 + 45 |
| scalar Y, side 81 | 36 + 45 |

One side-81 representative remains for each centered/scalar X--Z pair. The
three scalar gap blocks become one X--Z representative and one stable Y
block. The resulting prediction is 12 PSD blocks, maximum side 81, and
16,707 packed real-symmetric triangle entries.

## Fail-closed truth conditions

Before a derived MOF is accepted, the implementation checks:

1. exact Hamiltonian invariance;
2. closure and involutivity of every moment and row action;
3. all 31,810 source block coefficients for exact covariance;
4. every stable plus/minus cross entry for exact zero after quotient;
5. invariance of the complete affine-equality row space;
6. deterministic reconstruction of every new upper-triangle coefficient,
   moment inventory, block inventory, and assembly hash;
7. solver-free MOF reload counts, names, cone types, and side dimensions.

The gamma-zero numerical gate remains mandatory before gamma one-half is
solved in this representation.
