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
