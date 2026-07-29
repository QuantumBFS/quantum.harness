# Total positivity and ordered fermion propagation for sign-free determinants

## Team

|  |  |
|---|---|
| **Team name** | zhong-guo-ren-neng-fei |
| **Members** | Zong-yue Liu |

## Challenge

| Row |  |
|---|---|
| **Challenge** | Test total nonnegativity and ordered one-dimensional fermion propagation as a determinant-QMC sign-free principle beyond fixed split-metric, Kramers, and Majorana constructions. |
| **Catalog issue** | `Addresses #121` — “Sign-problem free hunter,” released by Lei Wang, Institute of Physics, Chinese Academy of Sciences. |
| **Track** | `tracks/qmc/` — selected from the issue’s `Method: Quantum Monte Carlo` field. |

## Status and scope

We prove an arbitrary-depth determinant inequality for exponentials of real
tridiagonal Metzler matrices, supply a randomized and exact verification
harness, identify an interacting open-chain auxiliary-field realization, and
give algebraic obstructions to the fixed structures listed in issue #121.

The underlying theory of totally nonnegative matrices is classical. We do not
claim to have invented total positivity, nor do we claim worldwide priority
for its use in determinant QMC. The research claim at this stage is narrower:

1. the determinant theorem and physical auxiliary-field construction below
   are proved;
2. the full generator family is not contained in the previous
   conformal-orthogonal candidate or in the fixed split, Kramers, or 2024
   Majorana contraction conditions;
3. the surveyed sign-problem literature did not reveal this ordered
   total-nonnegativity formulation as a DQMC guiding principle;
4. an independent expert novelty review remains necessary before making a
   publication-priority claim.

## 1. Candidate generator family

Define

\[
\mathcal T_n=
\left\{
A\in M_n(\mathbb R):
A_{ij}=0\ \text{when}\ |i-j|>1,\quad
A_{i,i+1}\geq0,\quad A_{i+1,i}\geq0
\right\}.
\]

The diagonal entries are arbitrary real numbers. Thus \(\mathcal T_n\)
consists of tridiagonal Metzler matrices.

### Theorem

For every depth \(L\geq1\) and every
\(A_1,\ldots,A_L\in\mathcal T_n\), let

\[
P=e^{A_1}e^{A_2}\cdots e^{A_L}.
\]

Then every minor of \(P\) is nonnegative, and

\[
\boxed{\det(I+P)\geq1.}
\]

In particular, the fermion determinant is strictly positive for every
configuration and every product depth.

## 2. Proof

### 2.1 Additive compounds

For \(1\leq k\leq n\), let \(A^{[k]}\) be the generator induced by \(A\)
on the exterior-power space \(\bigwedge^k\mathbb R^n\). Let \(C_k(M)\)
be the \(k\)-th multiplicative compound matrix; its entries are all
\(k\)-by-\(k\) minors of \(M\), indexed by increasing row and column
subsets. Exterior-power functoriality gives

\[
C_k(e^A)=e^{A^{[k]}}.
\]

### 2.2 Every additive compound is Metzler

An off-diagonal entry of \(A^{[k]}\) replaces one index in an ordered
\(k\)-subset by another index. For a general dense matrix this replacement
may carry either sign because the resulting wedge basis must be reordered.

For \(A\in\mathcal T_n\), a nonzero replacement can only move an index
between adjacent sites \(r\) and \(r+1\). If the replacement does not
create a repeated index, its position in the ordered subset is unchanged.
The wedge reordering sign is therefore positive. The corresponding entry
is \(A_{r,r+1}\) or \(A_{r+1,r}\), both nonnegative.

Hence every \(A^{[k]}\) is Metzler.

### 2.3 Metzler exponentials are entrywise nonnegative

If \(M\) is Metzler, choose \(c\) large enough that \(M+cI\) is
entrywise nonnegative. Then

\[
e^M
=e^{-c}e^{M+cI}
=e^{-c}\sum_{r=0}^{\infty}\frac{(M+cI)^r}{r!}
\]

is entrywise nonnegative. Therefore

\[
C_k(e^A)=e^{A^{[k]}}\geq0
\]

entrywise for every \(k\). Thus \(e^A\) is totally nonnegative.

### 2.4 Arbitrary products

The Cauchy–Binet formula expresses every minor of a product as a sum of
products of minors of the factors. Therefore totally nonnegative matrices
are closed under multiplication, and

\[
P=e^{A_1}\cdots e^{A_L}
\]

is totally nonnegative.

### 2.5 The fermion determinant

For every square matrix \(P\),

