# Exact cones for the fixed symmetric-oddcycle candidate

Fix

\[
B=\begin{pmatrix}
0&0&2&0&0\\
2&0&0&0&0\\
0&2&0&1&0\\
0&0&0&1&1\\
0&0&-1&0&1
\end{pmatrix},
\qquad {\cal G}=\{B,B^{\mathsf T}\}.
\]

For a word \(W\in\langle{\cal G}\rangle\), write
\(\chi_k(W)=\operatorname{tr}(\wedge^kW)\).  The statements below are
exact lemmas, not floating-point observations.

## Lemma 1: a symbolic grade-four cone

In the lexicographic basis of \(\wedge^4\mathbb R^5\), let
\(D=\operatorname{diag}(1,1,1,-1,1)\).  For the two-parameter matrix in
the same sparsity pattern, direct minor expansion gives

\[
D(\wedge^4B(x,y))D=
\begin{pmatrix}
x^3&x^3y&0&x^2y^2&0\\
0&x^3&0&x^2y&0\\
0&0&0&x^2&0\\
0&0&0&0&x^2\\
x^2y&x^2y^2&x^2&xy^3&0
\end{pmatrix}.
\]

The transformed transpose atom is the transpose of this matrix.  Hence
both atoms are entrywise nonnegative for \(x,y>0\), so
\(\chi_4(W)\geq0\) for every word.  This lemma does not assert that the
whole two-parameter family is sign-free.

## Lemma 2: fixed rational simplicial cones

For \(B=B(2,1)\), the stored rational transforms replay exactly:

- a 10-dimensional cone for
  \(\wedge^1B\oplus\wedge^4B\), proving
  \(\chi_1(W)+\chi_4(W)\geq0\);
- a 15-dimensional cone for
  \(\wedge^2B\oplus\wedge^4B\), proving
  \(\chi_2(W)+\chi_4(W)\geq0\).

For either grade set \(K\), the verifier constructs the exact block atoms
\(A_i=\bigoplus_{k\in K}\wedge^k B_i\), reads a rational invertible
matrix \(S\), and checks every entry of \(S^{-1}A_iS\) is nonnegative.
Trace invariance then gives
\(\sum_{k\in K}\chi_k(W)=\operatorname{tr}(S^{-1}A_WS)\geq0\) for every
word.

The compact certificate SHA-256 values are:

- grades \(\{1,4\}\):
  `f13915705d792899cb36580f67bc36dae691ee33f6fba989e090f979cef81f5a`;
- grades \(\{2,4\}\):
  `af9b881a5cc6e6065d58f4588e2631fc46a692391feb829a25757b90334f4264`.

## Remaining theorem gap

These lemmas do not yet prove
\(\det(I+W)=\sum_{k=0}^5\chi_k(W)\geq0\).  In particular, a cone for
grades \(\{2,3\}\) is impossible: at \(W=B^7\),

\[
\chi_2(W)=13875,\qquad
\chi_3(W)=-171633,\qquad
\chi_2(W)+\chi_3(W)=-157758.
\]

The positive scalar sectors must therefore participate in the remaining
bound.  With the first cone, the natural exact target is the complementary
sum \(\chi_0+\chi_2+\chi_3+\chi_5\); with the second cone it is
\(\chi_0+\chi_1+\chi_3+\chi_5\).

## Lemma 3: exact self-dual form of the complementary sum

For every invertible \(5\times5\) matrix \(W\), Jacobi's complementary
minor identity gives

\[
\chi_3(W)=\det(W)\chi_2(W^{-1}).
\]

Every letter has determinant \(8\).  Thus a length-\(n\) word obeys

\[
F(W):=\chi_0+\chi_2+\chi_3+\chi_5
=1+8^n+\chi_2(W)+8^n\chi_2(W^{-1}).
\]

Equivalently, \(F\) is the character of the determinant-normalized
self-dual representation
\(\wedge^0\oplus\wedge^2\oplus\wedge^3\oplus\wedge^5\).
This is the exact form in which a global path pairing or a norm bound must
use the vacuum and full sectors.

A tempting stronger statement is false: the ten pairs of complementary
principal minors are not individually nonnegative.  For \(W=B\), the
\(\{0,1\}\) minor is \(0\) and its \(\{2,3,4\}\) complement is \(-1\).
For \(W=B^2\), the pairs indexed by
\(\{0,3\}\leftrightarrow\{1,2,4\}\) and
\(\{1,4\}\leftrightarrow\{0,2,3\}\) both sum to \(-8\).
Consequently, a proof cannot be a direct termwise complementary-minor or
unsigned LGV pairing.

The two middle sectors also cannot be separated.  Besides the pure-power
grade-\((2,3)\) obstruction above, the mixed word `0001010101` has the
exact values

\[
\chi_2=-1307360,\quad
\chi_3=5656076689,\quad
\chi_5=1073741824,\quad
F=6728511154.
\]

For comparison, the global scalar compensation is visible already in pure
powers:

