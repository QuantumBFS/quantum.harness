# Sign-free fermion determinants from coherently oriented Lorentz path metrics

## Abstract

We introduce a finite-state extension of the split-contraction criterion
for sign-problem-free auxiliary-field quantum Monte Carlo.  Instead of
requiring every one-particle propagator to contract one common indefinite
metric, we assign a Lorentz metric to each state of a labelled graph.  A
strict matrix inequality on every edge makes the metrics telescope around
every closed word.  A second, finite time-orientation condition fixes the
otherwise undetermined sign of the fermion determinant.  For odd
one-particle dimension and positive letter determinants, the resulting
criterion proves

\[
\det(I+A_{s_n}\cdots A_{s_1})>0
\]

at arbitrary product depth.

We give an exact rational four-state certificate for the real five-mode
alphabet

\[
\{B(1/1000),B(1/1000)^{\mathsf T},
  B(4/5),B(4/5)^{\mathsf T}\}.
\]

All metric inertias, 16 strict edge inequalities, 16 time-orientation
tests, and letter determinants are verified by integer arithmetic.  A
separate exact Gordan--Stiemke certificate proves that the four letters do
not admit a common strict split-contraction metric, so the finite-state
certificate is strictly stronger for this example.  Finally, the same
alphabet gives a positive five-valued auxiliary-field decomposition of a
real Hermitian, number-conserving, interacting five-mode Hamiltonian.  The
result is a grand-canonical cluster construction; locality and
fixed-filling positivity are not claimed.

## 1. Determinant QMC setup

Let \(V=\mathbb R^d\), and let

\[
\mathcal F(V)=\bigoplus_{k=0}^{d}\wedge^k V
\]

be the number-conserving fermion Fock space.  The vacuum-normalized
exterior implementer

\[
\Gamma_\wedge(A)=\bigoplus_{k=0}^{d}\wedge^k A
\]

obeys

\[
\Gamma_\wedge(A_2)\Gamma_\wedge(A_1)
=\Gamma_\wedge(A_2A_1)
\]

and

\[
\operatorname{Tr}_{\mathcal F}\Gamma_\wedge(W)
=\sum_{k=0}^{d}\operatorname{Tr}(\wedge^kW)
=\det(I_d+W).
\tag{1}
\]

For a discrete auxiliary-field history
\(\mathcal C=(s_1,\ldots,s_n)\) with scalar coefficients \(q_s>0\),

\[
w(\mathcal C)
=\left(\prod_{\ell=1}^{n}q_{s_\ell}\right)
\det(I_d+A_{s_n}\cdots A_{s_1}).
\tag{2}
\]

Thus strict positivity of the determinant for every word removes the
configuration sign problem in the grand-canonical trace.

## 2. Finite-state Lorentz path metrics

Consider invertible real letters
\(\mathcal A=\{A_0,\ldots,A_{m-1}\}\subset GL(d,\mathbb R)\).
Associate with state \(i\) a real symmetric nonsingular matrix \(R_i\)
with inertia

\[
\operatorname{In}(R_i)=(1,d-1).
\tag{3}
\]

For every ordered pair of states define the labelled gap

\[
G_{ij}=R_i-A_j^{\mathsf T}R_jA_j.
\tag{4}
\]

The state has a concrete automaton interpretation.  Reading letter \(j\)
moves the metric label to state \(j\), independently of the previous
state.  The previous state is retained in (4), which supplies all
\(m^2\) edges.

### 2.1. Why a time orientation is necessary

The inequalities \(G_{ij}\succ0\) alone do not determine the sign of
\(\det(I+W)\), even when \(\det W>0\).  For example,

\[
R=\operatorname{diag}(1,-1,-1,-1,-1),
\qquad
A=\operatorname{diag}(-1/2,-2,2,2,2)
\]

satisfy

\[
R-A^{\mathsf T}RA
=\operatorname{diag}(3/4,3,3,3,3)\succ0,
\qquad
\det A=8,
\]

but

\[
\det(I+A)=-27/2.
\]

