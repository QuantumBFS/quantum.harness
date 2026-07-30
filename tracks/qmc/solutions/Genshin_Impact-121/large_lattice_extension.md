# Large-lattice extension of the local three-mode A/B vertices

Date: 2026-07-30

Status: analytic theorem extension. No new numerical calculation is used here.
The finite-size verification record remains in `verification_record.md`. The
purpose of this note is to make the arbitrary-system-size statement precise and
to separate local three-site support from total system size.

## 1. A 3-by-3 generator is a local vertex, not a three-site universe

The matrices A and B act on the one-particle space of one local triple. They are
not the one-particle Hamiltonian of the complete lattice. On a lattice with L
spinless-fermion modes, a resolved vertex is an L-by-L matrix equal to the
identity outside one triple, a word T is L-by-L, and the many-body Hilbert space
has dimension 2^L.

Repeating the same local term over all translated triples gives O(L) terms in one
dimension and O(L^2) terms in two dimensions. Neighboring terms overlap and, for
the explicit equal-coupling choice below, do not commute. Products of their local
propagators can transport a fermion across the complete connected lattice. Thus
"three-mode vertex" describes locality in exactly the same sense that a two-site
bond term describes a macroscopic spin chain.

The resulting Hamiltonian does contain a genuine three-site density interaction,
as well as hopping, density interactions, and correlated pair hopping. That is a
feature of the local operator, not a restriction to three particles or three
lattice sites.

## 2. Local alphabet and embeddings

For epsilon>0 and kappa>0 define

    A = [ -1-epsilon-kappa     1          -epsilon ]
        [       0          -1-kappa          1     ]
        [       2              0          -2-kappa ],

    S=diag(1,1,-1),     B=SAS.

The determinant-positive lattice construction below needs only epsilon>0 and
kappa>0. To retain the exact separation from every common quadratic metric and
from the fixed same-dimensional complex-CAR Wei classes proved in
`main_theorem.md`, restrict further to

    40 epsilon + 59 kappa < 2.                              (R)

Let Lambda be a finite set of sites and let D be a collection of three-element
subsets Delta of Lambda. An ordering of Delta defines the coordinate isometry

    E_Delta : R^3 -> R^|Lambda|.

The complete S3 average below makes the final local operator independent of this
temporary ordering. For X in {A,B}, sigma in S3, and a fixed vertex strength s>0,
define

    Y_(Delta,X,sigma)
      =E_Delta P_sigma X P_sigma^T E_Delta^T,

    U_(Delta,X,sigma)
      =exp[s Y_(Delta,X,sigma)]
      =I+E_Delta[exp(s P_sigma X P_sigma^T)-I_3]E_Delta^T.   (1)

The Fock-space lift is

    V_(Delta,X,sigma)=Gamma(U_(Delta,X,sigma))
      =exp[s sum_(i,j in Delta)
                c_i^dagger(P_sigma X P_sigma^T)_(ij)c_j].    (2)

A single V vertex need not be Hermitian. Hermiticity belongs to the complete
six-element twirl

    M_(Delta,X)=(1/6) sum_(sigma in S3)V_(Delta,X,sigma).    (3)

No assumption that different triples are disjoint is made.

## 3. Arbitrary bounded-degree three-uniform hypergraph theorem

### Theorem 1: arbitrary-size and arbitrary-depth determinant positivity

Let (Lambda,D) be any finite three-uniform hypergraph. Allow every factor in a
word to choose an arbitrary triple, A or B, a permutation, and a nonnegative
strength s_j. Then every finite word

    T=U_(Delta_m,X_m,sigma_m)(s_m) ...
      U_(Delta_1,X_1,sigma_1)(s_1)                           (4)

is real and obeys

    ||T||_infinity <= 1,
    det(I+T) >= 0.                                           (5)

This holds for every |Lambda|, every overlap pattern, every ordering, and every
word depth m. Bounded hypergraph degree is not needed for the finite-volume sign
statement; it is needed only for a uniform thermodynamic limit.

#### Proof

Every matrix in either S3 orbit has logarithmic infinity norm

    mu_infinity(P_sigma X P_sigma^T)=-kappa.

