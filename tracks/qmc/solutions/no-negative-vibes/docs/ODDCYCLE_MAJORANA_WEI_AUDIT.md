# Exact Majorana/Wei audit for the final oddcycle alphabet

Date: 2026-07-30

## Result and scope

Let

\[
B(p)=
\begin{pmatrix}
0&0&2&0&0\\
2&0&0&0&0\\
0&2&0&p&0\\
0&0&0&1&1\\
0&0&-1&0&1
\end{pmatrix}
\]

and

\[
\mathcal A=
\{B(1/1000),B(1/1000)^{\mathsf T},
  B(4/5),B(4/5)^{\mathsf T}\}.
\]

The final alphabet lies outside the sufficient class defined by Wei's fixed
\(J_1,J_2\) contraction conditions, even after a fixed complex orthogonal
Majorana basis change.

This is a no-go theorem for that sufficient class, including its
Majorana-reflection-positive and anticommuting-MTR equality cases.  It is
not a classification of sign-free QMC.  In particular, it does not exclude
unrelated fermion-bag, loop, worldline, or future sign-free mechanisms.

## Nambu lift and pulled-back Wei metric

For five complex modes use

\[
\Psi=(c,c^\dagger)^{\mathsf T},\qquad
\Omega=
\begin{pmatrix}
0&I_5\\
I_5&0
\end{pmatrix}.
\]

The number-conserving lift of a real invertible one-particle matrix is

\[
G(B)=\operatorname{diag}(B^{-1},B^{\mathsf T}),
\qquad
G(B)^{\mathsf T}\Omega G(B)=\Omega.
\tag{1}
\]

The order in (1) is essential.  Replacing it by
\(\operatorname{diag}(B,B^{-\mathsf T})\) changes the contraction
orientations and is not the adjoint action on \((c,c^\dagger)\).
Every letter has \(\det B=8>0\).  The scalar separating the exterior lift
\(\Gamma_\wedge(B)\) from the corresponding Majorana Spin lift is therefore
\(\sqrt{\det B}>0\), so it cannot change a configuration sign.

In Wei's canonical Majorana basis the contraction metric is
\(\eta_0=iJ_2\), where \(J_2\) is real, orthogonal, and skew-symmetric.
Represent an arbitrary fixed complex orthogonal Majorana basis in Nambu
coordinates by an invertible matrix \(S\) satisfying

\[
S^{\mathsf T}\Omega S=I_{10}.
\]

Pull the canonical metric back as

\[
\eta=S^{-\dagger}\eta_0S^{-1}.
\tag{2}
\]

Every Wei certificate then supplies this Hermitian matrix \(\eta\) such
that, for all \(B\in\mathcal A\),

\[
\eta-G(B)^\dagger\eta G(B)\succeq0
\tag{3}
\]

up to the harmless common reversal associated with the expansion
orientation.  Orthogonality and skew-symmetry of \(J_2\) additionally give

\[
\eta\Omega^{-1}\eta^{\mathsf T}=-\Omega.
\tag{4}
\]

Indeed, \(S^{\mathsf T}\Omega S=I\) implies
\(\Omega^{-1}=SS^{\mathsf T}\).  Since
\(\eta_0\eta_0^{\mathsf T}=-I\), substituting (2) gives (4) directly
(and \(\Omega\) is real).  Equation (4) is therefore the compatibility
sign that survives arbitrary fixed complex orthogonal basis freedom.

## Frozen dual forces the equality boundary

Write

\[
\eta=
\begin{pmatrix}
H&K\\
K^\dagger&D
\end{pmatrix},
\qquad H=H^\dagger,\quad D=D^\dagger.
\]

For \(B_j\) and \(B_j^{\mathsf T}\), the upper-left principal blocks of
(3) are

\[
H-B_j^{-\mathsf T}HB_j^{-1}\succeq0,\qquad
H-B_j^{-1}HB_j^{-\mathsf T}\succeq0.
\tag{5}
\]

Congruence by \(B_j^{\mathsf T}\) and \(B_j\), respectively, puts
\(R=-H\) into the two orientations of the frozen exact
Gordan--Stiemke dual.  The lower-right blocks for \(D\) already have those
two orientations.

