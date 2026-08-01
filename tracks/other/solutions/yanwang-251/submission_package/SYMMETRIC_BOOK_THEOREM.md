# A strict Rayleigh theorem on the symmetric `K4`-book slice

Let

```text
B_r = K3 join independent(r).
```

Give every non-designated core edge activity `p > 0` and every
non-designated core--leaf edge activity `q > 0`.  Designated-edge activities
are arbitrary and strictly positive; they cancel from the Rayleigh
difference.

## Theorem

For every `r >= 1` and every pair of distinct edges `e,f` of `B_r`,

```text
Delta_ef = Z_e Z_f - Z_ef Z > 0
```

on this two-parameter symmetric external-field slice.

This is not a proof that `B_r` is fully multivariate I-Rayleigh.  It proves
that a counterexample on this family must break core-edge or spoke symmetry.

## Five-state leaf transfer

Track only the partition induced on the three core vertices:

```text
S = 1|2|3
P = 12|3, 13|2, or 23|1
K = 123.
```

Writing `a = 1 + 3q`, one uniform leaf has transfer matrix

```text
       [ a  q^2 q^2 q^2 q^3  ]
       [ 0   a   0   0  2q^2 ]
M(q) = [ 0   0   a   0  2q^2 ].
       [ 0   0   0   a  2q^2 ]
       [ 0   0   0   0   a   ]
```

Thus `M = a I + N`, `N^3 = 0`, and

```text
M^n = a^n I + n a^(n-1) N + choose(n,2) a^(n-2) N^2.
```

The continuation partition functions after `n` leaves are

```text
K_n = a^n,
P_n = a^n + 2n a^(n-1) q^2,
S_n = a^n + n a^(n-1)(3q^2+q^3)
      + 3n(n-1) a^(n-2) q^4.
```

In particular,

```text
Z(B_r) = a^r(1+3p+3p^2)
         + r a^(r-1) q^2(3+q+6p)
         + 3r(r-1) a^(r-2) q^4.
```

For `S=S_n, P=P_n, K=K_n`, define

```text
U = P-K >= 0,
V = S-P >= 0,
R = P^2-SK = n q^2 a^(2n-2)(1+2q+nq^2) >= 0,
H = 3P^2+PK-4SK = 2n q^2(1+q)a^(2n-2) >= 0.
```

## The six edge-pair orbits

All expressions below use `Delta = BC-AD`, where `A,B,C,D` respectively sum
forests containing neither target, only `e`, only `f`, and both.

### Two core edges

Here `n=r`:

```text
A=S+pP,  B=C=P+pK,  D=K,
Delta_cc = R + pKP + p^2K^2 > 0.
```

Equivalently,

```text
Delta_cc = a^(2r-2) [
  r q^2(1+2q+r q^2) + pa(a+2r q^2) + p^2a^2
].
```

### Core edge and incident spoke

Here `n=r-1`:

```text
A=(1+2q)S +(2p+4pq+q^2)P +(p^2+2p^2q+pq^2)K,
B=(1+2q)P +(2p+4pq+q^2)K,
C=S +(2p+2q)P +(p^2+3pq+q^2)K,
D=P +(2p+q)K.
```

Direct expansion gives

```text
Delta_inc =
  q(R+P^2) + q^2(R+2P^2+PK)
  + p^2qK^2(5+9q) + 2pq^2K^2(1+3q) + q^4K^2
  + pqPK(5+9q) + 3q^3PK > 0.
```

### Core edge and opposite spoke

Again `n=r-1`:

```text
A=(1+2q)S +(2p+4pq+q^2)P +(p^2+2p^2q+2pq^2)K,
B=(1+2q)P +(2p+4pq)K,
C=S +(2p+2q)P +(p^2+2pq+q^2)K,
D=P +(2p+2q)K,
Delta_opp = 2qR + q^2H + 2pqK(pK+qK+P) > 0.
```

### Two spokes on the same leaf

Here `n=r-1`:

```text
A=(1+q)(S+3pP+3p^2K),
B=C=S+(q+3p)P+(2pq+3p^2)K,
D=P+(q+2p)K.
```

The positive decomposition is

```text
Delta_sl =
  p^2K^2(3p+q)^2 + 6p^3K(3P-K) + 3p^2qK(3P-K)
  + pq^2PK + p^2[6SK+9P(P-K)] + pq[2SK+3P(P-K)]
  + q^2R + p[6SP-2SK-3P^2] + qS(P-K) + S(S-P).
```

The only non-immediate bracket satisfies

```text
6SP-2SK-3P^2 >= P(3P-2K) > 0.
```

### Two spokes on different leaves

Let `n=r-2`, `ell=1+2q`, and

```text
A0 = ell^2(S+3pP+3p^2K) + 2q^2 ell P + 4pq^2 ell K,
B0 = ell S + (3p ell+2q+5q^2)P
     + (3p^2 ell+4pq+10pq^2+q^2+4q^3)K,
D0 = S+(3p+4q)P+(3p^2+8pq+4q^2)K.
```

For the same-core orbit, `A=A0`, `B=C=B0`, `D=D0`, and
`Delta_ds=q^2 Q_ds`, where

```text
Q_ds =
 p^2[36q^2K^2+36qK^2+10K^2+12KV]
+p[48q^3K^2+q^2(72K^2+36KU)
   +q(44K^2+36KU+32KV)+10K^2+10KU+12KV+12UV]
+16q^4K^2+q^3(32K^2+24KU)
+q^2(28K^2+36KU+16KV+9U^2)
+q(12K^2+24KU+12KV+12U^2+16UV)
+2K^2+6KU+4U^2+2KV+4UV+4V^2.
```

For different core endpoints,

```text
A=A0+q^4K,  B=C=B0-q^3K,  D=D0+q^2K,
Delta_dd=q^2 Q_dd,
```

with

```text
Q_dd =
 p^2[9q^2K^2+18qK^2+7K^2+12KV]
+p[12q^3K^2+q^2(33K^2+9KU)
   +q(26K^2+18KU+32KV)+7K^2+7KU+12KV+12UV]
+4q^4K^2+q^3(12K^2+6KU)
+q^2(13K^2+21KU+11KV+9U^2)
+q(6K^2+18KU+6KV+12U^2+16UV)
+K^2+5KU+4U^2+KV+4UV+4V^2.
```

Every displayed coefficient is nonnegative and each orbit has a strictly
positive term.

## Independent computational check

`verify_interface_certificates.py` assigns integer activities `p=2`, `q=3`,
enumerates all forests of `B_r` independently for `r=1,2,3,4`, and checks all
222 edge pairs.  The theorem itself is the algebraic transfer-matrix proof,
not this finite regression.

## Next construction forced by the proof

Repeating one triangular interface applies the same nilpotent transfer and
only adds positive terms on the symmetric slice.  The next search family
therefore uses inequivalent overlapping interfaces:

```text
G_{r,s}:
  core K4 on a,b,c,d;
  r simplicial vertices attached to face abc;
  s simplicial vertices attached to face abd.
```

The first target is `G_{3,3}` (`n=10`, `m=24`), with cross-book spoke pairs,
the opposite core pair `ac,bd`, and same-book spokes receiving feedback from
the other book.