After embedding, rows outside Delta have logarithmic rate zero, so

    mu_infinity(Y_(Delta,X,sigma))=0,
    ||exp(sY_(Delta,X,sigma))||_infinity<=1.                 (6)

Submultiplicativity gives (5) for an arbitrary product, even when consecutive
factors overlap and fail to commute.

Every eigenvalue lambda of the real matrix T lies in the closed unit disk. Real
eigenvalues contribute 1+lambda>=0. Nonreal eigenvalues occur in conjugate pairs
and contribute

    (1+lambda)(1+lambda_bar)=|1+lambda|^2>=0.

Multiplying all contributions proves det(I+T)>=0. A zero is allowed in this
variable-strength theorem when T has an eigenvalue -1. No large-depth
extrapolation or finite-size assumption enters the proof.

### Corollary 1: strict fixed-strength support bound

For the fixed alphabet (1), put q=exp(-kappa s)<1. Given a nonempty word, let U
be the union of its touched sites. For each i in U, choose the last
(leftmost-applied) factor that contains i. Immediately after that factor acts,
the absolute row sum of row i is at most q, because its three local rows have
infinity norm at most q and the preceding partial product has infinity norm at
most one. Later factors do not touch i, so that row is unchanged. Sites outside
U remain exact identity rows and columns. Consequently

    T=I_(Lambda\U) direct-sum T_U,
    ||T_U||_infinity<=q<1,                                    (6a)

and therefore

    det(I+T)=2^(|Lambda|-|U|) det(I_U+T_U)>0,
    ||(I_U+T_U)^(-1)||_infinity<=1/(1-q).                     (6b)

Thus the fixed-s CT alphabet used below has no exact zero-weight configuration.
A computed zero is a numerical-stability or implementation failure, not a
separate component of the sampling support.

## 4. Hermitian, positive-semidefinite interacting Hamiltonian

For nonnegative couplings g_(Delta,X), define

    H_Lambda
      =sum_(Delta in D) sum_(X=A,B)
         g_(Delta,X)[I-M_(Delta,X)].                         (7)

### Theorem 2: operator properties

The Hamiltonian (7) is finite-range on every bounded-diameter hypergraph,
Hermitian, number conserving, and positive semidefinite.

#### Hermiticity

On the local three-mode Fock space, the S3 representations in particle-number
sectors N_Delta=0,1,2,3 are

    trivial,
    trivial direct-sum standard,
    sign direct-sum standard,
    sign.

All irreducible summands are real and occur with multiplicity one. Equation (3)
commutes with S3, so Schur's lemma makes it a real scalar on every irreducible
block. Therefore M_(Delta,X) is Hermitian in the standard Fock inner product.

#### Positivity and a local particle penalty

Put

    q=exp(-kappa s)<1.

On the local N_Delta=n>=1 sector, a projective exterior norm gives

    ||wedge^n exp(sP_sigma X P_sigma^T)|| <= q^n.

Permutation matrices are isometries for the same norm. Their average therefore
has spectral radius at most q^n. Since M_(Delta,X) is Hermitian, all its
N_Delta=n eigenvalues are real and have absolute value at most q^n. The vacuum
eigenvalue is exactly one. Hence

    I-M_(Delta,X)
      >=(1-q) Pi_(N_Delta>=1),                               (8)

where Pi_(N_Delta>=1) projects onto states with at least one fermion on Delta.
This proves both positive semidefiniteness and a strict local particle penalty.

### Genuine interaction

Every Hermitian number-conserving S3 scalar on three spinless modes has the unique
form

    h_Delta
      =C + e N_Delta + t K_Delta + V Q_(2,Delta)
       +J P_(s,Delta)^dagger P_(s,Delta)
       +W product_(i in Delta)n_i,                            (9)

where

    N_Delta=sum_(i in Delta)n_i,
    K_Delta=sum_(i!=j in Delta)c_i^dagger c_j,
    Q_(2,Delta)=sum_(i<j in Delta)n_i n_j,

and, after labeling the triple as 1,2,3,

    P_s^dagger
      =(c_1^dagger c_2^dagger-c_1^dagger c_3^dagger
        +c_2^dagger c_3^dagger)/sqrt(3).

