# Physical classification and no-go results for the S3 twirl

Date: 2026-07-29

Status: analytic companion note. No new numerical computation is used.

## Why the complete S3 twirl is Hermitian

Let rho_N be the S3 action in the N-particle sector. Restricting the Fock twirl to
that sector gives

    M_X^(N)
      =(1/6) sum_(sigma in S3)
        rho_N(sigma) (wedge^N exp(tau X)) rho_N(sigma)^(-1).

Therefore M_X^(N) commutes with rho_N(S3). For N=0,1,2,3 the representations are,
respectively,

    trivial,
    trivial direct-sum standard,
    sign direct-sum standard,
    sign.

Every summand is of real type and occurs with multiplicity one. By Schur's lemma,
the group average acts as a real scalar on each irreducible block. It is therefore
Hermitian in the standard Fock inner product. A single sampled Gaussian orbit
vertex need not be Hermitian; Hermiticity appears only after the complete six-term
twirl.

## 1. Complete local operator basis

For three spinless modes, the S3 representations in fixed number sectors are

    N=0: trivial,
    N=1: trivial + standard,
    N=2: sign + standard,
    N=3: sign.

A Hermitian, number-conserving S3 scalar therefore has six real sector eigenvalues

    e_0, e_u, e_s, e_2sign, e_2std, e_3.

Define

    N = sum_i n_i,
    K = sum_(i!=j) c_i^dagger c_j,
    Q_2 = sum_(i<j) n_i n_j,
    P_s^dagger=(c_1^dagger c_2^dagger-c_1^dagger c_3^dagger
                +c_2^dagger c_3^dagger)/sqrt(3).

Every such local operator is uniquely

    h = C + eps N + t K + V Q_2 + J P_s^dagger P_s + W n_1 n_2 n_3.

The inverse map from sector eigenvalues is

    C   = e_0,
    t   = (e_u-e_s)/3,
    eps = (e_u+2 e_s)/3-C,
    V   = e_2std-C-2 eps-t,
    J   = e_2sign-e_2std+e_u-e_s,
    W   = e_3-C-3 eps-3 V-J.

Thus the generic twirl is not an independent ring-exchange model. Its nonstandard
quartic structure is the correlated-hopping projector P_s^dagger P_s, together
with a possible three-body density term.

## 2. A tunable familiar slice

Write the twirl eigenvalues as

    (1, alpha, beta, d_2, gamma, zeta),

with d_2 in the N=2 sign irrep and gamma in the N=2 standard irrep. Its correlated-
hopping coefficient is exactly

    J_M=(alpha-beta)+(d_2-gamma).

For the rational A and B=SAS family at small tau,

    J_A =  (approximately 5.001995) tau^2 + O(tau^3),
    J_B = -(approximately 1.000995) tau^2 + O(tau^3).

A positive mixture can therefore tune J of the Hamiltonian

    h=-g_A M_A-g_B M_B

to zero near g_B/g_A=5. This gives a familiar hopping-density plus three-body slice.
The exact finite-tau ratio can be obtained by continuity once a time step is fixed.

## 3. Exact three-body no-go

For every twirled vertex,

    W_M = -det(I-exp(tau X)).

If exp(tau X) is a strict real contraction, det(I-exp(tau X))>0. Similarity of A
and B implies that their determinants are identical. Hence every positive mixture
has

    W_h=(g_A+g_B) det(I-exp(tau A)) > 0.

The three-body repulsion cannot be cancelled with positive safe coefficients. It
can vanish only on a boundary with an eigenvalue one, or by introducing negative
coefficients that invalidate the original positive-vertex expansion.

## 4. Reduction and stoquastic checks

For one triangle, a diagonal Fock-sign gauge can make h=-M stoquastic in the N=1
sector only when alpha-beta>=0, and in N=2 only when d_2-gamma>0. The A and B
orbits violate opposite conditions at small tau. Their positive mixture has only a
narrow possible gauge-compatible window, different from the ratio that removes J.
Overlapping triangles introduce further global consistency conditions.

The standard spinless fermion-bag and Majorana-QMC constructions in

- https://arxiv.org/abs/1311.0034
- https://arxiv.org/abs/1408.2269

use bipartite, half-filled, or particle-hole structures and do not directly cover
this nonbipartite triangular support. This is not a proof that no alternative bag or
non-diagonal stoquastic representation exists.

## 5. Finite-density no-go inside the contraction route

For an isolated triangle, every one-particle orbit factor U_sigma obeys

    ||U_sigma||_infinity<=q=exp(-kappa tau)<1.

The induced exterior norm therefore gives

    ||wedge^N U_sigma||<=q^N

in every N>=1 sector. Permutations are isometries for the same norm, so their
average M_X^(N) is also a contraction. The preceding Schur argument makes each
irreducible block a real scalar; hence every N>=1 eigenvalue lambda obeys
|lambda|<=q^N<=1. The vacuum block is exactly one. Since the complete twirl is
Hermitian, this proves I-M_X>=0 as an operator on Fock space.

For positive couplings,

    H_0-E_vac = sum_Delta,X g_X [I-M_(X,Delta)] >= 0.

Any deterministic one-body background dGamma(K) that remains safe under the same
contraction certificate has K>=0 and only reinforces the vacuum. A positive physical
chemical potential -mu N has one-particle propagation exp(+Delta tau mu), leaves the
contraction semigroup, and destroys this proof.

Grand-canonical positivity also does not imply positivity at fixed filling because

    det(I+zT)=sum_N z^N Tr(wedge^N T)

may be positive at z=1 while individual coefficients are negative. For example,
X=[[-1,-1],[1,-1]] at t=pi gives T=-exp(-pi)I: det(I+T)>0 but tr T<0.

Therefore the S3 contraction family defines an engineered Hermitian interacting model
with an exact sign-free grand-canonical determinant-valued series expansion and a
rigorous vacuum ground state. It is not a standard auxiliary-field DQMC formulation
or a solved finite-density algorithm. Canonical finite density requires a new
exterior-power cone or another pairing mechanism. This no-go motivates the separate
Perron-compound construction.
