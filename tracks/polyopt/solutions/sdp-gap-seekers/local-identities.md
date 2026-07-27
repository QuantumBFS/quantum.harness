# Local spin identities for Square J1-J2

Scope: exact identities on at most four spin-1/2 sites, their role in a
state-polynomial relaxation, and exact machine checks. Write

```text
B_ij = S_i · S_j.
```

All equalities below follow from the spin-1/2 Pauli algebra. They do not assume
a ground state, a phase, a boundary condition, or a value of `g`.

## 1. Two-site bond

`B_ij` has singlet/triplet eigenvalues `-3/4` and `1/4`, so

```text
(B_ij + 3/4)(B_ij - 1/4) = 0,
B_ij² + 1/2 B_ij - 3/16 = 0.
```

The projectors are

```text
P_ij^(0) = 1/4 - B_ij,
P_ij^(1) = 3/4 + B_ij,
P_ij^(0) + P_ij^(1) = 1,
P_ij^(s) P_ij^(t) = δ_(s,t) P_ij^(s).
```

Classification:

- The equalities are redundant when Pauli canonicalization is complete through
  the required polynomial degree.
- They are valuable reducer regression tests.
- Positivity localizers `q†P_ij^(s)q ≥ 0` can tighten an incomplete structured
  basis when the rows needed to express `Pq` as an ordinary moment square are
  absent. A full two-site RDM PSD block subsumes these scalar projector
  positivity tests.

## 2. Three-site triangle introduced geometrically by J2

Two adjacent J1 edges plus one J2 diagonal form a triangle. For

```text
T_ijk = (S_i + S_j + S_k)²
      = 9/4 + 2(B_ij + B_jk + B_ik),
```

the possible total spins are `1/2` and `3/2`, hence

```text
(T_ijk - 3/4)(T_ijk - 15/4) = 0.
```

The total-spin projectors are

```text
P_(1/2) = (15/4 - T_ijk)/3,
P_(3/2) = (T_ijk - 3/4)/3.
```

These projectors are degree two in the spin generators and are natural
low-order positivity localizers for the frustrated geometry. Their polynomial
identities still follow from the same Pauli algebra; J2 creates a useful local
cluster but no new onsite algebra.

## 3. Four-site square plaquette

For sites ordered cyclically `(1,2,3,4)`, define

```text
T = (S_1+S_2+S_3+S_4)²,
E = B_12+B_23+B_34+B_41,
D = B_13+B_24.
```

Then

```text
T = 3 + 2(E+D).
```

Four spin-1/2 particles have total spin `S=0,1,2`, so `T` has eigenvalues
`0,2,6` and

```text
T(T-2)(T-6) = 0.
```

The projectors onto total-spin sectors are

```text
P_0 = (T-2)(T-6)/12,
P_1 = T(6-T)/8,
P_2 = T(T-2)/24.
```

They have ranks `2,9,5`, respectively. The rank greater than `2S+1` for
`S=0,1` records multiplicities of the same total-spin representation; these
projectors do not resolve those copies.

The Casimir polynomial has generator degree six. It is automatically present
only when the chosen quotient/moment truncation reaches that degree. The
projectors themselves have degree four, so imposing their positivity can be a
lower-order strengthening, especially for a structured basis. A full
four-site RDM PSD constraint is more systematic and stronger.

## 4. J2-aligned plaquette resolution

Let the two diagonals carry pair spins

```text
A = S_1+S_3,       B = S_2+S_4.
```

Then

```text
D = 1/2(A²+B²-3),
E = A·B = 1/2(T-A²-B²),
[E,D] = 0.
```

Therefore the local plaquette operator

```text
h_p(g) = E + gD
```

is resolved by `(s_A,s_B,S)`:

| `s_A,s_B,S` | sector dimension | `E` | `D` | `h_p(g)` |
|---|---:|---:|---:|---:|
| `0,0,0` | 1 | 0 | `-3/2` | `-3g/2` |
| `0,1,1` | 3 | 0 | `-1/2` | `-g/2` |
| `1,0,1` | 3 | 0 | `-1/2` | `-g/2` |
| `1,1,0` | 1 | `-2` | `1/2` | `-2+g/2` |
| `1,1,1` | 3 | `-1` | `1/2` | `-1+g/2` |
| `1,1,2` | 5 | `1` | `1/2` | `1+g/2` |

Products of diagonal bond projectors and `P_0,P_1,P_2` give six orthogonal
joint projectors with ranks `1,3,3,1,3,5`. This resolution is useful for:

- exact tests of the J1/J2 coefficient convention;
- symmetry-adapted four-site RDM blocks;
- local projector positivity constraints aligned with the diagonal
  frustration.

It is not valid to force the reduced state into the lowest `h_p(g)` sector:
the global frustrated ground state need not minimize each plaquette term.

## 5. Sum rules: what is and is not valid

For any finite set of `N` spins,

```text
S_total² = 3N/4 + 2 Σ_(i<j) B_ij.
```

Only the sum over **all pairs** becomes a constant after one explicitly fixes
a global total-spin sector:

```text
Σ_(i<j) B_ij = 1/2[S(S+1)-3N/4].
```

Consequences:

- The NN bond sum is not a constant.
- The NN+NNN bond sum is not a constant unless that set happens to contain
  every pair, which it does not on a general square patch.
- The plaquette edge sum `E` is not fixed even by total plaquette spin because
  the diagonal-pair multiplicities remain.
- The infinite-system KMS hierarchy does not fix a finite patch's global spin
  sector. Importing an ED singlet-sector sum rule would change the problem.

Translation or SU(2) invariance can relate expectation values, for example

```text
ω(S_i^a S_j^b) = δ_ab ω(B_ij)/3
```

in an SU(2)-invariant state. These are optional state-symmetry constraints, not
operator identities and not valid in the unrestricted hierarchy.

## 6. Tightening priority

Recommended order:

1. Always canonicalize the exact Pauli algebra; use the bond identities as
   mandatory reducer tests.
2. For a structured low-order basis, add two-site RDM/projector positivity.
3. Add triangle total-spin projector positivity because J2 produces
   J1-J1-J2 triangles.
4. Add a four-site plaquette RDM block or the six J2-aligned joint projector
   localizers when memory permits.
5. Do not add fixed local-spin-sector equalities or NN bond “constants.”

If a purported extra equality is already reduced to zero by the Pauli
canonicalizer at the represented degree, adding it again only increases affine
constraint count and cannot legitimately tighten the relaxation.

## 7. Exact machine check

`src/LocalSpinIdentities.jl` constructs two-, three-, and four-spin matrices
over exact complex rationals. `scripts/check_local_identities.jl` verifies:

- bond minimal polynomial and projectors;
- triangle Casimir polynomial and projectors;
- plaquette Casimir polynomial and total-spin projectors;
- `T=3+2(E+D)` and `[E,D]=0`;
- the six-projector J2-aligned spectral resolution of `h_p(g)`.

No floating-point diagonalization is used.

Run:

```bash
julia --startup-file=no \
  tracks/polyopt/solutions/sdp-gap-seekers/scripts/check_local_identities.jl
```
