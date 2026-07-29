# Interacting lattice CT Gaussian-vertex realization of the S3 twirl

Date: 2026-07-29

Status: analytic theorem and implementation specification. No new numerical
computation is used. The construction below is a complete, finite-temperature,
interacting lattice realization of the determinant-positive support in issue #121.
Finite-density ground-state physics is not a requirement of that issue and is not
claimed here.

## 1. Reviewable lattice theorem

Fix parameters

    ε>0,   κ>0,   40ε+59κ<2,   s>0,

and define

    A = [ -1-ε-κ     1       -ε ]
        [    0      -1-κ      1 ]
        [    2        0      -2-κ],

    S=diag(1,1,-1),   B=SAS.

Here s is the fixed strength of a Gaussian vertex. It is not an imaginary-time
coordinate. Let Λ be any finite lattice with one spinless fermion mode per site,
and let D be any collection of ordered triples Δ=(r₁,r₂,r₃) of distinct sites.
The triples may overlap. Write E_Δ:R³→R^|Λ| for the coordinate embedding and P_σ
for the 3-by-3 permutation matrix of σ∈S3. For X∈{A,B}, define

    Y_(Δ,X,σ)=E_Δ P_σ X P_σ^T E_Δ^T,

    U_(Δ,X,σ)=exp(sY_(Δ,X,σ))
             =I+E_Δ[exp(sP_σXP_σ^T)-I₃]E_Δ^T,

    V_(Δ,X,σ)=exp[s sum_(p,q∈Δ) c_p^dagger
                          (P_σXP_σ^T)_(pq)c_q]
             =Γ(U_(Δ,X,σ)).

The resolved V vertices need not be Hermitian. Their complete local twirls are

    M_(Δ,X)=(1/6) sum_(σ∈S3) V_(Δ,X,σ).

For arbitrary couplings g_(Δ,X)≥0, set

    G₀=sum_(Δ,X) g_(Δ,X),

    H_bar=sum_(Δ,X) g_(Δ,X)[I-M_(Δ,X)].                  (1)

Equivalently H_bar=G₀I+H with H=−sum gM. Then:

1. H_bar is a finite-range, Hermitian, number-conserving interacting Hamiltonian.
2. Its grand-canonical partition function at μ=0 has an exact continuous-time
   Gaussian-vertex expansion with nonnegative scalar activities.
3. Every resolved configuration has a nonnegative determinant weight, for every
   β≥0, every finite lattice, every overlap pattern, and every expansion order.
4. The construction uses one spinless flavor. No identical-flavor square,
   Kramers partner, or conjugate determinant is introduced.

If D is the set of elementary triangles of a triangular lattice, the local terms
overlap and their quadratic and correlated-hopping pieces move particles through
the connected lattice. Thus this is not a collection of decoupled cells. Its
zero-temperature filling limitation is stated exactly in Section 10.

### Proof of locality, Hermiticity, and interaction

Every V_(Δ,X,σ) acts only on the three modes in Δ, so (1) is local. Section 5
proves that the complete six-term twirl M_(Δ,X) is Hermitian. Every vertex commutes
with the total number N, so H_bar conserves N.

The normal-ordered identity

    Γ(U)=:exp[c^dagger(U-I)c]:

shows explicitly that a three-mode Gaussian vertex contains terms through sixth
order in fermion operators. After twirling, Section 6 gives the complete local
operator basis. In particular, the coefficient of n₁n₂n₃ in M_X is exactly

    W_(M_X)=−det[I₃-exp(sX)].

Since ||exp(sX)||_infinity≤exp(−κs)<1, this determinant is positive. Therefore
the coefficient of n₁n₂n₃ in −gM_X is strictly positive for every g>0. The
Hamiltonian is genuinely interacting, not merely a quadratic Hamiltonian written
in unusual notation. At generic couplings it also contains ordinary hopping,
density interactions, and correlated pair hopping. A special positive mixture can
cancel one quartic coefficient, but cannot cancel the three-body repulsion; see
Sections 7-8.

### Proof of the configuration-wise determinant sign

For every X in either S3 orbit of A or B,

    μ_infinity(X)
      =max_i [X_ii+sum_(j≠i)|X_ij|]
      =−κ.

Signed permutations are isometries of the infinity norm. Hence the local block of
each resolved vertex satisfies

    ||exp(sP_σXP_σ^T)||_infinity≤q,   q=exp(−κs)<1.

