# Sign-free fermion determinants from coherently oriented Lorentz path metrics

> **Document status (2026-07-30):** research-paper draft accompanying the
> ready-for-review challenge submission. The exact claims and replay are
> submission-ready; bibliography normalization and collaborator editing remain
> before a separate external arXiv/journal submission. See the
> [complete challenge report](../CHALLENGE_REPORT.md) for all team results,
> including routes outside this paper's oddcycle scope.

## Abstract

We derive a determinant-QMC criterion from path-complete
\(1\)-dominance and strict path positivity.  Instead of
requiring every one-particle propagator to contract one common indefinite
metric, we assign a Lorentz metric to each state of a labelled graph.  A
strict matrix inequality on every edge makes the metrics telescope around
every closed word.  A second, finite time-orientation condition fixes the
otherwise undetermined sign of the fermion determinant.  With positive
letter determinants, the resulting criterion proves

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
not admit a common strict quadratic split-contraction metric of the tested
form.  Thus the four-state quadratic certificate succeeds where its
one-state quadratic counterpart cannot.  An exact Nambu-space pullback
also excludes Wei's fixed-\(J_1,J_2\) Majorana contraction sufficient
class after any fixed complex orthogonal Majorana basis change.  This does
not exclude the common nonquadratic cone or unrelated fermion-bag, loop,
worldline, or future sign-free mechanisms.  Finally, the same alphabet
gives a positive five-valued auxiliary-field decomposition of a real
Hermitian, number-conserving, interacting five-mode Hamiltonian.  The
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

## 2. A determinant corollary of Lorentz path metrics

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

### 2.2. Determinant theorem

**Theorem 1 (coherently oriented Lorentz path metric).**  
Suppose the real invertible letters \(A_j\) admit
symmetric matrices \(R_i\) and vectors \(u_i\) satisfying (3), (5)--(7),
and, for the gaps defined in (4),

\[
G_{ij}\succ0\qquad(0\le i,j<m).
\]

If \(\det A_j>0\) for every letter, then every nonempty word

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
For several states, the LMIs are a special case of known path-complete
\(p\)-dominance, while the component choice is strict path-complete
positivity.  The contribution claimed here is the fermion-determinant
consequence and its exact QMC realization, not the switched-system
architecture.

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

### 3.3. Independent robust frontier certificate

To test whether the exact construction was an isolated numerical point, we
subsequently scanned \(12\,325\) rational two-point cells in the larger
family

\[
B(p,q,r)=
\begin{pmatrix}
0&0&2&0&0\\
2&0&0&0&0\\
0&2&0&p&0\\
0&0&0&1&q\\
0&0&-r&0&1
\end{pmatrix}.
\]

The frozen path-metric oracle retained \(6\,266\) cells.  A dual-interior
ranking completed all survivors: \(4\,302\) solver calls succeeded,
\(4\,183\) met both ranking thresholds, and \(1\,964\) solver errors were
retained as inconclusive rather than interpreted as no-go results.  The
first five Pareto leaders all passed exact rational dual replay.

The leading robust point, `cell-4321`, is the alphabet generated by

\[
B(1/2000,11/10,9/10),\qquad
B(49/40,11/10,9/10)
\]

and their transposes.  A separate frozen certificate verifies the same
arbitrary-word theorem, exact common-quadratic-metric exclusion, and
positive-field interacting transfer as for (16).  Its four Lorentz metrics
have denominator \(10^9\); all four inertia gates and all 16 Stein gaps pass
exactly.  Its dual projection uses denominator \(10^8\), has exact
cancellation and trace one, and all four rational multipliers are positive
definite.

The two exact candidates have complementary numerical profiles:

| quantity | alphabet (16) | robust `cell-4321` |
|---|---:|---:|
| path-certificate margin | \(4.827288\times10^{-5}\) | \(2.217335\times10^{-5}\) |
| time-orientation margin | \(0.229974\) | \(0.220931\) |
| floating dual minimum eigenvalue | \(1.2435\times10^{-7}\) | \(1.31178\times10^{-4}\) |
| physical minimum row margin | \(1\) | \(7949/10000\) |

We retain (16) as the main statement because \(q=r=1\), its exact constants
are simpler, and its primal and physical margins are larger.  The robust
point is an independent exact replication with a substantially deeper
dual interior.  It supports robustness of the discovery, but the
Majorana/Wei exclusion below is proved only for the simpler main alphabet
(16), not independently for `cell-4321`.

## 4. Strict separation from a common quadratic metric

The four-state certificate is strictly more expressive than a one-state
quadratic certificate for this alphabet.  A common strict quadratic metric
is excluded exactly.

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
The alphabet (16) has no real symmetric common quadratic metric satisfying
all four strict inequalities (19).

The exact certificate uses only rational arithmetic and Sylvester
positivity tests.  It establishes strict separation from the tested common
quadratic split-contraction mechanism.

### 4.1 Exclusion of the fixed-\(J_1,J_2\) Majorana contraction class

