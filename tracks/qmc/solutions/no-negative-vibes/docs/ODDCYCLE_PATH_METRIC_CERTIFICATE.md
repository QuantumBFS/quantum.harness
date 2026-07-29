# Exact finite-state split-contraction certificate

This note proves strict determinant positivity for the four-letter alphabet

\[
\mathcal A=\{B(1/1000),B(1/1000)^{\mathsf T},
             B(4/5),B(4/5)^{\mathsf T}\},
\]

where

\[
B(p)=
\begin{pmatrix}
0&0&2&0&0\\
2&0&0&0&0\\
0&2&0&p&0\\
0&0&0&1&1\\
0&0&-1&0&1
\end{pmatrix}.
\]

The machine-readable certificate is frozen in
`oracle/oddcycle_path_metric.py`.  It contains four symmetric rational
matrices \(R_0,\ldots,R_3\), all with denominator \(10^9\), and one rational
time vector \(u_i\) for each matrix.  The exact verifier checks:

1. every \(R_i\) has inertia \((1,4)\), using Jacobi sign changes;
2. all 16 labelled transition gaps
   \[
   G_{ij}=R_i-A_j^{\mathsf T}R_jA_j
   \]
   are positive definite, using Sylvester's criterion;
3. \(u_i^{\mathsf T}R_i u_i>0\);
4. after a consistent choice of signs for the \(u_i\),
   \[
   u_i^{\mathsf T}R_iA_j^{-1}u_j>0
   \quad(0\le i,j<4);
   \]
5. \(\det A_j=8>0\) for every letter.

All of these checks use exact integer and rational arithmetic.

## Arbitrary-word theorem

Let \(W=A_{s_n}\cdots A_{s_1}\), put
\(P_k=A_{s_k}\cdots A_{s_1}\), \(P_0=I\), and set \(s_0=s_n\).
The transition inequalities telescope exactly:

\[
R_{s_n}-W^{\mathsf T}R_{s_n}W
=\sum_{k=1}^{n}
P_{k-1}^{\mathsf T}G_{s_{k-1},s_k}P_{k-1}\succ0.
\]

Thus every word is a strict split contraction, although the metric closing
the word depends on its final letter.

The positive vectors define future Lorentz cones

\[
\mathcal C_i^+
=\{x:x^{\mathsf T}R_i x>0,\ u_i^{\mathsf T}R_i x>0\}.
\]

The 16 orientation inequalities imply
\(A_j^{-1}(\mathcal C_j^+)\subset\mathcal C_i^+\) for every transition.
Consequently \(W^{-1}\) preserves the future cone associated with the
closing state.

The strict Stein inequality and inertia \((1,4)\) imply that \(W\) has no
unit-circle spectrum and has exactly one algebraically simple eigenvalue
\(\lambda_s\) inside the unit disk.  It is real because nonreal eigenvalues
occur in conjugate pairs.  Cone Perron--Frobenius applied to \(W^{-1}\)
makes its unique exterior eigenvalue \(1/\lambda_s\) positive, hence
\(\lambda_s>0\).

The remaining four eigenvalues lie outside the unit disk.  Their nonreal
pairs contribute positive factors to \(\det(I+W)\), while for every real
exterior eigenvalue the signs of \(1+\lambda\) and \(\lambda\) agree.
Therefore

\[
\operatorname{sign}\det(I+W)
=\operatorname{sign}\frac{\det W}{\lambda_s}=+1,
\]

because \(\det W=8^n\).  Hence

\[
\boxed{\det(I+W)>0\quad\text{for every nonempty word }W\in\mathcal A^*.}
\]

The time-orientation gate is essential: split contraction and positive
\(\det W\) alone do not fix this sign.

## Structural position

With one state, this construction reduces to the familiar common-metric
split-contraction certificate.  Four states provide a genuine strict
extension for this alphabet: a separate exact dual certificate excludes
every common symmetric metric satisfying the same forward and transpose
gaps.

Multiple metrics on a labelled graph are related to the known
path-complete Lyapunov framework.  The new mathematical content claimed
here is the indefinite-inertia version with coherent Lorentz time
orientation and its determinant-positivity consequence, together with
this exact QMC certificate—not the generic multiple-Lyapunov architecture.