\[
F(B^7)=1939395,\qquad F(B^{10})=882341964,
\]

even though \(\chi_3(B^7)=-171633\) and
\(\chi_3(B^{10})=-192388191\).  Any successful network identity must
therefore pair signed paths across different principal minors and particle
numbers; local nonnegativity is exactly obstructed by the examples above.

The exact grade-\((2,4)\) cone does not permit a smaller independent
odd-sector proof.  For the length-30 word

```text
101010110111111111111110101010
```

the exact odd complement is

\[
\chi_1+\chi_3+\chi_5
=-2247244599871205847393995794<0,
\]

with

\[
\begin{aligned}
\chi_1&=-5189582451,\\
\chi_3&=-3485184639156586117103537567,\\
\chi_5&=1237940039285380274899124224.
\end{aligned}
\]

The even part
\(\chi_0+\chi_2+\chi_4
=4272808041188297984567253760751379\)
still dominates, giving the positive full determinant
\(4272805793943698113361406366755585\).
Thus the existing grade-\((2,4)\) certificate plus a separate
grade-\((1,3,5)\) cone is impossible.  A successful certificate must
couple the even and odd parities (or prove a quantitative domination
inequality between them).

The other stored cone does not yield a partition proof either.  For

```text
101010101111111111111110101010
```

the complement of the exact grade-\((1,4)\) cone is

\[
\chi_0+\chi_2+\chi_3+\chi_5
=-3142487109366266808212314180.
\]

The certified grade-\((1,4)\) character is instead
\(4001439983856051764947534417243269\), so the complete determinant
remains positive at
\(4001436841368942398680726204929089\).
Therefore neither stored cone can be detached from its negative
complement.  The remaining routes are a full-Fock cone or a direct
quantitative domination certificate across the proposed split.

### The invariant sign chamber is not sufficient

The two directed triangles have cycle invariants \(D=8\) and \(T=-z\)
when the sole negative edge is changed from \(-1\) to \(-z\).  Exact
expansion of the four-letter pure word gives

\[
F(B(z)^4)=z^4-32z^3+268z^2-3000z+8194.
\]

Both \(z=3\) and \(z=4\) lie strictly inside the same sign chamber
\(0<z<D\), or equivalently \(-D<T<0\), but

\[
F(B(3)^4)=823>0,\qquad F(B(4)^4)=-1310<0.
\]

Therefore the cycle signs, their shared vertex, and the strict inequality
\(|T|<D\) do not make the detached complementary sector \(F\)
nonnegative.  This is an obstruction to the grade-\((1,4)\)-cone-plus-
complement proof, not a counterexample to the full determinant: exact
expansion instead gives

\[
\det(I+B(z)^4)=z^4-32z^3+396z^2+3136z+16388,
\]

which equals \(28577\) at \(z=3\) and \(33476\) at \(z=4\).  A theorem for
the full fixed \(z=1\) atom may therefore use quantitative domination by
the certified grade-\((1,4)\) sector; it cannot infer positivity of \(F\)
from only the two invariant signs.

### Exact unit-winding Bernstein lemma through depth 12

There is nevertheless a sharper finite exact statement at the fixed
negative-edge scale.  Give every letter the same variable negative edge
\(-z\), \(0\leq z\leq1\), and call the resulting complementary character
\(F_w(z)\).  Every compound atom is affine in the negative-edge amplitude
of its own time layer: a minor can use that one matrix entry at most once.
After setting all layer amplitudes equal to \(z\), write

\[
F_w(z)=\sum_{k=0}^{n} b_{w,k}
\binom{n}{k}z^k(1-z)^{n-k}.
\]

Pure integer-polynomial enumeration of every nonempty binary orientation
word through length 12 checked 8,190 words and 98,304 coefficients.  Every
\(b_{w,k}\) is nonnegative; the exact global minimum is \(17\), attained
at the one-letter word `0`, coefficient index 1.  Hence every tested word
is positive throughout the complete interval \(0\leq z\leq1\), rather
than only at the endpoint \(z=1\).

This is a finite-depth lemma, not the arbitrary-word theorem.  Its useful
structural content is that \(b_{w,k}\) averages the four endpoint atoms
(orientation \(B/B^{\mathsf T}\), winding amplitude \(0/1\)) over choices
of \(k\) active negative edges.

The stronger four-endpoint semigroup needed for a direct common-cone
promotion is, however, not positive.  In the alphabet
`0=B(0)`, `1=B(0)^T`, `2=B(1)`, `3=B(1)^T`, the frozen length-120 word

```text
220221211213112031133303133331333331303330300330000231110032111102212011110300002311121210222331121112310311331323112101
```

has exact \(F<0\).  Its word SHA-256 is
`c09e5facd6b822aad7f43b1fd5c16316a93680a55f129d30c4eb57d0569fa2e6`,
and its exact value is

```text
-18190120474553014207724320230898068534479316268000740547152031056720819382678784187176552826802467629600079871
```