The missing datum is the component of the Lorentz cone.

Choose a vector \(u_i\) satisfying

\[
u_i^{\mathsf T}R_i u_i>0
\tag{5}
\]

and define the future cone

\[
\mathcal C_i^+
=\{x:x^{\mathsf T}R_i x>0,\
       u_i^{\mathsf T}R_i x>0\}.
\tag{6}
\]

The finite orientation gate is

\[
c_{ij}:=
u_i^{\mathsf T}R_iA_j^{-1}u_j>0
\qquad(0\le i,j<m).
\tag{7}
\]

Because \(\det A_j>0\), the inverse may be replaced by
\(\operatorname{adj}(A_j)\) when checking signs exactly.

### 2.2. Main determinant theorem

**Theorem 1 (coherently oriented Lorentz path metric).**  
Suppose the real invertible letters \(A_j\) admit
symmetric matrices \(R_i\) and vectors \(u_i\) satisfying (3)--(7) for
all \(i,j\).  If \(\det A_j>0\) for every letter, then every nonempty word

\[
W=A_{s_n}\cdots A_{s_1}
\]

satisfies

\[
\det(I_d+W)>0.
\tag{8}
\]

**Proof.**
Put \(P_k=A_{s_k}\cdots A_{s_1}\), \(P_0=I\), and \(s_0=s_n\).
Direct expansion gives the cyclic telescoping identity

\[
R_{s_n}-W^{\mathsf T}R_{s_n}W
=\sum_{k=1}^{n}
P_{k-1}^{\mathsf T}
G_{s_{k-1},s_k}
P_{k-1}\succ0.
\tag{9}
\]

Write the positive matrix in (9) as \(G\).  Equation (9) excludes
unit-circle eigenvalues: if \(Wx=\lambda x\) and \(|\lambda|=1\), then
\(x^*Gx=0\), a contradiction.

Let \(E_s\) and \(E_u\) be the generalized spectral subspaces inside and
outside the unit circle.  Iterating (9) on \(E_s\) gives

\[
x^*R_{s_n}x
=\sum_{k=0}^{\infty}(W^kx)^*G(W^kx)>0
\quad(x\in E_s\setminus\{0\}),
\tag{10}
\]

so \(\dim E_s\le1\).  Applying the inverse form of (9) on \(E_u\) gives

\[
-x^*R_{s_n}x
=\sum_{k=1}^{\infty}(W^{-k}x)^*G(W^{-k}x)>0,
\tag{11}
\]

so \(\dim E_u\le d-1\).  Since there is no unit-circle spectrum and
\(\dim E_s+\dim E_u=d\), equality holds in both bounds.  Hence \(W\) has
exactly one algebraically simple eigenvalue
\(\lambda_s\) in the open unit disk.  It is real because nonreal
eigenvalues occur in conjugate pairs.

For \(L_j=A_j^{-1}\), equation (4) implies

\[
L_j^{\mathsf T}R_iL_j-R_j
=L_j^{\mathsf T}G_{ij}L_j\succ0.
\tag{12}
\]

It follows from (5), (7), and connectedness of the two timelike
components that

\[
L_j(\mathcal C_j^+)\subset\mathcal C_i^+.
\tag{13}
\]

Moreover, every nonzero boundary vector is sent to the cone interior by
the strict term in (12).  Around the closed state cycle of the word,
\(W^{-1}\) therefore strongly preserves the proper cone
\(\overline{\mathcal C_{s_n}^+}\).  Cone Perron--Frobenius makes its
spectral radius a positive simple eigenvalue.  The unique eigenvalue of
\(W^{-1}\) outside the unit disk is \(1/\lambda_s\), hence
\(\lambda_s>0\).

All remaining eigenvalues of \(W\) lie outside the unit disk.  A nonreal
conjugate pair contributes positively to both \(\det W\) and
\(\det(I+W)\); for a real exterior eigenvalue,
\(\operatorname{sign}(1+\lambda)=\operatorname{sign}\lambda\).  Thus