\[
\det(I+P)
=
\sum_{S\subseteq\{1,\ldots,n\}}\det P[S,S].
\]

The empty principal minor equals \(1\). All other terms are nonnegative
because \(P\) is totally nonnegative. Hence

\[
\det(I+P)\geq1.
\]

## 3. Exact boundary counterexample

The theorem does not extend to arbitrary directed graphs. Let \(E_{ij}\)
denote a three-dimensional matrix unit. Since \(E_{ij}^2=0\),

\[
e^{E_{ij}}=I+E_{ij}.
\]

Adding the directed closing edge \(E_{31}\) yields the exact seven-slice word

\[
P=(I+E_{12})^3(I+E_{31})(I+E_{23})^3
=
\begin{pmatrix}
1&3&9\\
0&1&3\\
1&0&1
\end{pmatrix}.
\]

Consequently,

\[
I+P=
\begin{pmatrix}
2&3&9\\
0&2&3\\
1&0&2
\end{pmatrix},
\qquad
\boxed{\det(I+P)=-1}.
\]

This is an exact integer certificate. It shows that the open ordered-chain
geometry is essential. The certificate excludes the enlarged class with an
independent directed closing edge; it does not by itself prove that every
Hermitian periodic-chain formulation has a sign problem.

## 4. Reduction and novelty checks

The claims below concern the whole family \(\mathcal T_n\). Individual
matrices or smaller subfamilies may of course satisfy older sufficient
conditions.

### 4.1 Previous conformal-orthogonal candidate

The previous candidate required a fixed positive-definite matrix \(H\) and

\[
A=\alpha I+K,\qquad K^{\mathsf T}H+HK=0.
\]

The new class contains every nonscalar real diagonal matrix \(D\). If such a
\(D\) admitted the decomposition above, \(K=D-\alpha I\) would have real
eigenvalues. But an \(H\)-skew matrix is similar to a real skew-symmetric
matrix and therefore has purely imaginary eigenvalues. Both statements can
hold only when \(D-\alpha I=0\), contradicting the choice of \(D\).

Thus \(\mathcal T_n\) is not contained in the previous candidate.

### 4.2 Fixed split metric

The split-orthogonal and split-semigroup conditions require a fixed
nondegenerate indefinite metric \(\eta\) satisfying

\[
A^{\mathsf T}\eta+\eta A=0
\]

or a common one-sided semidefinite inequality.

The family \(\mathcal T_n\) contains \(I\) and \(-I\). Applying the same
one-sided inequality to both forces equality, while \(A=I\) then gives
\(2\eta=0\), a contradiction. Similarity transformations cannot remove
this obstruction because \(I\) remains \(I\).

Even after allowing a central scalar to be removed from each generator,
all traceless diagonal matrices \(D\) and \(-D\) remain. For \(n\geq3\),

\[
D\eta+\eta D=0
\]

for every traceless diagonal \(D\) forces every entry of \(\eta\) to vanish.

### 4.3 No common Kramers symmetry

Suppose a common antiunitary symmetry \(\Theta=UK\) fixes every real
generator. Then \(U\) commutes with every generator. The family contains

\[
E_{ii},\qquad E_{i,i+1},\qquad E_{i+1,i}.
\]

These matrix units generate the full real matrix algebra. Its complex
commutant consists only of scalars, so \(U=\lambda I\) and

\[
\Theta^2=U\overline U=|\lambda|^2I,
\]

which cannot equal the Kramers value \(-I\).

### 4.4 No 2024 Majorana contraction structure

The 2024 contraction-semigroup condition requires a fixed real orthogonal
skew-symmetric matrix \(J_2\) such that

\[
i\left(J_2V-\overline VJ_2\right)\preceq0
\]

for every Majorana kernel \(V\), together with a separate \(J_1\) reality
condition.

For a real diagonal number-conserving generator \(D\), the Majorana kernel,
up to a positive scalar Fock factor, is

\[
V(D)=iR(D),\qquad
R(D)=
\begin{pmatrix}
0&D\\
-D&0
\end{pmatrix}.
\]

Because the family contains both \(D\) and \(-D\), the inequality must be an
equality:

\[
J_2R(D)+R(D)J_2=0
\]

for every real diagonal \(D\).

Write

\[
J_2=
\begin{pmatrix}
X&Y\\
Z&W
\end{pmatrix}.
\]

Taking \(D=I\) gives \(Z=Y\) and \(W=-X\). Varying diagonal \(D\)
forces \(X\) and \(Y\) to be diagonal. Skew-symmetry then forces
\(X=Y=0\), hence \(J_2=0\), contradicting orthogonality.