Thus no trace-compatible cone can contain all four independently varying
endpoint generators.  This does not contradict the Bernstein lemma:
each coefficient is a fixed-cardinality average over endpoint assignments,
and one negative assignment need not make that average negative.  The
remaining proof target must preserve this symmetrization instead of
dropping to the full four-generator semigroup.

## Arbitrary-word theorem for the fixed atom

The fixed \(z=1\) atom is sign-free at every word length.  The proof uses
the exact depth-12 Bernstein audit above and two independent tail bounds.
Write \(\chi_k(W)=\operatorname{tr}(\wedge^k W)\).

First, in the common sign gauge \(D=\operatorname{diag}(1,1,1,-1,1)\),
both grade-four atoms

\[
M_s=D(\wedge^4 B_s)D,\qquad B_s\in\{B,B^{\mathsf T}\},
\]

are entrywise nonnegative and have \((M_s)_{00}=8\).  Put
\(N_s=\wedge^3 B_s\).  Exact integer enumeration of all 8,192 binary
blocks \(u\) of length 13 proves

\[
100\lVert N_u\rVert_F^2 < (M_u)_{00}^2.
\]

The worst block is `0000000111111`, with

\[
\frac{\lVert N_u\rVert_F^2}{(M_u)_{00}^2}
=
\frac{244364780910343182599473}
{31993824161320836400152576}
<\frac1{100};
\]

the unsimplified strict integer margin is
\(7557346070286518140205276\).  Exact enumeration of every remainder
of length 0 through 12 gives

\[
\lVert N_v\rVert_F^2\leq 10(M_v)_{00}^2,
\]

with equality only for the empty remainder.

Split any word of length at least 13 into 13-letter blocks and one short
remainder.  Frobenius submultiplicativity and
\(|\operatorname{tr}X|\leq\sqrt{10}\lVert X\rVert_F\) bound the signed
grade-three trace.  Nonnegativity of every \(M_s\) lets the grade-four
trace retain the state-zero path through every block.  After squaring,
the first complete block contributes the strict factor
\(10\cdot({<}1/100)\cdot10<1\); every additional block improves it.
Consequently

\[
\chi_3(W)+\chi_4(W)>0 \qquad (|W|\geq13).
\]

Second, exact Sylvester certificates give

\[
\lVert B\rVert_2^2<6,\qquad
\lVert\wedge^2B\rVert_2^2<29.
\]

The leading principal minors of the two Gram gaps are respectively

```text
2, 4, 4, 8, 20
```

and

```text
13, 117, 1881, 34285, 308565, 7714125, 143345585,
810463115, 12625622675, 188548677535.
```

Hence

\[
|\chi_1(W)|\leq5(\sqrt6)^n,\qquad
|\chi_2(W)|\leq10(\sqrt{29})^n.
\]

At \(n=6\), the exact upper bound is

\[
5\cdot6^3+10\cdot29^3=244970<8^6=262144,
\]

with margin 17,174; both ratios decrease thereafter.  Since
\(\chi_0=1\) and \(\chi_5=8^n\),

\[
\chi_0+\chi_1+\chi_2+\chi_5>0 \qquad (n\geq6).
\]

For every \(n\geq13\), adding the last two strict inequalities proves
\(\det(I+W)>0\).  At lengths 1 through 12, the exact Bernstein audit
proves \(\chi_0+\chi_2+\chi_3+\chi_5>0\), while the stored exact
grade-\((1,4)\) cone gives \(\chi_1+\chi_4\geq0\).  The empty word gives
\(\det(2I)=32\).  Therefore

\[
\boxed{\det(I+W)>0\quad\text{for every }W\in\langle B,B^{\mathsf T}\rangle.}
\]

## Two arbitrary-length positive word classes

Two infinite word families admit direct proofs independent of a cone.
First, the exact characteristic polynomial of \(B\) is

\[
p(\lambda)=\lambda^5-2\lambda^4+\lambda^3-7\lambda^2+16\lambda-8.
\]

Exact Sturm counting gives one positive real root, no negative real root,
and two nonreal conjugate pairs.  Moreover, the exact gcd of \(p\) and its
reciprocal polynomial has degree zero, so no nonreal root lies on the unit
circle.  Therefore, for every \(n\geq1\),

\[
\det(I+B^n)=(1+r^n)
|1+z_1^n|^2|1+z_2^n|^2>0.
\]

The same statement holds for \((B^{\mathsf T})^n\).

Second, let \(\bar u^{\,R}\) denote reverse order together with exchanging
`0` and `1`, so that \(B_0^{\mathsf T}=B_1\).  With the word-product
convention used by the oracle,

\[
W(u\bar u^{\,R})=W(u)^{\mathsf T}W(u).
\]

This matrix is positive semidefinite, hence every transpose-reflection
square word has
\(\det(I+W)>0\), at arbitrary length.  These lemmas cover all pure words,
all alternating even powers, and every cyclic representative admitting
the displayed reflection-square cut.  They do not yet cover a generic
binary necklace, which remains the full-Fock cone or domination target.
