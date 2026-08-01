# Interface-width barriers and finite-layer escape in weighted random forests

## Abstract

Let `I_G` be the multivariate generating polynomial of all forests of a
finite graph.  The open I-Rayleigh problem asks whether two distinct edges
are negatively correlated under every positive external field.  We isolate
three exact structural facts relevant to a counterexample search.  First,
every positive two-terminal network inserted through a two-sum is only an
effective activity substitution, and hence cannot reverse a Rayleigh sign.
Second, forest signatures on three shared terminals satisfy an explicit
composition identity that preserves nonpositivity.  Third, this closure
fails at four terminals in the ambient positive partition-signature cone: we
give two positive integer signatures which are individually nonpositive for
all three disjoint target matchings but whose composition is strictly
positive for all three.  We also formulate an exposed-face reduction showing
that a minor-minimal counterexample cannot first arise from one monomial
asymptotic phase.  A finite witness, if it exists, must exploit finite-scale
interference between layers, and four terminals are the first interface
width at which the abstract composition algebra permits the sign reversal.

## 1. Sign convention

Delete two designated edges `e,f` and write the forest polynomial as

```text
I_G = A + x B + y C + x y D,
```

where `x,y` are the two designated activities.  The designated activities
cancel from the correlation sign.  Negative correlation is equivalent to

```text
B C - A D >= 0.
```

Throughout this note we use the reversed determinant

```text
R = A D - B C.
```

Thus a counterexample to issue #251 requires `R>0`.

## 2. Two-terminal networks are scalar activity substitutions

For a matroid `M` and element `g`, write

```text
I_M = I_M^g + y_g I_{M,g},
```

where `I_M^g` is the deletion polynomial and `I_{M,g}` is the contraction
coefficient.  Let matroids `M,N` meet only in a common nonloop, noncoloop `g`
and delete `g` after gluing.  Direct classification of independent sets gives

```text
I_{M +_2 N}
  = I_M^g I_{N,g} + I_{M,g} I_N^g - I_{M,g} I_{N,g}

  = I_{N,g} [ I_M^g
      + ((I_N^g-I_{N,g})/I_{N,g}) I_{M,g} ].
```

At positive activities, both `I_{N,g}` and
`I_N^g-I_{N,g}` are nonnegative, and the former is strictly positive.  The
bracket is exactly `I_M` evaluated at the effective activity

```text
y_g^eff = (I_N^g-I_{N,g}) / I_{N,g} >= 0.
```

For a nondegenerate positive network the effective activity is positive.
Consequently, when both targets lie in `M`, the resulting Rayleigh
determinant is the determinant of `M` at `y_g^eff`, multiplied by the square
of a common positive factor.  When the targets lie on opposite sides, the
standard two-sum expansion factors through the two side determinants.

This recovers the known closure of I-Rayleigh matroids under two-sums, but it
also gives the following search-specific conclusion.

**Two-terminal amplifier obstruction.**  Series stretching, parallel
thickening, subdivision, and arbitrary finite positive two-terminal graph
replacement cannot turn a nonpositive source into a positive issue-251
determinant.  Such a gadget changes an activity; it does not select a forest
cardinality layer.

## 3. A single exposed phase cannot be the first counterexample

Let every non-target activity scale as

```text
beta_h(T) = c_h T^(a_h),  c_h>0.
```

Let `d_A,d_B,d_C,d_D` be the leading degrees in the four target sectors.  A
necessary condition for the leading terms of `AD` and `BC` to compete is

```text
d_A+d_D = d_B+d_C.
```

Assign target valuations

```text
a_e=d_A-d_B,  a_f=d_A-d_C.
```

Then all four sectors occur in one initial form of the graphic-matroid
independence polynomial.  On every nonzero valuation block, the greedy
decomposition of a matroid-polytope face produces bases of delete/contract
minors, with loops and coloops accounting for forced elements.  The initial
form is therefore a monomial times a product of weighted basis polynomials of
graphic minors.  Those basis polynomials are real stable and hence Rayleigh,
so the aligned leading determinant is nonpositive for arbitrary positive
amplitudes `c_h`.

If the adjusted valuation has a zero block, an independent-set polynomial of
a delete/contract minor remains.  A positive leading determinant must then
already be a counterexample in that smaller minor.

**Exposed-face corollary.**  In a minor-minimal counterexample, no single
exposed Newton face has positive Rayleigh determinant.  The first sign
reversal must be a finite-scale interaction of at least two adjacent layers.

This is not a proof of the I-Rayleigh conjecture: a sum of individually
nonpositive phase contributions need not remain nonpositive because of cross
terms between phases.

## 4. Three terminals: an exact no-go identity

Remove adjacent targets `uv,uz`.  A forest of the remaining graph induces one
of five connectivity partitions on `u,v,z`.  Denote their positive total
weights by

```text
p = u|v|z,  q = uv|z,  r = uz|v,  s = vz|u,  t = uvz.
```

Adding neither target, only `uv`, only `uz`, or both gives

