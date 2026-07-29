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
\(|T|<D\) do not define a sign-free cluster chamber.  A theorem for the
fixed \(z=1\) atom must use a quantitatively smaller negative-winding
margin (or an equivalent stronger inequality), not only the two invariant
signs.

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
of \(k\) active negative edges.  An invariant trace-compatible cone for
those four endpoint atoms would promote the Bernstein pattern to all
depths and even allow independent layer amplitudes in \([0,1]\).
