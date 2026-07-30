# Oddcycle Majorana/Wei no-go design

Date: 2026-07-30

## Objective

Determine whether the final four-letter oddcycle alphabet can satisfy the
full sufficient condition of Wei's 2024 contraction-semigroup framework
after an arbitrary fixed complex orthogonal change of Majorana basis.

The result must distinguish:

- exclusion of one real symmetric five-dimensional common metric, which is
  already exact;
- exclusion of the full ten-Majorana contraction condition, which is the new
  target; and
- mechanisms outside Wei's sufficient condition, which remain outside the
  claim.

## Chosen route

Use a necessary-condition reduction in Nambu space.  This is preferable to
direct nonconvex searches over basis transformations and Clifford structures:
a failed nonlinear search is not a no-go certificate, while the reduction
uses only exact rational linear algebra and the already frozen dual.

The paper's novelty statement is upgraded only after the independent exact
replay passes.

## Algebraic representation

For five complex fermion modes write

\[
\Psi=(c,c^\dagger)^{\mathsf T},\qquad
\Omega=
\begin{pmatrix}
0&I_5\\
I_5&0
\end{pmatrix}.
\]

The number-conserving lift of a real invertible one-particle matrix \(B\) is

\[
G(B)=\operatorname{diag}(B,B^{-\mathsf T}),\qquad
G(B)^{\mathsf T}\Omega G(B)=\Omega .
\]

All four oddcycle letters have positive determinant and a real logarithm.
The scalar separating the complex-fermion lift from the Majorana Spin lift
is therefore positive, so it does not alter the configuration sign.

## Necessary Wei metric

In Wei's canonical Majorana basis, \(J_2\) is real, orthogonal, and
skew-symmetric, and the contraction metric is
\(\eta_0=iJ_2\).  Allow an arbitrary fixed complex Majorana basis by choosing
an invertible \(S\) with

\[
S^{\mathsf T}\Omega S=I_{10}.
\]

Pulling the metric back to Nambu space gives

\[
\eta=S^{-\dagger}\eta_0S^{-1}.
\]

Every Wei certificate therefore supplies a Hermitian \(\eta\) satisfying,
for all four letters,

\[
\eta-G(B)^\dagger\eta G(B)\succeq0
\tag{1}
\]

after reversing the overall sign of \(\eta\) if the expansion orientation is
used.  Orthogonality and skew-symmetry of \(J_2\) also impose

\[
\eta\Omega^{-1}\eta^{\mathsf T}=-\Omega .
\tag{2}
\]

Equation (2) retains the sign that distinguishes an orthogonal complex
structure from the canonical particle-hole bilinear form.

## Exact boundary reduction

Partition

\[
\eta=
\begin{pmatrix}
H&K\\
K^\dagger&D
\end{pmatrix},
\qquad H=H^\dagger,\quad D=D^\dagger .
\]

The upper-left principal blocks of (1), for \(B_j\) and \(B_j^{\mathsf T}\),
are

\[
H-B_j^{\mathsf T}HB_j\succeq0,\qquad
H-B_jHB_j^{\mathsf T}\succeq0.
\tag{3}
\]

Pairing (3) with the four frozen positive-definite dual multipliers gives
zero total trace by exact dual cancellation.  Every term is nonnegative, so
all four matrices in (3) vanish.  The same argument, after congruence by
\(B_j\) and \(B_j^{\mathsf T}\), makes the two lower-right gaps vanish.
A positive-semidefinite block matrix with a zero diagonal principal block
has a zero corresponding off-diagonal block.  Consequently,

\[
K B_j=B_jK,\qquad K B_j^{\mathsf T}=B_j^{\mathsf T}K.
\tag{4}
\]

## Scalar-commutant lemma

Let \(B_0=B(a)\), \(B_1=B(b)\), with \(a\ne b\).  Their difference is a
nonzero multiple of \(E_{34}\), and the transpose difference is a nonzero
multiple of \(E_{43}\).  Any common commutant element \(X\) therefore
commutes with both matrix units.  It has no entries joining
\(\operatorname{span}(e_3,e_4)\) to its complement and restricts to
\(\lambda I_2\) on that span.

Using

\[
B(p)e_1=2e_2,\quad
B(p)e_2=2e_3,\quad
B(p)e_5=e_4+e_5
\]