At epsilon=1/100 and kappa=1/1000, the exact small-s interaction certificates of
the two twirls are

    I_A=15062013/3000000,
    I_B=3056033/3000000.                                    (10)

Both are positive. Since the functional defining I_X vanishes on every constant
plus one-body operator, the corresponding value for the local term

    h_Delta=sum_X g_X(I-M_X)

is

    -[g_A I_A+g_B I_B]s^2+O(s^3),

which is nonzero for every nontrivial nonnegative choice of g_A,g_B and all
sufficiently small positive s. Thus the lattice Hamiltonian is genuinely
interacting, not a disguised quadratic model.

There is also an exact three-density statement. For h_Delta, the coefficient W is

    W=(g_A+g_B)det[I-exp(sA)]>0,                              (11)

because A and B are similar and exp(sA) is a strict real contraction. Adding the
identity shift in (7) changes only C and does not change W.

## 5. Exact continuous-time determinant expansion

Introduce a resolved label

    a=(Delta,X,sigma),
    lambda_a=g_(Delta,X)/6,

and write

    G_0=sum_(Delta,X)g_(Delta,X),
    V=sum_a lambda_a V_a,
    H_Lambda=G_0 I-V.                                       (12)

The grand-canonical partition function at chemical potential zero is

    Z_Lambda(beta)=Tr exp(-beta H_Lambda)

      =exp(-beta G_0)
       sum_(m=0)^infinity
       integral_(0<tau_1<...<tau_m<beta)
       d tau_1 ... d tau_m
       sum_(a_1,...,a_m)
       product_(j=1)^m lambda_(a_j)
       det[I+U_(a_m)...U_(a_1)]                              (13)

      =exp(-beta G_0)
       sum_(m=0)^infinity beta^m/m!
       sum_(a_1,...,a_m)
       product_(j=1)^m lambda_(a_j)
       det[I+U_(a_m)...U_(a_1)].

The Fock trace identity

    Tr_Fock Gamma(T)=det(I+T)

has the same factor order as (13). Theorem 1 makes every configuration weight
nonnegative for arbitrary m and |Lambda|. A resolved V_a may be non-Hermitian;
this causes no problem because the complete sum V and H_Lambda are Hermitian and
the resolved Fock trace is real and nonnegative.

The expansion is absolutely convergent. Indeed, every eigenvalue of T has modulus
at most one, so

    0<=det(I+T)<=2^|Lambda|.

Summing the scalar activities at each order bounds (13) by 2^|Lambda|. The
normalized configuration measure is therefore

    P(C)
      =exp(-beta G_0) beta^m/m!
       product_j lambda_(a_j) det(I+T_C)/Z_Lambda(beta).      (14)

A Poisson proposal may draw m with mean beta G_0 and each label with probability
lambda_a/G_0. Determinant reweighting changes the accepted order distribution,
so beta G_0 is a proposal scale rather than an exact statement about the sampled
mean order.

## 6. Translation-invariant one-dimensional chain

Let Lambda_L=Z/LZ with L>=4 and periodic boundary conditions. Take every
consecutive triple

    Delta_x={x,x+1,x+2},     x in Z/LZ,

with site-independent couplings g_A,g_B>=0. Then

    H_L^(1D)=sum_(x=0)^(L-1)
             sum_(X=A,B)g_X[I-M_(Delta_x,X)]                 (15)

is translation invariant, range two, and sign free at arbitrary L and CT order.

### Explicit noncommutativity of overlaps

Define the one-particle first-order twirls

    X_bar=(1/6)sum_(sigma in S3)P_sigma X P_sigma^T.

Every off-diagonal entry of X_bar is the average of the six off-diagonal entries
of X. Thus

    b_A=(4-epsilon)/6,
    b_B=(epsilon-2)/6,

and the combined off-diagonal coefficient is

    b_eff=[g_A(4-epsilon)+g_B(epsilon-2)]/6.                 (16)

The translated local term has the analytic expansion

    h_x(s)
      =sum_X g_X[I-M_(Delta_x,X)]
      =-s dGamma(g_A A_bar+g_B B_bar)_(Delta_x)+O(s^2).