The frozen dual has exact zero cancellation, trace-one normalization, and
four positive-definite rational multipliers.  Pairing it with the
positive-semidefinite nonstrict gaps gives a sum of nonnegative traces
whose exact total is zero.  Every diagonal-block gap must therefore vanish.
A positive-semidefinite block matrix with a zero diagonal principal block
has zero off-diagonal block.  Consequently,

\[
K B_j=B_jK,\qquad
K B_j^{\mathsf T}=B_j^{\mathsf T}K.
\tag{6}
\]

## Exact scalar commutant and zero diagonal blocks

The machine replay stacks all entries of

\[
E_{ab}A-AE_{ab},\qquad A\in\mathcal A,
\]

into a rational linear system with 25 unknowns.  Its exact rank is 24.
Since \(I_5\) lies in the nullspace, the common complex commutant is exactly
\(\mathbb C I_5\).

The alphabet is closed under transpose.  A common invariant subspace would
therefore have an invariant orthogonal complement, whose projector would
belong to the commutant.  Scalar commutant thus makes the alphabet
irreducible.

If a nonzero \(H\) obeyed both equality cases of (5), its kernel would be
invariant under every letter.  Irreducibility would make \(H\) invertible.
But every letter has determinant eight, whereas

\[
B_j^{\mathsf T}HB_j=H
\quad\Longrightarrow\quad
\det H=64\det H,
\]

a contradiction.  Thus \(H=0\), and the same argument gives \(D=0\).
Equation (6) then leaves only

\[
\eta=
\begin{pmatrix}
0&kI_5\\
\bar kI_5&0
\end{pmatrix}.
\tag{7}
\]

## Exact compatibility-sign contradiction

It is enough to multiply the two-dimensional block coefficients of (7).
With

\[
\omega=\begin{pmatrix}0&1\\1&0\end{pmatrix},\qquad
e=\begin{pmatrix}0&k\\\bar k&0\end{pmatrix},
\]

exact symbolic algebra gives

\[
e\omega e^{\mathsf T}=|k|^2\omega.
\tag{8}
\]

Tensoring (8) with \(I_5\) produces
\(\eta\Omega^{-1}\eta^{\mathsf T}=|k|^2\Omega\), which has sign \(+1\).
The Wei orthogonal-complex-structure identity (4) requires sign \(-1\).
The singular case \(k=0\) also fails (4).  No pulled-back Wei contraction
metric exists.

## Solver-independent replay

The implementation is
`oracle/oddcycle_majorana_wei_audit.py`; its publication-gate regression is
`tests/test_oddcycle_majorana_wei_audit.py`.  Run on WSL with one BLAS
thread:

```bash
cd tracks/qmc/solutions/no-negative-vibes
env OMP_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 MKL_NUM_THREADS=1 \
  NUMEXPR_NUM_THREADS=1 PYTHONHASHSEED=0 \
  python -m oracle.oddcycle_majorana_wei_audit
env OMP_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 MKL_NUM_THREADS=1 \
  NUMEXPR_NUM_THREADS=1 PYTHONHASHSEED=0 \
  python -m pytest -q \
  tests/test_oddcycle_majorana_wei_audit.py \
  tests/test_oddcycle_final_certificate.py
```

The development replay returned exact commutant rank 24, nullity one,
four positive-definite dual multipliers, boundary sign \(+1\), Wei sign
\(-1\), and exact payload SHA-256
`0290bd707ab6aa729c2ad87526beae74168dbc554aa4b424e9fead3c62163ed6`.
The authoritative source commit and raw JSON are populated by the final
clean-worktree archival replay.

No SDP solver, eigensolver, random sampler, logarithm, or parameter scan is
used by this audit.

## Primary sources

- Wei et al., *Majorana Positivity and the Fermion Sign Problem of Quantum
  Monte Carlo Simulations*, *Phys. Rev. Lett.* **116**, 250601 (2016),
  arXiv:1601.01994.
- Li, Jiang, and Yao, *Majorana-time-reversal symmetries: a fundamental
  principle for sign-problem-free quantum Monte Carlo simulations*,
  *Phys. Rev. Lett.* **117**, 267002 (2016), arXiv:1601.05780.
- Wei, *Semigroup approach to the sign problem in quantum Monte Carlo
  simulations*, *Phys. Rev. B* **110**, 075146 (2024),
  arXiv:1712.09412v3.
