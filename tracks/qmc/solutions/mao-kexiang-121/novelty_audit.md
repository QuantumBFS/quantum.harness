# Targeted novelty and priority audit for the polyhedral and Perron-compound criteria

Date: 2026-07-29

Status: targeted primary-source search, not a proof of priority. No claim below is
based merely on the absence of a search hit.

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
> non-Hilbert common norm and prove that, at generator level and for sufficiently
> small discrete time steps, it is not embeddable in Wei's fixed-metric complex-CAR
> semigroups.

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
