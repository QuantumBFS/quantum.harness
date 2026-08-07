# Seed-61 top-pair product tail certificate

## Result

For the positive gauge of the seed-61 pair `B,B^T`, order the eigenvalues
of a word `w` by decreasing modulus.  Exact weighted block bounds prove

```text
p(w) = lambda_2(w) lambda_3(w) > 1
```

for every word of length at least 18.

Together with the independent stable-band result
`|lambda_4(w)| < 1` from length 24, this proves

```text
(1 + lambda_2(w))(1 + lambda_3(w)) > 0
```

for every word of length at least 24 in the signed branch

```text
tr(w) - rho(w) >= 0.
```

This is a conditional top-band result.  The branch
`tr(w)-rho(w) < 0` remains to be certified before these tail results can be
reported as a proof of `det(I+w)>0`.

## Perron quotient

Every four-letter one-particle product and every three-letter third
compound product is strictly positive.  Perron--Frobenius and the strict
modulus gaps therefore give

```text
rho(w) = lambda_1(w),
rho(Lambda^3(w)) = lambda_1(w) lambda_2(w) lambda_3(w).
```

Consequently

```text
p(w) = rho(Lambda^3(w)) / rho(w).
```

It is enough to prove that a weighted upper bound for `rho(w)` is smaller
than a positive-cone conorm for `rho(Lambda^3(w))`.

## Exact five-block bound

Use the fixed positive integer weights

```text
d_1 = (555238,644059,2025872,2010441,686581)

l_3 = (915676,787059,569210,1342330,926592,
       859950,1005198,1005675,1938371,1163083).
```

For a matrix `A` and a nonnegative matrix `C`, respectively, define

```text
||A||_(1,d) = max_j sum_i d_i |A_ij| / d_j,
m_(1,l)(C) = min_j sum_i l_i C_ij / l_j.
```

Exact enumeration of all `2^5` five-letter blocks gives the extremal words

```text
upper: 11010
lower: 00001
```

and

```text
max ||w||_(1,d_1) / min m_(1,l_3)(Lambda^3(w))

= 45809663718420017101544620032000
  / 51474730402860830203560494083391

= 0.889944704127562... < 1.
```

All acceptance inequalities use integers and `fractions.Fraction`.

## Exact residue cover

Write the length as `5m+r`, with `0 <= r < 5`.  Exact enumeration at each
residue gives the following smallest successful block counts.

| `r` | residue factor (decimal display only) | blocks `m` | first certified length |
|---:|---:|---:|---:|
| 0 | 1.000000 | 1 | 5 |
| 1 | 1.504876 | 4 | 21 |
| 2 | 1.451007 | 4 | 22 |
| 3 | 1.328610 | 3 | 18 |
| 4 | 1.077506 | 1 | 9 |

For each residue, every later length with that residue is also certified.
The last potentially uncovered same-residue lengths are therefore
`0,16,17,13,4`.  Their maximum is 17, so every length at least 18 is
covered.

## The nonnegative-trace branch

Set

```text
A = tr(w) - rho(w),
p = lambda_2 lambda_3,
theta = |lambda_4|,
u = lambda_2 + lambda_3,
v = lambda_4 + lambda_5.
```

The real spectral splitting gives `A=u+v`, while modulus ordering gives
`v <= |lambda_4|+|lambda_5| <= 2 theta`.  Hence

```text
(1+lambda_2)(1+lambda_3)
  = 1 + p + u
  = 1 + p + A - v
 >= 1 + p + A - 2 theta.
```

For length at least 24, the exact certificates give `p>1` and `theta<1`.
If also `A>=0`, the right-hand side is strictly positive.

The reproducible entry point is
`oracle.exterior_seed61_top_product_tail.audit_seed61_top_product_tail`.