The embedded U has spectator identity blocks, so

    ||U_(Δ,X,σ)||_infinity≤1.

For any ordered resolved word

    T_C=U_(Δ_m,X_m,σ_m) ... U_(Δ_1,X_1,σ_1),             (2)

submultiplicativity gives ||T_C||_infinity≤1. Every real eigenvalue λ of the real
matrix T_C therefore obeys −1≤λ≤1, while nonreal eigenvalues occur in conjugate
pairs. Consequently

    det(I+T_C)
      =product_(λ real)(1+λ)
       product_(Im λ>0)|1+λ|²
      ≥0.                                                   (3)

On an isolated three-mode cluster the bound is strict and (3) is positive. On an
embedded lattice a zero is allowed because untouched spectator directions make
the global norm non-strict. Nonnegativity is the sign-free condition required by
issue #121.

## 2. Exact continuous-time expansion and activities

Let a resolved label be

    a=(Δ,X,σ),   λ_a=g_(Δ,X)/6,   B_a=U_(Δ,X,σ).

The nonnegative number λ_a is the activity of that resolved vertex. Expanding the
interaction exponential for (1), and using the ordered simplex
0<t₁<...<t_m<β, gives

    Z=Tr exp(−βH_bar)

     =exp(−βG₀) sum_(m=0)^infinity sum_(a₁,...,a_m)
        integral_(0<t₁<...<t_m<β) [product_(j=1)^m λ_(a_j)dt_j]
        det[I+T_C].                                           (4)

For m=0, T_C=I and the determinant is 2^|Λ|. Equation (4) follows from the exact
second-quantization identities

    Γ(U_m)...Γ(U_1)=Γ(U_m...U_1),
    Tr_F Γ(T)=det(I+T).

There is no Hubbard-Stratonovich approximation and no Trotter error. The times t_j
only order noncommuting vertices; the fixed matrix amplitude is s. Because there
is no separate free propagator in (1), the time integrals may also be performed
analytically:

    Z=exp(−βG₀) sum_(m=0)^infinity β^m/m!
       sum_(a₁,...,a_m) [product_j λ_(a_j)] det[I+B_(a_m)...B_(a_1)].

This discrete-word form and the ordered-time form sample the same series.

Equation (3), together with λ_a≥0 and exp(−βG₀)>0, proves that every integrand in
(4) is nonnegative. This is an exact continuous-time Gaussian-vertex QMC
representation of a non-Gaussian interacting Hamiltonian. It is not the standard
auxiliary-field DQMC decomposition of a quartic Hubbard interaction.

## 3. Directly implementable sampler

A minimal Metropolis sampler stores an ordered list

    C=[(t₁,a₁),...,(t_m,a_m)]

and its determinant D(C)=det[I+T_C]. Choose any normalized proposal distribution
q_prop(a)>0 on resolved labels and nonzero probabilities p_ins,p_del. One sweep can
be written as follows.

```text
C ← empty list; D ← 2^|Λ|
repeat:
    choose INSERT or DELETE with probabilities p_ins and p_del

    if INSERT:
        draw a from q_prop(a), draw t uniformly in [0,β)
        C_new ← C with (t,a) inserted in time order
        D_new ← stable_det(I + ordered_product(C_new))
        R ← [β λ_a/(m+1)] [p_del/(p_ins q_prop(a))] [D_new/D]
        accept C_new with probability min(1,R)

    if DELETE and m>0:
        choose one of the m vertices uniformly; call its label a
        C_new ← C with that vertex removed
        D_new ← stable_det(I + ordered_product(C_new))
        R ← [m/(β λ_a)] [p_ins q_prop(a)/p_del] [D_new/D]
        accept C_new with probability min(1,R)

    after equilibration, measure Gaussian estimators at a chosen cyclic cut
```

The insertion and deletion ratios are exact detailed-balance ratios for the
ordered-simplex measure in (4). Insert/delete moves alone connect all finite words;
time shifts and label swaps may be added to improve mixing. A determinant that is
negative beyond floating-point tolerance is an implementation failure, not a sign
to be sampled with reweighting.

At a cyclic cut with product T, define

    C_ij=[T(I+T)^(-1)]_ij=<c_j^dagger c_i>_C.

Configuration-wise Wick contractions then give all equal-time number-conserving
observables. The conditional matrix C need not itself look like a physical density
matrix because an individual resolved word is not Hermitian; only the weighted
average is a physical expectation value.