The stronger ten-Majorana audit must retain the CAR bilinear form, not just
the real five-dimensional quadratic metric.  In Nambu coordinates
\(\Psi=(c,c^\dagger)^{\mathsf T}\), define

\[
\Omega=\begin{pmatrix}0&I_5\\I_5&0\end{pmatrix},\qquad
G(B)=\operatorname{diag}(B^{-1},B^{\mathsf T}).
\]

Then \(G(B)^{\mathsf T}\Omega G(B)=\Omega\).  Pulling any Wei contraction
metric through an arbitrary fixed complex orthogonal Majorana basis change
is explicit.  Let \(S\) satisfy

\[
S^{\mathsf T}\Omega S=I_{10},
\qquad
\eta=S^{-\dagger}(iJ_2)S^{-1},
\]

where \(J_2\) is the real orthogonal skew-symmetric canonical Wei
structure.  The pulled-back Hermitian \(\eta\) satisfies

\[
\eta-G(B)^\dagger\eta G(B)\succeq0,\qquad
\eta\Omega^{-1}\eta^{\mathsf T}=-\Omega
\tag{21}
\]

for all four letters, up to a common reversal for the expansion
orientation.  Indeed, \(S^{\mathsf T}\Omega S=I\) gives
\(\Omega^{-1}=SS^{\mathsf T}\), while
\((iJ_2)(iJ_2)^{\mathsf T}=-I\); substitution yields the second identity
in (21).  Moreover, every letter has \(\det B=8>0\).  The scalar separating
\(\Gamma_\wedge(B)\) from its Majorana Spin lift is
\(\sqrt{\det B}>0\), so the lift cannot change a configuration sign.

Write
\(\eta=\left(\begin{smallmatrix}H&K\\K^\dagger&D\end{smallmatrix}\right)\).
The principal blocks of the first inequality in (21), after congruence,
have exactly the two orientations paired by (20).  Positivity and the
four positive-definite exact dual multipliers force every such nonstrict
gap to equality.  The off-diagonal gaps then vanish.

An exact rational commutant calculation for the four letters has rank 24
in ambient dimension 25, so the common complex commutant is
\(\mathbb C I_5\).  Transpose closure makes the alphabet irreducible.
If \(H\) or \(D\) were nonzero, its invariant kernel would therefore be
trivial; but congruence invariance and \(\det B=8\) would give
\(\det H=64\det H\), or the analogous contradiction for \(D\).
Consequently

\[
\eta=\begin{pmatrix}0&kI_5\\\bar kI_5&0\end{pmatrix}.
\]

This boundary form satisfies
\(\eta\Omega^{-1}\eta^{\mathsf T}=|k|^2\Omega\), with sign \(+1\), whereas
(21) requires sign \(-1\).

**Proposition 4.**

The alphabet (16) lies outside the sufficient class defined by Wei's fixed
\(J_1,J_2\) contraction conditions, including after any fixed complex
orthogonal Majorana basis change.

This proposition also excludes the Majorana-reflection-positive and
anticommuting-MTR equality cases contained in that sufficient class.  It
does not exclude unrelated fermion-bag, loop, worldline, or future
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
\tag{22}
\]

Exact row arithmetic gives a maximum diagonal-dominance requirement of
36, so \(T\) is real symmetric positive definite with minimum row margin
one.  Therefore

\[
e^{-H}=T/41
\tag{23}
\]

defines a real Hermitian, number-conserving Hamiltonian
\(H=-\log(T/41)\).

Equation (23) is a positive discrete auxiliary-field decomposition with
fields

\[
I,\ B_0,\ B_0^{\mathsf T},\ B_1,\ B_1^{\mathsf T}
\]

and coefficients

\[
\frac1{41}(37,1,1,1,1).
\tag{24}
\]

Deleting identity letters from a history leaves a word in (16), so
Corollary 2 makes every configuration containing a nonidentity field
strictly positive.  The all-identity history is the empty word and has
weight \(\det(2I_5)=2^5>0\).

The transfer is not a scalar Gaussian exterior lift.  If it were, its
vacuum, one-particle, and two-particle blocks would obey

\[
41T_2=\wedge^2(T_1).
\tag{25}
\]

The exact difference in (25) has 58 nonzero entries, the first equal to
164.  Thus \(H\) is genuinely interacting.  Each nonidentity field also
admits a real one-particle logarithm because its characteristic polynomial
has no eigenvalue on the negative real axis.

## 6. Reproducibility

The proof is split into solver-independent exact replays:

```bash
python -m pytest -q \
  tests/test_oddcycle_path_metric.py \
  tests/test_oddcycle_metric_dual.py \
  tests/test_oddcycle_pair_physical.py \
  tests/test_oddcycle_majorana_wei_audit.py \
  tests/test_oddcycle_final_certificate.py
```

The independently promoted robust point has a single-command replay:

```bash
python -m oracle.oddcycle_robust_certificate
python -m pytest -q tests/test_oddcycle_robust_certificate.py
```