in \(XB(p)=B(p)X\) successively gives
\(Xe_2=\lambda e_2\), \(Xe_1=\lambda e_1\), and
\(Xe_5=\lambda e_5\).  Hence the common complex commutant of the four
letters is exactly \(\mathbb C I_5\).

If a nonzero \(H\) obeyed both equalities in (3), its kernel would be
invariant under every \(B_j\) and \(B_j^{\mathsf T}\).  The scalar-commutant
lemma makes the alphabet irreducible, so \(H\) would be invertible.  But

\[
\det H=\det(B_j)^2\det H=64\det H
\]

is impossible.  Thus \(H=0\); the same reasoning gives \(D=0\).  Equation
(4) gives \(K=kI_5\), so every possible boundary metric is

\[
\eta=
\begin{pmatrix}
0&kI_5\\
\bar kI_5&0
\end{pmatrix}.
\tag{5}
\]

## Final incompatibility

For (5),

\[
\eta\Omega^{-1}\eta^{\mathsf T}=|k|^2\Omega ,
\]

which cannot equal \(-\Omega\).  The case \(k=0\) is singular and also fails
(2).  Therefore no full Wei contraction certificate exists for the final
alphabet, even after a fixed complex orthogonal Majorana basis change.

Because Wei's equality cases contain the Majorana reflection-positive and
the two anticommuting-MTR sufficient classes, this also excludes those
sufficient explanations for this alphabet.  It does not exclude unrelated
fermion-bag, loop, worldline, or future sign-free mechanisms.

## Replay design

Add one solver-independent module and one focused test:

```text
oracle/oddcycle_majorana_wei_audit.py
tests/test_oddcycle_majorana_wei_audit.py
```

The module will:

1. reuse the frozen exact dual and verify all four multipliers are positive
   definite, normalized, and exactly cancelling;
2. construct the rational main alphabet;
3. build exact linear commutant constraints and verify complex nullity one;
4. replay the hand commutant lemma through exact ranks;
5. report that the only Nambu boundary form is (5);
6. multiply symbolic \(2\times2\) block coefficients to verify the
   \(+\lvert k\rvert^2\Omega\) versus \(-\Omega\) incompatibility; and
7. emit a compact JSON certificate with the source commit and exact digest.

No SDP, logarithm, eigensolver, random number generator, or parameter scan
belongs in this replay.

## Acceptance gates

- The focused test first fails because the audit module is absent.
- Exact commutant nullity is one over the rationals.
- The frozen dual replay passes without a solver.
- The boundary metric has zero diagonal blocks and scalar off-diagonal
  blocks.
- The compatibility signs are exactly `+1` for the boundary and `-1` for a
  Wei orthogonal complex structure.
- The existing main and robust certificate regressions remain green on WSL.
- Only after those gates pass may the paper abstract and challenge audit say
  that the Wei/Majorana sufficient condition is excluded.

## Failure policy

If any exact gate fails, retain the current narrow novelty claim.  Record the
failed identity and do not replace it with a floating feasibility result.
No broad scan is authorized by this design.

## Primary-source basis

- [Wei, *Semigroup approach to the sign problem in quantum Monte Carlo
  simulations*, arXiv:1712.09412v3](https://arxiv.org/html/1712.09412v3):
  the element contraction inequality, fixed \(J_1,J_2\) conditions, complex
  orthogonal Majorana basis allowance, and inclusion of the earlier
  reflection-positive and MTR equality cases.
- [Wei et al., *Majorana Positivity and the Fermion sign problem of Quantum
  Monte Carlo Simulations*,
  arXiv:1601.01994v5](https://arxiv.org/abs/1601.01994):
  the Majorana reflection-positive and Majorana Kramers sufficient
  conditions.
- [Li, Jiang, and Yao, *Majorana-time-reversal symmetries: a fundamental
  principle for sign-problem-free quantum Monte Carlo simulations*,
  arXiv:1601.05780v3](https://arxiv.org/abs/1601.05780):
  the two anticommuting-MTR sign-free symmetry classes.
- [Quantum Harness challenge
  #121](https://github.com/QuantumBFS/quantum.harness/issues/121):
  the explicit novelty filter and physical-realization requirements.