For neighboring triples, the one-particle commutator has the private-endpoint
matrix element

    [Z_x,Z_(x+1)]_(x,x+3)=2 b_eff^2,                         (17)

because there are two length-two paths through the shared sites x+1 and x+2 in
one order and no path in the reverse order. Therefore

    [h_x(s),h_(x+1)(s)] != 0

for all sufficiently small positive s whenever b_eff!=0. The symmetric choice

    g_A=g_B=g>0

is especially clean: b_eff=g/3 exactly. It uses all twelve resolved orbit
vertices with positive activities, is translation invariant, interacting by
(10)-(11), and is explicitly not a sum of commuting or decoupled cells.

## 7. Explicit periodic triangular-lattice construction

Let

    Lambda_L={n_1 e_1+n_2 e_2 : n_1,n_2 in Z/LZ}

be a periodic triangular lattice with L>=3. For every r include the two elementary
triangles

    Delta_r^+={r,r+e_1,r+e_2},

    Delta_r^-={r+e_1+e_2,r+e_1,r+e_2}.                      (18)

Use the same positive g_A,g_B and the same s on every triangle and orientation:

    H_L^(tri)
      =sum_(r in Lambda_L) sum_(eta=+,-) sum_(X=A,B)
         g_X[I-M_(Delta_r^eta,X)].                           (19)

Equation (19) has 2L^2 local triples and

    G_0=2L^2(g_A+g_B).

It is translation invariant. Because the complete local twirl is insensitive to
the ordering of a triangle, equal couplings on the two orientations also restore
the triangular-lattice point-group action.

Every site belongs to six elementary triangles. Adjacent up and down triangles
share an edge but have distinct third vertices. Replacing x and x+3 in (17) by
those two private vertices gives the same leading commutator matrix element

    2 b_eff^2.

Consequently the equal-coupling model is a connected, noncommuting,
translation-invariant two-dimensional interacting system. The determinant proof
continues to use only the common coordinate infinity norm and is unchanged by
the number or pattern of overlapping triangles.

## 8. A square-lattice three-cluster construction

For completeness, let Lambda_L be a periodic square lattice and let

    Q_r={r,r+e_x,r+e_y,r+e_x+e_y}

be a plaquette. Include all four triples Q_r minus {v}, one for every v in Q_r,
with equal couplings. The resulting Hamiltonian

    H_L^(sq)
      =sum_r sum_(v in Q_r) sum_(X=A,B)
         g_X[I-M_(Q_r minus {v},X)]                          (20)

is translation invariant, C4v invariant, and supported within one plaquette.
Neighboring L-shaped triples overlap and are noncommuting for b_eff!=0 by the
same shared-path argument. This is a square-lattice realization; it does not
require calling an L-shaped cluster an elementary triangle.

## 9. Thermodynamic limit

Consider Z^d with a finite list of three-site shapes and all their translates.
Assume the number of active triples containing any site is bounded uniformly by
d_D. Let

    g_max=max_(Delta) sum_X g_(Delta,X).

From Hermiticity and the spectral bound above,

    ||I-M_(Delta,X)||<=2,
    ||h_Delta||<=2 sum_X g_(Delta,X).                        (21)

Thus the interaction is uniformly bounded and finite range. Moreover

    0<=H_Lambda<=C|Lambda|,
    1<=Z_Lambda(beta)<=2^|Lambda|.                           (22)

For van Hove boxes Lambda, define

    p_Lambda(beta)=|Lambda|^(-1) log Z_Lambda(beta),
    f_Lambda(beta)=-p_Lambda(beta)/beta.

If two boxes are separated by cutting the interactions that cross their common
boundary, the removed operator B has

    ||B||<=C_boundary |partial Lambda|.

For self-adjoint H and B, the Gibbs variational principle gives

    |log Tr exp[-beta(H+B)]-log Tr exp(-beta H)|
      <=beta ||B||.                                         (23)

Tiling a large box by fixed smaller boxes and applying (23) makes the pressure
nearly additive, with an error proportional to boundary area. Taking first the
large-box limit and then the tile-size limit proves

    p(beta)=lim_(Lambda approaches Z^d)p_Lambda(beta)        (24)