The tests check the theorem certificate, common-quadratic-metric dual
separation, physical transfer, and full fixed-\(J_1,J_2\) Majorana/Wei
exclusion.  The semidefinite programs are discovery tools only; `cvxpy`
is not needed to replay the frozen rational results.

The repository also records the complete search ledger, word counts,
failed cone attempts, exact rationalization method, and software
environment.  A final archival release should attach a machine-readable
summary containing the commit hash and exact certificate digests.

## 7. Relation to prior work and scope

The ordinary one-state split-orthogonal and contraction-semigroup
criteria are established sign-free mechanisms.  Multiple quadratic
Lyapunov functions, path-complete positivity, and path-complete
\(p\)-dominance are established switched-system tools.  With forward
letters and \(P_i=R_i\), our 16 LMIs are path-complete \(p=4\) dominance
inequalities at rate one; with inverse letters and \(P_i=-R_i\), they are
the equivalent \(p=1\) formulation.  The dominated spectral splitting and
path-dependent Perron direction are therefore known control-theory
conclusions.

The all-to-all edge set also produces one common nonquadratic cone for the
inverse alphabet.  If \(K_i=\overline{\mathcal C_i^+}\), then

\[
K=\bigcap_iK_i
\]

is proper and solid.  Indeed, for any fixed \(j\), (12)--(13) put the open
set \(A_j^{-1}(\mathcal C_j^+)\) inside every
\(\mathcal C_i^+\), so the intersection has nonempty interior.  It is
closed, convex, and pointed because each \(K_i\) is.  For
\(x\in K\setminus\{0\}\), (12) gives

\[
(A_j^{-1}x)^{\mathsf T}R_i(A_j^{-1}x)>x^{\mathsf T}R_jx\ge0
\quad\text{for every }i.
\]

Continuity from the future sheet fixes the component, and hence

\[
A_j^{-1}(K\setminus\{0\})\subset\operatorname{int}K.
\]

Thus the orientation part is a common cone-preserving semigroup, even
though no common *quadratic* Lorentz metric exists.  We do not claim the
graph, multiple quadratic cones, or common Perron cone as new.

The contribution here is the combination of:

1. an explicit determinant-sign corollary for the fermionic
   grand-canonical trace;
2. an exact alphabet for which a four-state quadratic certificate works
   but a common quadratic metric is impossible;
3. a solver-independent rational certificate;
4. an exact exclusion of Wei's fixed-\(J_1,J_2\) Majorana contraction
   sufficient class for the same alphabet;
5. a positive-field interacting fermion realization.

The following limitations are explicit.

- The result controls the full Fock trace, not each fixed-particle sector.
- The Hamiltonian is a five-mode cluster and is generally nonlocal.
- Proposition 3 excludes the common real symmetric quadratic metric
  inequalities but not the common nonquadratic cone above.
- Proposition 4 excludes Wei's fixed-\(J_1,J_2\) Majorana contraction
  sufficient class, including fixed complex orthogonal basis changes.  It
  does not exclude unrelated fermion-bag, loop, worldline, or future
  sign-free mechanisms.
- The current result is a sufficient class, not a classification of
  sign-problem-free QMC.

The exact Nambu reduction and replay are given in
`ODDCYCLE_MAJORANA_WEI_AUDIT.md`.  The remaining publication work is
collaborator review, clean-commit archival replay, reference completion,
and conversion of this draft to a submission-ready manuscript.

## References to complete before external paper submission

1. Wang et al., split-orthogonal-group sign-problem-free QMC.
2. Wei, *Semigroup approach to the sign problem in quantum Monte Carlo
   simulations*, *Phys. Rev. B* **110**, 075146 (2024),
   arXiv:1712.09412v3.
3. Wei et al., *Majorana Positivity and the Fermion Sign Problem of Quantum
   Monte Carlo Simulations*, *Phys. Rev. Lett.* **116**, 250601 (2016),
   arXiv:1601.01994.
4. Li, Jiang, and Yao, *Majorana-time-reversal symmetries: a fundamental
   principle for sign-problem-free quantum Monte Carlo simulations*,
   *Phys. Rev. Lett.* **117**, 267002 (2016), arXiv:1601.05780.
5. Wu and Zhang, sufficient symmetry condition for absence of the sign
   problem.
6. A. A. Ahmadi, R. M. Jungers, P. A. Parrilo, and M. Roozbehani,
   “Joint Spectral Radius and Path-Complete Graph Lyapunov Functions,”
   *SIAM J. Control Optim.* **52**, 687 (2014),
   doi:10.1137/110855272.
7. F. Forni, R. M. Jungers, and R. Sepulchre, “Path-complete positivity
   of switching systems,” arXiv:1611.02603.
8. G. O. Berger and R. M. Jungers, “p-dominant switched linear systems,”
   *Automatica* **132**, 109801 (2021),
   doi:10.1016/j.automatica.2021.109801.
9. A standard cone Perron--Frobenius reference for strongly positive maps.
10. A standard discrete-time indefinite Stein inertia theorem reference.