Let n=|Λ|, k=3, and m be the current expansion order. A transparent dense
implementation exploits B_a-I having rank at most k. Rebuilding one word costs
O(mkn²), and a stabilized determinant costs O(n³), with O(n²+m) storage. Thus a
fully naive sweep of O(m) proposals costs O(m²kn²+mn³). Given cached left/right
products and a stabilized inverse, the matrix-determinant lemma reduces the
algebraic ratio itself to O(kn²+k³). Maintaining those caches after accepted
arbitrary-time insertions and performing periodic QR or SVD stabilization adds an
implementation-dependent polynomial overhead; no fast-update benchmark is claimed
here. The relevant expansion scale is βG₀, although the interacting determinant
changes the actual mean order. Absence of a sign problem does not by itself
guarantee fast Markov-chain mixing.

For an insertion between T_C=LR, write B_a=I+E D_a E^T with E=E_Δ. The fast ratio
is the k-by-k determinant

    D(C_new)/D(C)
      =det_k[I_k+D_a E^T R(I+LR)^(-1)L E].

This identity supplies a direct unit test for an optimized implementation against
the full n-by-n determinant.

### Preregistered no-run smoke benchmark

The first implementation benchmark is fixed to the previously approved convention:

- four-site open chain with one spinless orbital per site;
- overlapping ordered triples Δ₁=(1,2,3) and Δ₂=(2,3,4), with no wraparound triple;
- ε=0.01, κ=0.001, and fixed vertex amplitude s=0.1 (called τ=0.1 in
  the run configuration);
- g_(Δ,A)=g_(Δ,B)=0.25 for both triples;
- μ=0 and β∈{0.25,0.5,1,2}.

This paragraph records inputs only. No chain was sampled and no benchmark number is
claimed in this analytic note. Before a future run, the random seed, warmup,
measurement count, stabilization interval, and error analysis must also be frozen.
For this 16-dimensional Fock space, a future implementation can compare Z, energy,
density, and selected correlators against exact diagonalization while also checking
that every accepted determinant sign is nonnegative.

## 4. Finite-temperature physical meaning and scope

The model (1) is a short-range spinless-fermion lattice Hamiltonian. On overlapping
triangles it has mobile excitations and genuine interactions. Equation (4) can be
used to measure its free energy, energy, density, compressibility, and equal- or
imaginary-time correlation functions at any finite β. At μ=0, thermally excited
particle sectors contribute even though the exact zero-temperature ground state is
the vacuum.

Adding −μN multiplies the one-body word by

    z=exp(βμ),

so the configuration determinant becomes det(I+zT_C). For μ≤0, z≤1 and the common
nonexpansion proof still gives nonnegative weights. For fixed μ>0 at arbitrarily
large β, the present z=1 theorem is insufficient; the exact obstruction is stated
in Section 10. Therefore this document does not claim a finite-density ground state
or a generic positive-μ algorithm.

The deliverable in issue #121 is a matrix/Lie-semigroup condition ensuring
determinant nonnegativity. It does not impose finite density as an acceptance
condition. The lattice theorem above supplies a concrete interacting physical
realization of that mathematical result; finite density is a separate extension,
not a criterion that should be retroactively used to reject the issue solution.

No doubled flavor is needed here. Conversely, doubling the model would trivially
replace every weight by a determinant square, but that is the established
Kramers/identical-flavor mechanism and carries no novelty for issue #121.

## 5. Why the complete S3 twirl is Hermitian

Let rho_N be the S3 action in the N-particle sector. Restricting the Fock twirl to
that sector gives

    M_X^(N)
      =(1/6) sum_(sigma in S3)
        rho_N(sigma) (wedge^N exp(sX)) rho_N(sigma)^(-1).

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

## 6. Complete local operator basis

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

## 7. A tunable familiar slice

Write the twirl eigenvalues as

    (1, alpha, beta, d_2, gamma, zeta),

with d_2 in the N=2 sign irrep and gamma in the N=2 standard irrep. Its correlated-
hopping coefficient is exactly

    J_M=(alpha-beta)+(d_2-gamma).

For the rational A and B=SAS family at small s,

    J_A =  (approximately 5.001995) s^2 + O(s^3),
    J_B = -(approximately 1.000995) s^2 + O(s^3).