for every finite beta, and hence the free-energy density f(beta) exists. The same
proof covers the periodic one-dimensional, triangular, and square constructions.

Finite-volume Gibbs states have subsequential infinite-volume limits for local
observables. At a point where p is differentiable with respect to a coupling,
the corresponding local energy-density expectation is fixed by that derivative.
In two dimensions, phase coexistence may make an individual local-observable
limit boundary-condition dependent; existence of pressure must not be
misreported as uniqueness of every Gibbs state.

## 10. Estimators on the positive measure

For a nonzero-weight configuration C, put

    T_C=U_(a_m)...U_(a_1),
    R_C=T_C(I+T_C)^(-1).                                    (25)

The standard Gaussian trace identities give

    <c_i^dagger c_j>_C=(R_C)_(j,i),

    <c_i c_j^dagger>_C=[(I+T_C)^(-1)]_(i,j),

    <N>_C=tr R_C.                                           (26)

For i!=j, equal-time density correlations follow from Wick's theorem:

    <n_i n_j>_C
      =(R_C)_(i,i)(R_C)_(j,j)
       -(R_C)_(i,j)(R_C)_(j,i).                             (27)

Time-displaced Green functions are obtained by splitting the ordered word at the
insertion time and propagating (25) with the left and right segments. Higher
number-conserving observables use the corresponding Wick minors. The estimator
need not be positive configuration by configuration; the absence of the sign
problem is the positivity of (14).

Differentiating (13) with respect to beta gives the particularly simple energy
estimator

    <H_Lambda>=G_0-<m>/beta.                                (28)

Derivatives with respect to g_X give the expectation of
sum_Delta[I-M_(Delta,X)]. Number fluctuations give compressibility whenever a
sign-free chemical-potential deformation is available.

Corollary 1 excludes det(I+T_C)=0 for the fixed-s measure (14). A computed zero
must therefore stop the run as a numerical-stability or implementation failure.
For the more general variable-strength boundary covered only by Theorem 1,
zero-weight words can occur; unnormalized one- and two-body numerators can then
be defined with adjugates or minors rather than division by a singular matrix.

At fixed beta, G_0 is proportional to volume for all translation-invariant
examples. Hence the natural CT expansion scale is extensive, O(beta|Lambda|).
The determinant is |Lambda|-dimensional. Local determinant-ratio and Green-matrix
updates can make insertions polynomial in |Lambda|, but positivity alone does not
prove rapid Markov-chain mixing or a favorable autocorrelation time. The direct
pilot prototype keeps primary scalar traces in memory and checkpoint JSON so
tau_int, ESS, and R-hat can be reconstructed; this costs O(number of
measurements) memory. A production run must replace it with durable chunked trace
storage without changing the estimator definitions.

## 11. Exact vacuum gap and the finite-density boundary

The large-lattice extension strengthens, rather than removes, the vacuum
limitation. Suppose every site belongs to at least r_min active triples and use
uniform g_A,g_B. Summing (8) gives

    H_Lambda
      >=(g_A+g_B)(1-q)
        sum_(Delta in D)Pi_(N_Delta>=1).                     (29)

On every local occupation basis state,

    N_Delta<=3 Pi_(N_Delta>=1).

Also

    sum_Delta N_Delta
      =sum_i r_i n_i
      >=r_min N.

Therefore the operator inequality

    H_Lambda>=Delta_vac N,

    Delta_vac
      =(g_A+g_B)(1-exp(-kappa s)) r_min/3                   (30)

holds. The covered periodic lattice has a unique vacuum ground state and a strict
particle-number gap. For the constructions above,

    one-dimensional consecutive triples: r_min=3,
    triangular elementary triangles:     r_min=6,
    square plaquette triples:             r_min=12.

These are rigorous lower bounds, not measured excitation gaps.

### Chemical potential

Because H_Lambda conserves N,

    Z(beta,mu)
      =Tr exp[-beta(H_Lambda-mu N)]

has the same CT expansion with

    det(I+zT_C),     z=exp(beta mu).                         (31)

