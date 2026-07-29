# Targeted novelty and priority audit for the polyhedral and Perron-compound criteria

Date: 2026-07-29

Status: targeted primary-source search, not a proof of priority. No claim below is
based merely on the absence of a search hit.

The search was refreshed on 2026-07-29 against the arXiv/APS primary records,
the Semantic Scholar citation graph of arXiv:1712.09412, the issue #121 comment
thread, and every open challenge PR in the upstream repository.  Query families
combined the physics vocabulary

```text
fermion determinant / determinant QMC / sign-problem-free / auxiliary field
```

with the matrix vocabulary

```text
common norm / logarithmic norm / matrix measure / polyhedral Lyapunov /
Banach contraction / H-matrix / Metzler / cone / compound matrix
```

and separately searched citations of the 2015 split-orthogonal, 2016 Majorana,
2020 intrinsic-sign, 2024 semigroup, and 2025 time-reversal-positivity papers.
This protocol can falsify a priority claim by finding prior art; it cannot prove
priority by failing to find it.

## 1. Search outcome

The targeted search found no QMC paper that directly uses either

1. a common l_infinity or general polyhedral/Banach contraction to prove
   det(I+word)>=0 for arbitrary auxiliary-field words; or
2. a common proper Perron cone together with strict second-compound contraction to
   prove det(I+word)>=0 while allowing one expanding one-particle mode.

It also found no direct occurrence of the complete combination

    two S3 orbits + open parameter family + exact no-common-quadratic witness
    + odd-dimensional full-span complex-CAR obstruction + interacting Fock twirl.

These are negative targeted-search results, not exhaustive historical proofs.

## 2. Closest QMC sources

1. Z.-C. Wei, Semigroup approach to the sign problem in quantum Monte Carlo
   simulations, Phys. Rev. B 110, 075146 (2024):
   https://doi.org/10.1103/PhysRevB.110.075146

   This is the fixed Hermitian indefinite-metric framework, including its stated
   complex-orthogonal Majorana extension. The odd-n/full-span theorem in
   `main_theorem.md` separates the supplied support from these
   sufficient classes, not from every possible positive decomposition.

   Wei's 2025 follow-up, *Time-reversal positivity*, arXiv:2510.06226,
   develops a cone-theoretic positivity tool for the time-reversal-symmetric
   non-Hermitian Hubbard setting.  It is prior art for the time-reversal cone
   language, but it retains a fixed antiunitary structure and does not supply the
   real common-Banach-norm determinant criterion used here.

2. L. Wang et al., Split orthogonal group: a guiding principle for sign-problem-free
   fermionic simulations, Phys. Rev. Lett. 115, 250601 (2015):
   https://arxiv.org/abs/1506.05349

3. Z.-C. Wei et al., Majorana positivity and the fermion sign problem, Phys. Rev.
   Lett. 116, 250601 (2016):
   https://arxiv.org/abs/1601.01994

4. Z.-X. Li, Y.-F. Jiang, and H. Yao, Majorana-time-reversal symmetries, Phys. Rev.
   Lett. 117, 267002 (2016):
   https://arxiv.org/abs/1601.05780

Items 2-4 are the principal group, reflection-positivity, and MTR baselines.

5. X.-Y. Xu et al., Monte Carlo study of lattice compact quantum electrodynamics
   with fermionic matter, Phys. Rev. X 9, 021022 (2019), Appendix A:
   https://arxiv.org/abs/1807.07574

   The appendix gives the pseudo-unitary SU(n,n) route constraining the determinant
   to be real. It is prior art for complex pseudo-unitary phase constraints, not the
   common-polyhedral real A/B positivity mechanism claimed here.

6. Contemporary challenge PR #259 proves a tridiagonal Metzler/total-nonnegative
   route and maps it to one-dimensional noncrossing/Jordan-Wigner physics:
   https://github.com/QuantumBFS/quantum.harness/pull/259

   That independently submitted route overlaps the exploratory
   `total_nonnegative_semigroup` direction and is excluded from this package. It
   does not use the signed A/B polyhedral family or the Perron-plus-compound
   orientation criterion.

7. O. Golan, A. Smith, and Z. Ringel, Intrinsic sign problem in fermionic and
   bosonic chiral topological matter, Phys. Rev. Research 2, 043032 (2020):
   https://arxiv.org/abs/2005.05566

   Appendix F is an important scope check on local and homogeneous known DQMC
   design principles.  The present support-level separation is not an intrinsic
   sign-problem theorem for a phase and must not be advertised as one.

