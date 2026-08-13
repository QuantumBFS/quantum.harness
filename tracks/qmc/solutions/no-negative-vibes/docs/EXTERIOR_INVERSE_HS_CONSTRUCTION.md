# Transpose-paired exterior candidates: exact inverse Hamiltonian construction

Date: 2026-07-29

## Result

The physical reverse map is automatic for every exact exterior candidate
card, without assuming locality or a one-particle logarithm for the complete
atom.  Let the card contain a real matrix \(B\), its transpose
\(B^{\mathsf T}\), and their shared rational coefficient \(q>0\).  On the
complete number-conserving Fock space define

\[
\Gamma(B)\big|_{\mathcal H_k}=\wedge^k B,\qquad
H_B=-q\left[\Gamma(B)+\Gamma(B^{\mathsf T})\right].
\]

Because exterior powers commute with transposition,

\[
\Gamma(B^{\mathsf T})=\Gamma(B)^{\mathsf T}
                    =\Gamma(B)^\dagger ,
\]

so \(H_B\) is an exact real Hermitian Hamiltonian.  It is generally nonlocal
and can contain number-conserving terms through body order \(N\); this is
allowed by the present reverse-construction scope.

The interaction-expansion vertex has the two-field positive decomposition

\[
-H_B=q\,\Gamma(B)+q\,\Gamma(B^{\mathsf T})
    =2q\,\mathbb E_{s\in\{0,1\}}\Gamma(B_s),
\quad B_0=B,\quad B_1=B^{\mathsf T}.
\]

Thus every auxiliary scalar is positive.  Each exact card also stores a
finite product factorization of \(B_s\) into real Gaussian micro-gates:
rational shears are \(\exp(qE_{ij})\), positive diagonals have real diagonal
logs, and the weighted odd cycle has its declared real-log witness.  The
construction therefore does not require the complete product \(B\) to be
represented by one real logarithm.

## Exact QMC identity

For an ordered branch history \(w=(s_1,\ldots,s_L)\), functoriality and the
fermionic trace identity give

\[
\begin{aligned}
\operatorname{Tr}_{\rm Fock}
  [\Gamma(B_{s_1})\cdots\Gamma(B_{s_L})]
 &=\operatorname{Tr}_{\rm Fock}
   \Gamma(B_{s_1}\cdots B_{s_L})\\
 &=\det[I+B_{s_1}\cdots B_{s_L}].
\end{aligned}
\]

Consequently

\[
\operatorname{Tr}[(-H_B)^L]
=\sum_{w\in\{0,1\}^L}
 q^L\det[I+B_{s_1}\cdots B_{s_L}].
\]

This is the exact bridge from a candidate matrix semigroup to a Hermitian
many-fermion Hamiltonian with a positive-coefficient continuous-time
Gaussian/HS expansion.

## What remains open

The inverse map does **not** by itself prove that every determinant on the
right-hand side is nonnegative.  There are three logically separate levels:

1. transpose pairing proves Hermiticity and positive auxiliary coefficients;
2. finite word tests provide numerical or exact finite-depth evidence;
3. a shared exterior cone (or a different semigroup theorem) proves
   nonnegativity at arbitrary depth.

For `exact5-oddcycle-block-pair`, the exact shallow sector-trace gate leaves
the probe seeds

```text
13, 61, 97, 100, 117, 124, 132, 147, 211, 238, 244
```

as the current transform-search priorities.  They are not yet theorem-level
sign-free candidates.  The next decisive numerical/mathematical test is to
search grades 2 and 3 for a common exact simplicial cone for both \(B\) and
\(B^{\mathsf T}\).  One exact all-grade hit immediately upgrades the
corresponding \(H_B\) above to an arbitrary-order sign-free physical model.

## Reproducible verifier

`oracle/exterior_inverse_hs.py` reconstructs all Fock minors with SymPy exact
arithmetic, builds \(H_B\), and verifies both the history trace/determinant
identity and the complete auxiliary-field Taylor sum.  The focused tests in
`tests/test_exterior_inverse_hs.py` cover all eleven prioritized seeds and
orders \(L=0,\ldots,4\) for seed 13.
