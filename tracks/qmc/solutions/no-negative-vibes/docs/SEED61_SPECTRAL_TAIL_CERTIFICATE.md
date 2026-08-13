# Seed-61 stable spectral tail certificate

## Result

For the gauge-fixed seed-61 atom

```text
B = [[1,    3/8,  0,     0,     0],
     [0,    1,    1/4,   0,     0],
     [0,    0,    1,     13/12, 0],
     [0,    0,    0,     1,     11/96],
     [77/96,77/256,0,     0,     1]]
```

and every word `w` in `{B,B^T}*` of length at least 24, order the
eigenvalues by decreasing modulus.  The exact certificate proves

```text
|lambda_4(w)| < 1.
```

Consequently the stable pair `{lambda_4,lambda_5}`, if real and negative,
lies entirely in `(-1,0)`.  Its factor

```text
(1 + lambda_4)(1 + lambda_5)
```

is therefore positive.

This is one half of the desired long-word determinant theorem.  It does not
control the remaining quadratic factor associated with
`{lambda_2,lambda_3}` and must not be reported as a proof of
`det(I+w)>0`.

## Why the spectrum splits into two pairs

The gauge-fixed `B` and `B^T` are entrywise nonnegative.  Their third
compound matrices are also entrywise nonnegative.  Exact finite enumeration
in the certificate shows:

- every four-letter one-particle product is strictly positive;
- every three-letter third-compound product is strictly positive.

Positivity persists after multiplication by either atom.  Perron--Frobenius
therefore gives, for every word of length at least four,

```text
lambda_1 > 0,
|lambda_1| > |lambda_2|,
lambda_1 lambda_2 lambda_3 > 0,
|lambda_3| > |lambda_4|.
```

Because the characteristic polynomial is real and `det(w)=1`, the spectrum
has the real blocks

```text
[lambda_1] [lambda_2,lambda_3] [lambda_4,lambda_5],
```

where each two-dimensional block is either a conjugate pair or two real
eigenvalues with positive product.

## Exact weighted block bound

Let `C_3(s)=Lambda^3(B_s)` and `C_4(s)=Lambda^4(B_s)` for a word `s`.
Use the fixed integer weights

```text
d_4 = (545184,1853704,1809811,822488,664742)

l_3 = (892037,831964,595034,1329636,938155,
       788316,986631,1041039,1971566,1137182).
```

For a matrix `A`, define the weighted induced one-norm

```text
||A||_(1,d) = max_j sum_i d_i |A_ij| / d_j.
```

For a nonnegative matrix `C`, define the positive-cone conorm

```text
m_(1,l)(C) = min_j sum_i l_i C_ij / l_j.
```

Both bounds are multiplicative in the required direction:

```text
||A A'||_(1,d) <= ||A||_(1,d) ||A'||_(1,d),
m_(1,l)(C C') >= m_(1,l)(C) m_(1,l)(C').
```

Exact integer enumeration of all `2^10` ten-letter blocks gives

```text
U = max_s ||C_4(s)||_(1,d_4),
L = min_s m_(1,l_3)(C_3(s)),
```

with the extremal words

```text
upper: 1010110111
lower: 0000000000
```

and

```text
U/L =
140069234893420513349411826255996828139180583377937872380734577296116865537995
/
200200542368656762406096089328573547753146738147263530057688153284699104477184

= 0.699644632507996... < 1.
```

All arithmetic uses integers and `fractions.Fraction`; there is no
floating-point acceptance gate.

## Residues and the cutoff

Write a length as `10m+r`, with `0 <= r < 10`.  For each residue, the same
exact enumeration computes

```text
C_r =
max_(|s|=r) ||C_4(s)||_(1,d_4)
/
min_(|s|=r) m_(1,l_3)(C_3(s)).
```

The table lists the smallest `m` for which the exact rational inequality
`C_r (U/L)^m < 1` holds.

| `r` | `C_r` (decimal display only) | blocks `m` | first certified length |
|---:|---:|---:|---:|
| 0 | 1.000000 | 1 | 10 |
| 1 | 1.576307 | 2 | 21 |
| 2 | 1.831384 | 2 | 22 |
| 3 | 1.729440 | 2 | 23 |
| 4 | 1.548853 | 2 | 24 |
| 5 | 1.325926 | 1 | 15 |
| 6 | 1.102270 | 1 | 16 |
| 7 | 0.989257 | 1 | 17 |
| 8 | 0.870412 | 1 | 18 |
| 9 | 0.782450 | 1 | 19 |

Thus every length at least 24 satisfies the bound.  Indeed,

```text
rho(C_4(w)) <= ||C_4(w)||_(1,d_4),
rho(C_3(w)) >= m_(1,l_3)(C_3(w)),
```

and the strict order-three Perron splitting gives

```text
rho(C_4(w)) / rho(C_3(w)) = |lambda_4(w)| < 1.
```

## Why a stronger naive tail criterion cannot work

The word `q=B^T B^11` is strictly positive but has two non-Perron real
eigenvalues approximately

```text
-13.988974239...,  -3.774044480....
```

Exact characteristic-polynomial signs isolate them in `(-14,-13)` and
`(-4,-3)`.  Every odd power of `q` therefore supplies arbitrarily long words
with non-Perron real eigenvalues below `-1`.  A successful proof cannot aim
to put every non-Perron real eigenvalue above `-1`; it must keep the two
negative eigenvalues in each spectral pair on the same side of `-1`.

After the stable-band result above, the only remaining long-word condition is

```text
h_+(w) =
1 + (lambda_2 + lambda_3) + lambda_2 lambda_3 > 0.
```

The reproducible certificate is
`oracle.exterior_seed61_spectral_tail.audit_seed61_stable_band_tail`.