8. C. Wu and S.-C. Zhang, Phys. Rev. B 71, 155115 (2005), together with the
   finite-density designer models of Berg, Metlitski, and Sachdev, Science 338,
   1606 (2012), and Schattner et al., Phys. Rev. X 6, 031028 (2016), are controls
   against an incorrect finite-density novelty claim.  Their nonnegative weights
   follow from determinant squaring or a fixed Kramers/conjugate pairing.  Adding
   a duplicated flavor to the present real support would therefore be useful as a
   control but not a new mechanism.

The upstream issue thread also points to Appendix A of Phys. Rev. X 9, 021022
(2019), where a pseudo-unitary SU(n,n) condition makes the determinant real.
That observation is included here as prior art even though reality alone is weaker
than the nonnegativity theorem sought in issue #121.

## 3. Closest control and matrix sources

1. F. Blanchini, Nonquadratic Lyapunov functions for robust control, Automatica 31,
   451-461 (1995):
   https://doi.org/10.1016/0005-1098(94)00133-4

2. T. V. Nguyen et al., Relations between common quadratic Lyapunov functions and
   common infinity-norm Lyapunov functions, Trans. SICE 40, 1067-1069 (2004), and
   the discrete-time counterpart:
   https://doi.org/10.1093/ietfec/e89-a.6.1794

3. P. Mason, Y. Chitour, and M. Sigalotti, On universal classes of Lyapunov
   functions for linear switched systems, Automatica 155, 111155 (2023):
   https://doi.org/10.1016/j.automatica.2023.111155

These sources make clear that polyhedral common Lyapunov functions and stable
switched families without a common quadratic metric are established control theory.
The bare l_infinity cone is not new mathematics.

4. V. Yu. Protasov, Perron matrix semigroups (2025/2026):
   https://arxiv.org/abs/2502.10571

5. O. Y. Kushel, Cone-theoretic generalization of total positivity, Linear Algebra
   Appl. 436, 537-560 (2012):
   https://arxiv.org/abs/1301.3731

6. C. Wu, I. Kanevskiy, and M. Margaliot, k-contraction: theory and applications,
   Automatica 136, 110048 (2022):
   https://arxiv.org/abs/2008.10321

7. F. Forni and R. Sepulchre, Differential dissipativity theory for dominance
   analysis, IEEE Trans. Autom. Control 64, 2340-2351 (2019):
   https://arxiv.org/abs/1710.01721

These are the closest ingredients for the Perron-compound direction. None of the
searched sources combines proper-cone Perron orientation with an absolute
second-compound bound for fermion determinant positivity.

## 4. Defensible novelty statements

For the polyhedral family:

> We give an explicit open sign-free generator-support family certified by a
> non-Hilbert common norm.  Within one fixed, same-dimensional one-particle/CAR
> representation, we prove that it cannot be mapped by a fixed complex similarity
> into an ordinary Hermitian contraction or expansion cone, a split equality
> class, or Wei's fixed complex-CAR semigroups; the discrete-support statement
> persists for sufficiently small time steps.

The elementary common-norm determinant lemma and polyhedral Lyapunov theory are
not new mathematics.  The candidate contribution is their explicit use as a QMC
guiding principle, the open family separating it from the cited fixed-metric
classes, and the interacting realization using exactly the certified vertices.

For the finite-density direction:

> We introduce a Perron-compound positivity criterion: common proper-cone
> preservation fixes the orientation of the only allowed expanding mode, while a
> common second-compound contraction prevents any second unstable mode.

Do not claim a new Lie group, a new theory of polyhedral Lyapunov functions, or a
Hamiltonian intrinsically beyond every HS, fermion-bag, Jordan-Wigner, stoquastic,
or other representation.

## 5. Publication assessment

The current package has potential as the basis of a mathematical-physics or
QMC-method note, but it is not publication-ready. The potentially publishable core
would combine:

- an open arbitrary-depth determinant theorem;
- exact separation from common ellipsoids and a support-level argument against one
  fixed complex-CAR Wei structure;
- an engineered interacting Hermitian two-twirl realization;
- a distinct Perron-compound theorem and exact no-go statements mapping its limits.

Before an external preprint claim, the package still needs a dedicated A/B harness,
independent expert checking of the fixed-CAR proof, a more systematic priority
audit, and a sharper physical target. A condensed-matter venue would additionally
need a scalable intercell-hopping construction, a nontrivial phase or critical
point, and an algorithmic benchmark.