The obstruction also survives a fixed complex orthogonal Majorana change of
basis. Pulling back its antiunitary operator gives \(CK\), where
\(CR(D)+R(D)C=0\). On each orbital the general block has the form

\[
C_i=
\begin{pmatrix}
x_i&y_i\\
y_i&-x_i
\end{pmatrix}.
\]

The diagonal entries of \(C_i\overline{C_i}\) are
\(|x_i|^2+|y_i|^2\), so \(C\overline C=-I\) is impossible.

Since the 2024 paper identifies its symmetric-\(J_1\) branch with Majorana
reflection positivity and its equality cases with the earlier
Majorana-symmetry constructions, this excludes a fixed old structure
covering the full family.

## 5. Interacting determinant-QMC realization

Consider an open chain of one-component spinless fermions:

\[
H=
-\sum_{i=1}^{n-1}t_i
\left(c_i^\dagger c_{i+1}+c_{i+1}^\dagger c_i\right)
-\sum_i\mu_i n_i
-\sum_{i=1}^{n-1}V_i n_i n_{i+1},
\]

with \(t_i\geq0\), \(V_i\geq0\), and arbitrary chemical potentials
\(\mu_i\). The final term is an attractive nearest-neighbor density
interaction.

For \(a=\Delta\tau V_i\) and \(N_i=n_i+n_{i+1}\),

\[
n_i n_{i+1}=\frac{N_i^2-N_i}{2},
\]

and the real Gaussian identity gives

\[
e^{a n_i n_{i+1}}
=
e^{-aN_i/2}
\int_{\mathbb R}\frac{d\phi}{\sqrt{2\pi}}\,
e^{-\phi^2/2}
e^{\sqrt a\,\phi N_i}.
\]

The auxiliary-field measure is positive, and every field value contributes
only a real diagonal one-body generator. The kinetic imaginary-time
generator has adjacent off-diagonal entries
\(\Delta\tau t_i\geq0\). Thus every kinetic, chemical-potential, and
auxiliary-field factor lies in the semigroup generated by
\(\mathcal T_n\).

For every auxiliary-field configuration,

\[
w(\phi)
=
f(\phi)
\det\left(I+\prod_\ell e^{A_\ell(\phi)}\right)
\geq f(\phi)>0,
\]

where \(f(\phi)\) is the positive Gaussian factor.

The construction uses one fermion flavor and arbitrary chemical potential,
so it is not restricted to half filling. One-dimensional versions may also
admit worldline or Jordan–Wigner sign-free algorithms; the contribution here
is the determinant-level theorem.

## 6. Vandermonde and the physical meaning of total positivity

The total-positivity mechanism has a direct fermionic interpretation rather
than being an arbitrary matrix trick.

### 6.1 Slater determinants

For one-particle orbitals \(\phi_j(x)=x^j\), the \(N\)-fermion Slater
matrix is Vandermonde:

\[
\Phi_{ij}=x_i^{j-1},\qquad
\det\Phi=\prod_{i<j}(x_j-x_i).
\]

For \(N\) noninteracting spinless fermions in a one-dimensional harmonic
trap, the occupied orbitals are Hermite polynomials times Gaussians. Their
ground-state Slater determinant reduces to

\[
\Psi_0(x_1,\ldots,x_N)
=
C e^{-\sum_i x_i^2/(2\ell^2)}
\prod_{i<j}(x_j-x_i).
\]

Within the ordered chamber \(x_1<\cdots<x_N\), this wavefunction has fixed
sign. The zeros at collisions are the Pauli principle in coordinate space.

### 6.2 Imaginary-time heat kernels

The free-particle imaginary-time kernel is

\[
K_\tau(x,y)
=
\frac{1}{\sqrt{4\pi\lambda\tau}}
\exp\left[-\frac{(x-y)^2}{4\lambda\tau}\right].
\]

It factors as

\[
K_\tau(x,y)
=
C_\tau
e^{-x^2/(4\lambda\tau)}
e^{xy/(2\lambda\tau)}
e^{-y^2/(4\lambda\tau)}.
\]

The kernel \(e^{xy}\) is strictly totally positive, and positive row and
column scaling preserves all minor signs. The harmonic-oscillator Mehler
kernel has the same positive-Gaussian-times-\(e^{cxy}\) structure.

For ordered initial and final positions, the \(N\)-fermion propagator is

\[
K_\tau^{(N)}(\mathbf x,\mathbf y)
=
\det[K_\tau(x_i,y_j)]_{i,j=1}^N\geq0.
\]