A positive mixture can therefore tune J of the Hamiltonian

    h=-g_A M_A-g_B M_B

to zero near g_B/g_A=5. This gives a familiar hopping-density plus three-body slice.
The exact finite-s ratio can be obtained by continuity once a vertex amplitude is fixed.

## 8. Exact three-body no-go

For every twirled vertex,

    W_M = -det(I-exp(sX)).

If exp(sX) is a strict real contraction, det(I-exp(sX))>0. Similarity of A
and B implies that their determinants are identical. Hence every positive mixture
has

    W_h=(g_A+g_B) det(I-exp(sA)) > 0.

The three-body repulsion cannot be cancelled with positive safe coefficients. It
can vanish only on a boundary with an eigenvalue one, or by introducing negative
coefficients that invalidate the original positive-vertex expansion.

## 9. Reduction and stoquastic checks

For one triangle, a diagonal Fock-sign gauge can make h=-M stoquastic in the N=1
sector only when alpha-beta>=0, and in N=2 only when d_2-gamma>0. The A and B
orbits violate opposite conditions at small s. Their positive mixture has only a
narrow possible gauge-compatible window, different from the ratio that removes J.
Overlapping triangles introduce further global consistency conditions.

The standard spinless fermion-bag and Majorana-QMC constructions in

- https://arxiv.org/abs/1311.0034
- https://arxiv.org/abs/1408.2269

use bipartite, half-filled, or particle-hole structures and do not directly cover
this nonbipartite triangular support. This is not a proof that no alternative bag or
non-diagonal stoquastic representation exists.

## 10. Finite-density no-go inside the contraction route

For an isolated triangle, every one-particle orbit factor U_sigma obeys

    ||U_sigma||_infinity≤q=exp(−κs)<1.

The induced exterior norm therefore gives

    ||wedge^N U_sigma||<=q^N

in every N>=1 sector. Permutations are isometries for the same norm, so their
average M_X^(N) is also a contraction. The preceding Schur argument makes each
irreducible block a real scalar; hence every N>=1 eigenvalue lambda obeys
|lambda|<=q^N<=1. The vacuum block is exactly one. Since the complete twirl is
Hermitian, this proves I-M_X>=0 as an operator on Fock space.

For positive couplings,

    H_bar=sum_(Delta,X) g_(Delta,X)[I-M_(Delta,X)]≥0,
    H_bar|vac>=0.

If every orbital belongs to at least one active triple, the common zero eigenspace
is only the global vacuum. A Hermitian one-body background dGamma(K) that remains
safe under the same contraction certificate has K≥0 and only reinforces the
vacuum. A positive chemical potential −μN instead contributes z=exp(βμ)>1 to the
word and leaves this proof.

For a fixed real word T, the exact all-fugacity criterion is

    det(I+zT)≥0 for every z>0

if and only if every distinct negative real eigenvalue of T has even algebraic
multiplicity. Complex-conjugate pairs contribute |1+zλ|², positive real
eigenvalues never vanish for z>0, and a negative eigenvalue gives the positive
root z=−1/λ; the polynomial changes sign there exactly when that root has odd
multiplicity. Strict positivity for all z>0 requires no negative real eigenvalue.

For a real 3-by-3 word with detT>0, two distinct negative eigenvalues therefore
produce a negative interval between their two positive roots. They are harmless for
all z only if they are exactly degenerate, in which case the weight can vanish. The
current contraction theorem proves positivity at z=1 (and 0≤z≤1), but proves
neither negative-spectrum avoidance nor this degeneracy for every word. Positive-μ
sign freedom is consequently an open extension, not a result of the present model.

Grand-canonical positivity also does not imply positivity at fixed filling because

    det(I+zT)=sum_N z^N Tr(wedge^N T)

may be positive at z=1 while individual coefficients are negative. For example,
X=[[-1,-1],[1,-1]] at t=pi gives T=-exp(-pi)I: det(I+T)>0 but tr T<0.

Therefore the S3 contraction family defines an engineered Hermitian interacting
model with an exact, implementable, sign-free CT Gaussian-vertex sampler and a
rigorous vacuum ground state. It is not a standard Hubbard-Stratonovich DQMC
formulation and does not solve finite-density ground-state sampling. Canonical
finite density requires a separate coefficient-wise compound-trace certificate;
positive grand-canonical μ requires the all-fugacity criterion above. These are
extensions beyond the acceptance condition of issue #121.
