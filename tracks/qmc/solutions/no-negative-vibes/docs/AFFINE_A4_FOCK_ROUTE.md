# Affine \(A_4\) route for the seed-61 full-Fock determinant

## Verdict

The Lam--Pylyavskyy loop-total-positivity route does **not** prove

\[
\det(I+w)>0,\qquad w\in\{B,B^T\}^*.
\]

The mapping to positive affine \(A_4\) Chevalley generators is exact, but
Theorem 3.5 of [Lam--Pylyavskyy, arXiv:0812.0840](https://arxiv.org/abs/0812.0840)
controls \(\det X(t)\), not \(\det(I+X(t))\).  The latter is a full-exterior
character after evaluation at \(t=1\), and it is not a positive cylindric
network partition function in general.

This eliminates the proposed theorem route, not the fixed seed-61
positivity claim.  The existing exact depth-16 scan remains valid evidence
for that claim.

## Exact folding map

Conjugate the audited seed-61 atom by

\[
D=\operatorname{diag}(1,1,-1,-1,-1).
\]

Then \(\widetilde B=DBD\) and \(D B^T D=\widetilde B^T\), so every word is
conjugated by the same \(D\) and its determinant is unchanged.  With

\[
(a_1,a_2,a_3,a_4,a_5)
=\left(\frac38,\frac14,\frac{13}{12},\frac{11}{96},\frac{77}{96}\right),
\]

the positive atom is

\[
\widetilde B=
\begin{pmatrix}
1&a_1&0&0&0\\
0&1&a_2&0&0\\
0&0&1&a_3&0\\
0&0&0&1&a_4\\
a_5&a_5a_1&0&0&1
\end{pmatrix}.
\]

Using the paper's folding convention
\(A_{ij}(t)=\sum_k x_{i,j+5k}t^k\), define

\[
\begin{aligned}
e_i(a;t)&=I+aE_{i,i+1}, &&1\leq i<5,\\
e_5(a;t)&=I+atE_{5,1},\\
f_i(a;t)&=I+aE_{i+1,i}, &&1\leq i<5,\\
f_5(a;t)&=I+at^{-1}E_{1,5}.
\end{aligned}
\]

The required loop lifts are therefore

\[
\begin{aligned}
E(t)&=e_5(a_5;t)e_4(a_4;t)e_3(a_3;t)e_2(a_2;t)e_1(a_1;t),\\
F(t)&=f_1(a_1;t)f_2(a_2;t)f_3(a_3;t)f_4(a_4;t)f_5(a_5;t),
\end{aligned}
\]

with \(E(1)=\widetilde B\), \(F(1)=\widetilde B^T\), and
\(F(t)=E(t^{-1})^T\).  Thus a matrix word has a multiplicative loop lift
obtained by replacing its letters by \(E(t)\) and \(F(t)\).

Every factor is a positive Chevalley generator.  Hence every lifted word is
loop-TNN by the semigroup property, and Theorem 3.4 supplies a nonnegative
cylindric-network realization.

## Why the determinant theorem does not transfer

For \(n=5\), Theorem 3.5 gives

\[
\det X(t)=
\sum_{k\in\mathbb Z}(-1)^{k(5-1)}
\left(\sum_{P\in\Gamma_k}\operatorname{wt}(P)\right)t^k,
\]

so its winding signs are indeed all positive.  But replacing \(X(t)\) by
\(I+X(t)\) is not an allowed consequence: loop-TNN matrices are closed
under multiplication, not addition.

The failure is already exact for the one-letter block.  Put
\(p=a_1a_2a_3a_4a_5\).  Direct symbolic expansion gives

\[
\boxed{\det(I+E(t))=32-pt},\qquad
\boxed{\det(I+\widetilde B)=32-p}.
\]

The negative winding coefficient proves that \(I+E(t)\) cannot itself be
the path matrix of a nonnegative cylindric network to which Theorem 3.5
applies.  It also gives an immediate positive-parameter counterexample to
any parameter-uniform claim: \(a_i=3\) yields
\(\det(I+\widetilde B)=32-3^5=-211\).

For seed 61,

\[
p=\frac{11011}{1179648},\qquad
\det(I+\widetilde B)=
\frac{37737725}{1179648}>0,
\]

so the one-letter obstruction does not falsify the fixed seed.

Finally,

\[
\det(I+X(1))
=\sum_{r=0}^{5}\operatorname{tr}\!\left(\Lambda^r X(1)\right)
=\chi_{\Lambda^\bullet\mathbb C^5}(X(1)).
\]

This is the character of the reducible full exterior algebra under the
evaluation representation.  It is not a single generalized minor, and
loop total nonnegativity controls minors of the unfolded periodic matrix,
not this evaluated character.  The known negative grade-2 and grade-4
traces are therefore consistent with the theory.

## Consequence

Do not use Theorems 3.4--3.5 as a proof of seed-61 full-Fock positivity.
A successful proof must add a seed-specific estimate or a genuinely
full-exterior positive realization that controls the cancellations between
grades.  A targeted next test is to search for a trace-compatible cone
directly on \(\Lambda^\bullet\mathbb R^5\), rather than sector by sector.