\[
\operatorname{sign}\det(I+W)
=\operatorname{sign}\frac{\det W}{\lambda_s}.
\tag{14}
\]

The right-hand side is positive because
\(\det W=\prod_k\det A_{s_k}>0\) and \(\lambda_s>0\).
\(\square\)

For one state, Theorem 1 reduces to the standard common-metric
split-contraction construction with an explicit component condition.
For several states it is a multiple-Lyapunov or path-complete extension,
but with indefinite inertia and a coherent Lorentz orientation.

## 3. An exact five-mode certificate

Define

\[
B(p)=
\begin{pmatrix}
0&0&2&0&0\\
2&0&0&0&0\\
0&2&0&p&0\\
0&0&0&1&1\\
0&0&-1&0&1
\end{pmatrix}
\tag{15}
\]

and

\[
\mathcal A=
\{B(1/1000),B(1/1000)^{\mathsf T},
  B(4/5),B(4/5)^{\mathsf T}\}.
\tag{16}
\]

Every letter has determinant eight.

### 3.1. Exact rational data

The certificate contains four symmetric matrices

\[
R_i=10^{-9}N_i,
\]

where the integer matrices \(N_i\) are stored verbatim in
`oracle/oddcycle_path_metric.py`.  It also stores

\[
u_0=e_5,\qquad
u_1=u_2=u_3=e_4,
\tag{17}
\]

up to the exact sign choices selected by the verifier.

No floating-point statement is used in the proof.  Fraction-free
determinants and exact rational matrix products verify:

- every \(R_i\) has one positive and four negative eigenvalues;
- every one of the 16 matrices \(G_{ij}\) is positive definite;
- every \(u_i\) is timelike;
- all 16 coherently oriented scalars in (7) are positive;
- every \(\det A_j=8\).

Theorem 1 then gives:

**Corollary 2.**  
For every \(n\ge1\) and every
\(A_{s_k}\in\mathcal A\),

\[
\det(I_5+A_{s_n}\cdots A_{s_1})>0.
\tag{18}
\]

### 3.2. Search evidence preceding the theorem

The certificate was found after a boundary-focused two-point scan.  As a
discovery check, all \(22\,369\,620\) nonempty words through length 12
were enumerated, with exact replay of the minimum

\[
\min\det(I+W)=176/5.
\]

A separate exterior-algebra diagnostic exhausted the Hodge scalar through
length 14, including \(268\,435\,456\) words at the final depth.  These
searches are not assumptions of Corollary 2; they document how the exact
candidate was selected and provide independent regression tests.

## 4. Strict separation from a common metric

The four-state result would be structurally uninteresting if the same
alphabet admitted one common strict metric.  This possibility is excluded
exactly.

Suppose one symmetric \(R\) satisfied both

\[
R-B_j^{\mathsf T}RB_j\succ0,
\qquad
R-B_jRB_j^{\mathsf T}\succ0
\tag{19}
\]

for \(j=0,1\), where \(B_0=B(1/1000)\) and \(B_1=B(4/5)\).
The frozen dual certificate gives four rational positive-definite matrices
\(X_0,X_1,Y_0,Y_1\) with total trace one and

\[
\sum_{j=0}^{1}
\left(
X_j-B_jX_jB_j^{\mathsf T}
+Y_j-B_j^{\mathsf T}Y_jB_j
\right)=0.
\tag{20}
\]

Taking Frobenius inner products of (19) with the corresponding positive
multipliers gives a strictly positive sum.  Cyclicity of the trace turns
the same sum into the inner product of \(R\) with (20), which is zero.
This contradiction proves:

**Proposition 3.**  
The alphabet (16) has no real symmetric common metric satisfying all four
strict inequalities (19).

The exact certificate uses only rational arithmetic and Sylvester
positivity tests.  It establishes strict separation from the tested
common split-contraction mechanism, not a classification of all possible
sign-free mechanisms.

## 5. Hermitian interacting auxiliary-field model

Let

