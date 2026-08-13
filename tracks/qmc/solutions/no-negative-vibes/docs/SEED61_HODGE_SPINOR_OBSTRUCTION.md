# Seed-61 Hodge/spinor cone audit

## Verdict

The canonical Hodge, particle-hole, and Spin\((5,5)\) structures do not
produce a proper trace-positive cone for the fixed seed-61 pair by
themselves.  They do give an exact and useful reduction:

\[
\Gamma(B)\simeq \operatorname{diag}(E,E^{-T}),\qquad
\Gamma(B^T)\simeq \operatorname{diag}(E^T,E^{-1}),
\]

where

\[
E=\Lambda^{\mathrm{even}}B
 =\Lambda^0B\oplus\Lambda^2B\oplus\Lambda^4B
\]

has dimension \(16\).  The obstruction is that the associated Mukai form
has split inertia \((16,16)\), the natural Hodge orthant has an exact
two-entry sign conflict, and even the paired
\((\Lambda^1,\Lambda^4)\) trace becomes negative at \(B^7\).  Therefore a
successful proof must couple the \((1,4)\) and \((2,3)\) particle-hole
pairs; pairing complementary grades separately is insufficient.

This does not rule out a different nonpolyhedral cone with that required
cross-pair coupling.

## Exact Hodge block transform

Use increasing-grade lexicographic exterior bases.  For an even subset
\(I\subset\{0,\ldots,4\}\) and an odd subset \(J\), define

\[
H_{I,J}=
\begin{cases}
\operatorname{sgn}(I,J),&J=I^c,\\
0,&J\ne I^c,
\end{cases}
\]

where \(\operatorname{sgn}(I,J)\) is the sign of
\(e_I\wedge e_J=e_0\wedge\cdots\wedge e_4\).  Thus \(H\) is a signed
permutation and \(HH^T=I_{16}\).

Let \(O=\Lambda^{\mathrm{odd}}B\).  Functoriality of the top wedge and
\(\det B=1\) give the exact identity

\[
\boxed{E^T H O=H}.
\]

After replacing the odd coordinate \(o\) by its Hodge dual \(y=Ho\), the
two atoms act as

\[
G_0=\begin{pmatrix}E&0\\0&E^{-T}\end{pmatrix},\qquad
G_1=\begin{pmatrix}E^T&0\\0&E^{-1}\end{pmatrix}=G_0^T.
\]

In self/anti coordinates \(u=(x+y)/\sqrt2\),
\(v=(x-y)/\sqrt2\), the first atom is

\[
\boxed{
M_0=\frac12
\begin{pmatrix}
E+E^{-T}&E-E^{-T}\\
E-E^{-T}&E+E^{-T}
\end{pmatrix}},\qquad M_1=M_0^T.
\]

The module replays every identity over the rationals.

## Why the Mukai form is not a Lorentz cone

In \((x,y)\) coordinates the invariant top-wedge form is

\[
Q(x,y)=2x^Ty.
\]

In \((u,v)\) coordinates it becomes

\[
Q(u,v)=\lVert u\rVert^2-\lVert v\rVert^2,
\]

so its inertia is \((16,16)\), not \((1,31)\).  Its positive locus has no
two-sheeted “future” component: because the positive index exceeds one,
\((u,0)\) can be rotated continuously to \((-u,0)\) while \(Q>0\).
Adding a linear orientation does not repair convexity.  For example,

\[
\begin{aligned}
u_1&=e_0+2e_1,&v_1&=2f_0,\\
u_2&=e_0-2e_1,&v_2&=2f_0
\end{aligned}
\]

both have \(Q=1\) and positive \(e_0\)-coordinate, whereas their sum has
\(Q=4-16=-12\).  Hence the natural Spin\((5,5)\) quadratic locus is not a
proper convex cone.

## Exact orthant obstructions

The self/anti matrix \(M_0\) has 122 negative entries.  More decisively,
in the Hodge-paired even-subset coordinates,

\[
(M_0)_{+:01,\,+:02}=-\frac{62717}{589824},\qquad
(M_0)_{+:02,\,+:01}=\frac18.
\]

A diagonal sign gauge multiplies both entries by the same sign.  It cannot
make both \(M_0\) and \(M_1=M_0^T\) nonnegative.

A particle-hole transformation and a Jordan--Wigner reordering act on the
occupation basis by a signed permutation.  Such a similarity only
permutes reciprocal-entry products.  In the original Fock matrix,

\[
\Gamma(B)_{k2:13,\,k2:24}=-\frac{11}{384},\qquad
\Gamma(B)_{k2:24,\,k2:13}=\frac{1001}{3072}.
\]

Their product is negative, so no particle-hole/Jordan--Wigner signed
occupation basis makes both transpose-paired atoms entrywise nonnegative.

## Complementary-grade trace obstruction

For every determinant-one word \(W\), Hodge duality gives

\[
\operatorname{tr}\Lambda^{5-k}W
=\operatorname{tr}(\Lambda^kW)^{-1}.
\]

Thus the full trace can be regrouped as

\[
\det(I+W)
=2+\chi_{14}(W)+\chi_{23}(W),
\]

with

\[
\chi_{14}=\operatorname{tr}W+\operatorname{tr}W^{-1},\qquad
\chi_{23}=\operatorname{tr}\Lambda^2W+
           \operatorname{tr}(\Lambda^2W)^{-1}.
\]

At the valid word \(W=B^7\), exact arithmetic gives

\[
\chi_{14}(B^7)=
-\frac{
2637203457670395078041392722514295103565195
}{
3178828148885691643853424575651009708163072
}<0,
\]

while

\[
\chi_{23}(B^7)=
\frac{
140780460557849141078414587008569
}{
2284347543117575620391199571968
}>0
\]

and

\[
\det(I+B^7)=
\frac{
199626234419917700768513242993680430182814325
}{
3178828148885691643853424575651009708163072
}>0.
\]

Therefore no standalone trace-positivity argument for the \((1,4)\) pair
can prove the result.  The observed positivity already needs compensation
from the \((2,3)\) pair.

## Focused next move

Do not continue with a generic 32-dimensional cone search.  The reduced
target is the seed-specific character inequality

\[
\boxed{\chi_{23}(W)\ge -2-\chi_{14}(W)}
\qquad\text{for }W\in\{B,B^T\}^*.
\]

The next structured calculation should use the positive one-body gauge
\(\widetilde B=DBD\) and its five fixed rational cyclic-shear factors to
seek either:

1. an invariant dominance cone coupling only the \(10+10\)
   \((2,3)\) block to the \(5+5\) \((1,4)\) block; or
2. a direct recursion/SOS certificate for the displayed character
   inequality.

Either route has to encode cross-pair dominance explicitly.  A cone or
form that remains block diagonal in the three Hodge pairs is now exactly
excluded.

## Reproduction

From `tracks/qmc/solutions/no-negative-vibes` run

```powershell
python -m pytest tests\test_exterior_seed61_hodge_spinor.py -q
```

The implementation is
`oracle/exterior_seed61_hodge_spinor.py`; its two tests cover the exact
Mukai/sign obstructions and the exact \(B^7\) paired-trace witness.