```text
A=p+q+r+s+t,  B=p+r+s,  C=p+q+s,  D=p,
```

and hence

```text
R = AD-BC = p(t-s) - (r+s)(q+s).
```

Let two graph modules `x,y` share only the three terminals and otherwise have
disjoint edges and vertices.  Their forest signatures compose by joining
compatible terminal partitions; pairs whose union creates a cycle are
discarded.  Expanding the five resulting coordinates gives

```text
R(x*y)
 = p_x^2 R(y) + p_y^2 R(x) - 2 p_x p_y s_x s_y.
```

All weights on the right are nonnegative.  Therefore `R(x)<=0` and
`R(y)<=0` imply `R(x*y)<=0`.  For `n` parallel copies of one module,

```text
R_n = n p^(2n-2) [ R_1 - (n-1)s^2 ] <= 0.
```

The bundled verifier constructs the complete five-state composition tensor
and compares every integer coefficient of the two resulting biquadratic
polynomials.  This is an exact symbolic certificate of the identity.

## 5. Four terminals: exact abstract escape

For disjoint targets on four boundary vertices, a deleted forest has one of
the 15 set-partition states.  Composition is the fixed bilinear map obtained
by joining two compatible partitions.  Use the restricted-growth ordering
generated lexicographically by `verify_interface_certificates.py` and define

```text
X = (69,74,58,54,6,87,17,18,38,76,1,35,34,3,61),
Y = (72,57,58,29,3,17,72,90,16,6,79,89,81,11,24).
```

Every entry is a positive integer.  Before composition their exact reversed
gaps for the three perfect matchings are

| signature | `01|23` | `02|13` | `03|12` |
|---|---:|---:|---:|
| `X` | -32,521 | -71,096 | -51,330 |
| `Y` | -20,413 | -19,316 | -67,112 |

Thus each signature is nonpositive for every disjoint target matching.
Nevertheless their identity-boundary composition has

| matching | `A` | `B` | `C` | `D` | `AD-BC` |
|---|---:|---:|---:|---:|---:|
| `01|23` | 176,722 | 53,877 | 58,496 | 24,255 | 1,134,803,118 |
| `02|13` | 176,722 | 45,125 | 44,283 | 13,646 | 413,278,037 |
| `03|12` | 176,722 | 45,172 | 53,955 | 14,213 | 74,494,526 |

This proves that four-terminal global information is sufficient to reverse
the sign in the unrestricted positive signature cone.  It does **not** prove
that `X` or `Y` is the signature of a positive-weight graph module.  Graphic
realizability is precisely the remaining obstruction.

## 6. A strict symmetric-book slice

Let

```text
B_r = K3 join independent(r).
```

Give every non-designated core edge activity `p>0` and every
non-designated core-to-leaf edge activity `q>0`.  Designated activities are
arbitrary and cancel from the sign.

**Symmetric-book theorem.**  For every `r>=1` and every pair of distinct
edges `e,f` of `B_r`,

```text
Z_e Z_f - Z_ef Z > 0
```

on this two-parameter activity slice.

The proof is a five-state transfer calculation on the three core vertices.
The complete orbit-by-orbit positive decompositions are supplied in
`SYMMETRIC_BOOK_THEOREM.md`.  The bundled verifier independently enumerates
all forests for `r=1,2,3,4` at integer activities and checks every edge pair.
The finite enumeration is a regression; the symbolic transfer decomposition
is the proof for arbitrary `r,p,q`.

## 7. Consequence for the search geometry

The results distinguish three interface regimes:

```text
two terminals    effective scalar activity; no sign escape
three terminals  five-state algebra with a negative correction; no escape
four terminals   15-state algebra permits exact positive crossover
```

Together with the exposed-face corollary, this points to a sharply defined
remaining problem: realize, or closely approach along a curved interior path,
a positive four-terminal crossover using actual graph forest signatures.
More extreme one-scale weights and more two-/three-terminal replication
cannot supply the missing mechanism.

## 8. Limitations

1. No graph with `AD-BC>0` is produced.
2. The four-terminal vectors are abstract positive signatures; their graphic
   realizability is open.
3. The symmetric-book theorem concerns a grouped two-parameter slice, not
   arbitrary independent activities on that topology.
4. The exposed-face statement is a minimal-counterexample reduction, not
   global nonpositivity of the full signomial.

## References

- D. G. Wagner, *Negatively correlated random variables and Mason's
  conjecture*, Annals of Combinatorics 12 (2008), 211-239.
- M. Erickson, *Sums of squares and negative correlation for spanning
  forests of series parallel graphs*, arXiv:1008.3660.
- J. Borcea, P. Branden, and T. M. Liggett, *Negative dependence and the
  geometry of polynomials*, Journal of the AMS 22 (2009), 521-567.
- X. Huang, *On Negative Correlation of Arboreal Gas on Some Graphs*,
  arXiv:2311.00965.
- QuantumBFS/quantum.harness#213, *Stable incident-edge marginals for
  weighted forests*, complementary adjacent-edge result by @Osgood001.