For the fixed-strength alphabet, Corollary 1 gives

    det(I+zT_C)
      =(1+z)^(|Lambda|-|U|) det(I_U+zT_U)>0

whenever zq<1. Since q=exp(-kappa s) and z=exp(beta mu), this is the finite-
temperature sign-free window

    mu<kappa s/beta.                                          (31a)

It includes every mu<=0 and a small interval of positive chemical potential. At
the boundary mu=kappa s/beta, the norm argument guarantees only a nonnegative
determinant; it does not exclude an exact zero. Negative chemical potential
continues to reinforce the vacuum.

For mu>0 outside (31a), the thermodynamic pressure still exists because the
on-site Hilbert space is finite and -mu N is a bounded local term, but
configuration-wise positivity no longer follows from the support bound. For a
fixed real word T, positivity for every z>0 requires every distinct negative real
eigenvalue of T to have even algebraic multiplicity. The present theorem does not
enforce that condition.

Equation (30) separately implies that the vacuum remains the ground state for
0<mu<Delta_vac. Where this interval overlaps (31a), the CT representation is
sign free but its ground state is still the vacuum. The determinant certificate
for positive mu shrinks as beta tends to infinity and therefore proves no
finite-density ground-state regime.

At fixed particle number, the fugacity coefficients are

    det(I+zT)=sum_n z^n Tr(wedge^n T).                       (32)

Nonnegativity of the polynomial at z=1 does not imply nonnegativity of every
coefficient. The present construction therefore does not prove a sign-free
canonical finite-density algorithm, an itinerant finite-density phase, or a
positive-mu ground-state simulation.

At any finite beta and mu=0, thermally excited number sectors still contribute,
so (19) and (20) define nontrivial interacting finite-temperature lattice
thermodynamics. The honest missing result is a non-vacuum sign-free regime, not a
large-system extension.

## 12. Precise response to the "three-body system" objection

The following statements should not be conflated.

1. **Local matrix size.** A and B are 3-by-3 because one update acts on three
   one-particle orbitals.
2. **Local interaction order.** The complete twirl generates hopping, density
   interactions, correlated pair hopping, and a three-density term on that
   cluster.
3. **Total system size.** Equations (15), (19), and (20) act on arbitrarily many
   sites, with Fock dimension 2^|Lambda| and noncommuting overlapping terms.
4. **Physical limitation.** The proved contraction route has a vacuum ground
   state and does not yet yield a sign-free positive-density phase.

Only item 4 is a substantive limitation of the current physics. Calling the model
a "three-site system" because its elementary vertex is local would equally turn a
nearest-neighbor spin chain into a "two-spin system." The correct description is
an extensive lattice Hamiltonian built from finite-range three-site interactions.

## 13. Theorem package and claim boundary

The large-lattice result can be presented as the following theorem sequence.

1. **Finite-hypergraph word theorem:** arbitrary-size, arbitrary-depth
   determinant nonnegativity for every overlapping three-site word.
2. **Operator theorem:** complete S3 twirls give local Hermitian positive
   semidefinite interacting terms.
3. **Continuous-time theorem:** the exact determinant expansion defines a
   nonnegative grand-canonical configuration measure.
4. **Noncommutativity proposition:** equal A/B couplings on consecutive triples
   give an explicit nonzero adjacent-term commutator.
5. **Lattice corollaries:** periodic one-dimensional, triangular, and square
   constructions are translation invariant and finite range.
6. **Thermodynamic theorem:** pressure and free-energy density exist along
   van Hove sequences.
7. **Vacuum-bound proposition:** a quantitative particle-number gap holds; at
   finite beta the fixed-s determinant measure is strictly positive for
   mu<kappa s/beta (nonnegative at equality), while the certified positive-mu
   window vanishes as beta tends to infinity and fixed-density positivity remains
   open.

This extension uses no extra flavor, determinant square, disjoint-cell
factorization, or Jordan-Wigner reduction. It proves that the local A/B support
scales to macroscopic connected lattices without a sign problem in its exact
mu=0 continuous-time expansion. It does not establish publication priority,
rapid Monte Carlo mixing, a standard Hubbard auxiliary-field representation, or
a nontrivial finite-density ground-state phase.
