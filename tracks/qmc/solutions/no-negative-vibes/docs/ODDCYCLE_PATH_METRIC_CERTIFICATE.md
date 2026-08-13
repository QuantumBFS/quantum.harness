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
split-contraction certificate.  Four states are strictly more expressive
than one *quadratic* metric for this alphabet: a separate exact dual
certificate excludes every common symmetric metric satisfying the same
forward and transpose gaps.

The graph inequalities themselves are a special case of path-complete
\(p\)-dominance: with forward letters and \(P_i=R_i\) they give
\(p=4\) dominance at rate one, while the inverse-letter formulation with
\(P_i=-R_i\) gives \(p=1\).  The future-sheet maps are strict
path-complete positivity.  These switched-system structures and their
closed-path spectral conclusions are prior art.

Moreover, because all 16 edges are present, the inverse letters strongly
preserve the common nonquadratic cone

\[
K=\bigcap_iK_i,\qquad K_i=\overline{\mathcal C_i^+}.
\]

For any fixed \(j\), the open set
\(A_j^{-1}(\mathcal C_j^+)\) lies inside every
\(\mathcal C_i^+\), so \(K\) has nonempty interior.  As an intersection
of closed convex pointed cones it is closed, convex, and pointed, hence
proper and solid.  If \(x\in K\setminus\{0\}\), then

\[
(A_j^{-1}x)^{\mathsf T}R_i(A_j^{-1}x)
>x^{\mathsf T}R_jx\ge0
\quad\text{for every }i.
\]

Approximating \(x\) from \(\mathcal C_j^+\) fixes the future component,
which proves

\[
A_j^{-1}(K\setminus\{0\})\subset\operatorname{int}K.
\]

The exact dual does not exclude this common cone; it excludes only a
common quadratic metric.  The contribution claimed here is therefore the
fermion-determinant sign corollary, its exact rational four-letter
certificate, and the physical QMC realization—not a new
multiple-Lyapunov or cone-positivity architecture.

Relation to the full 10-Majorana Wei contraction conditions remains open.
In particular, the five-dimensional common-quadratic-metric dual does not
exclude fixed anticommuting \(J_1,J_2\) structures after the
number-conserving Majorana lift or after one fixed complex orthogonal
Majorana basis change.