This is the Karlin–McGregor noncollision determinant: in one dimension,
worldlines cannot exchange their order without crossing. Total
nonnegativity is the one-particle linear-algebra encoding of this
noncrossing fermion propagation.

The Vandermonde matrix is a confluent limit of the same kernel:

\[
\left.
\frac{\partial^{j-1}}{\partial y^{j-1}}e^{xy}
\right|_{y=0}
=x^{j-1}.
\]

Thus heat kernels, noncrossing paths, Vandermonde Slater states, and the
tridiagonal Metzler theorem are different presentations of one ordered
one-dimensional mechanism.

### 6.3 Relation to the grand-canonical determinant

For a one-particle propagator \(P\),

\[
\det(I+P)
=
\sum_{k=0}^n\operatorname{Tr}_{\wedge^k}P.
\]

The matrix entries of \(\wedge^kP\) are the \(k\)-particle Slater
minors. The determinant-QMC weight is therefore the sum of the fixed-particle
number propagation traces.

An additional direction, not yet claimed as a theorem here, is projector QMC
with Vandermonde or Hermite boundary Slater matrices:

\[
\det\left(
\Phi_{\mathrm L}^{\mathsf T}
e^{A_1}\cdots e^{A_L}
\Phi_{\mathrm R}
\right).
\]

The Cauchy–Binet formula suggests a natural positivity route when both the
bulk propagators and boundary orbital matrices lie in compatible
total-positivity cones.

## 7. Verification

Run:

```bash
python tracks/qmc/solutions/zhong-guo-ren-neng-fei/verify.py
```

The fixed-seed default run records:

- dimensions \(1\) through \(8\);
- depths \(1,2,4,8\);
- 250 random samples per dimension-depth cell;
- 8000 candidate products in total;
- zero negative determinants;
- zero determinants below \(1\) at tolerance;
- 64 exhaustive all-minor checks with no negative minor;
- 96 principal-minor identity checks;
- a five-orbital direct Fock-space trace cross-check;
- 600 split-Lie and 600 split-cone positive anchor samples;
- exact negative and zero controls for the other split-group components;
- commutant and Majorana-\(J_2\) linear-algebra obstruction checks;
- the exact integer directed-cycle counterexample.

The generated `results.json` records the seed, protocol, extrema, residuals,
and exact certificate.

Randomized tests support the implementation but do not replace the proof.

## 8. Literature checked

- L. Wang, Y.-H. Liu, M. Iazzi, M. Troyer, and G. Harcos,
  [Split orthogonal group: A guiding principle for sign-problem-free
  fermionic simulations](https://arxiv.org/abs/1506.05349).
- Z. C. Wei, C. Wu, Y. Li, S. Zhang, and T. Xiang,
  [Majorana Positivity and the Fermion sign problem of Quantum Monte Carlo
  Simulations](https://arxiv.org/abs/1601.01994).
- Z.-X. Li, Y.-F. Jiang, and H. Yao,
  [Majorana-time-reversal symmetries](https://arxiv.org/abs/1601.05780).
- Z.-C. Wei,
  [Semigroup approach to the sign problem in quantum Monte Carlo
  simulations](https://arxiv.org/abs/1712.09412), v3.
- M. Margaliot and E. D. Sontag,
  [Revisiting Totally Positive Differential Systems](https://arxiv.org/abs/1802.09590).
- M. Katori and H. Tanemura,
  [Noncolliding Brownian Motion and Determinantal
  Processes](https://arxiv.org/abs/0705.2460).
- P. K. Panigrahi and M. Sivakumar,
  [Laughlin Wave Function and One-Dimensional Free
  Fermions](https://arxiv.org/abs/cond-mat/9509039).
- MathOverflow,
  [How to prove this determinant is positive?](https://mathoverflow.net/questions/204460/how-to-prove-this-determinant-is-positive)
  and
  [How to prove this determinant is positive II?](https://mathoverflow.net/questions/229788/how-to-prove-this-determinant-is-positive-ii).

Targeted searches for total nonnegativity, tridiagonal Metzler generators,
fermion determinants, and auxiliary-field QMC did not reveal a source using
the theorem above as a determinant-QMC guiding principle. This is a search
record, not proof of publication priority.

## 9. Reproducible claim

The following statement is supported by the proof and artifacts in this
directory:

> Arbitrary finite products of exponentials of real tridiagonal Metzler
> generators are totally nonnegative. Their grand-canonical fermion
> determinants are at least one. The generator family has an open-chain,
> off-half-filled interacting auxiliary-field realization and is not covered
> as a whole by the fixed split, Kramers, or 2024 Majorana contraction
> conditions tested here.