\[
B_0=B(1/1000),\qquad B_1=B(4/5),
\]

and use the exterior Fock lift from (1).  Define the 32-dimensional
transfer

\[
T=
37I_{\mathcal F}
+\Gamma_\wedge(B_0)+\Gamma_\wedge(B_0)^{\mathsf T}
+\Gamma_\wedge(B_1)+\Gamma_\wedge(B_1)^{\mathsf T}.
\tag{21}
\]

Exact row arithmetic gives a maximum diagonal-dominance requirement of
36, so \(T\) is real symmetric positive definite with minimum row margin
one.  Therefore

\[
e^{-H}=T/41
\tag{22}
\]

defines a real Hermitian, number-conserving Hamiltonian
\(H=-\log(T/41)\).

Equation (22) is a positive discrete auxiliary-field decomposition with
fields

\[
I,\ B_0,\ B_0^{\mathsf T},\ B_1,\ B_1^{\mathsf T}
\]

and coefficients

\[
\frac1{41}(37,1,1,1,1).
\tag{23}
\]

Deleting identity letters from a history leaves a word in (16), so
Corollary 2 makes every configuration weight in (2) strictly positive.

The transfer is not a scalar Gaussian exterior lift.  If it were, its
vacuum, one-particle, and two-particle blocks would obey

\[
41T_2=\wedge^2(T_1).
\tag{24}
\]

The exact difference in (24) has 58 nonzero entries, the first equal to
164.  Thus \(H\) is genuinely interacting.  Each nonidentity field also
admits a real one-particle logarithm because its characteristic polynomial
has no eigenvalue on the negative real axis.

## 6. Reproducibility

The proof is split into three solver-independent exact replays:

```bash
python -m pytest -q \
  tests/test_oddcycle_path_metric.py \
  tests/test_oddcycle_metric_dual.py \
  tests/test_oddcycle_pair_physical.py
```

The tests check the theorem certificate, the common-metric dual
separation, and the physical transfer, respectively.  The semidefinite
programs are discovery tools only; `cvxpy` is not needed to replay the
frozen rational results.

The repository also records the complete search ledger, word counts,
failed cone attempts, exact rationalization method, and software
environment.  A final archival release should attach a machine-readable
summary containing the commit hash and exact certificate digests.

## 7. Relation to prior work and scope

The ordinary one-state split-orthogonal and contraction-semigroup
criteria are established sign-free mechanisms.  Multiple quadratic
Lyapunov functions and path-complete graph certificates are also standard
in switched-system stability.  We therefore do not claim the generic
idea of assigning several metrics to a graph.

The contribution here is the combination of:

1. indefinite Lorentz metrics with one positive direction;
2. a coherent, finitely checkable time orientation;
3. an arbitrary-word fermion-determinant sign theorem;
4. an exact alphabet for which the construction works but a common metric
   is impossible;
5. a positive-field interacting fermion realization.

The following limitations are explicit.

- The result controls the full Fock trace, not each fixed-particle sector.
- The Hamiltonian is a five-mode cluster and is generally nonlocal.
- Proposition 3 excludes the common real symmetric metric inequalities,
  not every Majorana reflection-positive, fermion-bag, loop, or hidden
  complex-basis reformulation.
- The current result is a sufficient class, not a classification of
  sign-problem-free QMC.

The main remaining publication task is a focused equivalence audit against
the full Majorana/contraction literature and the control-theory literature
on indefinite multiple-Lyapunov functions.

## References to complete before submission

1. Wang et al., split-orthogonal-group sign-problem-free QMC.
2. Wei, contraction-semigroup framework for fermion sign problems.
3. Li, Jiang, and Yao, Majorana-time-reversal classification.
4. Wu and Zhang, sufficient symmetry condition for absence of the sign
   problem.
5. Ahmadi, Jungers, Parrilo, and Roozbehani, path-complete graph Lyapunov
   functions.
6. A standard cone Perron--Frobenius reference for strongly positive maps.
7. A standard discrete-time indefinite Stein inertia theorem reference.
