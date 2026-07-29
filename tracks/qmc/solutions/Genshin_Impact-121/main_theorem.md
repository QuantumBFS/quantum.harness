# An open polyhedral determinant-positive family beyond the fixed Wei semigroups

Date: 2026-07-29

Status: analytic theorem draft under internal referee audit. The algebraic separation
from Wei 2024 is a vertex-support statement. Literature priority and exclusion of
alternative positive decompositions of the same many-body Hamiltonian are not
claimed.

## 1. Executive theorem

For epsilon>0 and kappa>0 define

    A = [ -1-epsilon-kappa     1          -epsilon ]
        [       0          -1-kappa          1     ]
        [       2              0          -2-kappa ]

    S = diag(1,1,-1),    B = S A S,

and let C(epsilon,kappa) be the union of the two S3 conjugacy orbits of A
and B. Throughout (R), the three diagonal entries of A (and of B) are pairwise
distinct. Any permutation stabilizing either matrix must therefore be the identity.
If the two orbits intersected, equality of their ordered diagonal entries would
again force the conjugating permutation to be the identity, but A!=B. Thus the
two orbits are disjoint and C(epsilon,kappa) contains exactly twelve matrices.

Throughout the open triangle

    epsilon>0,   kappa>0,   40 epsilon + 59 kappa < 2,             (R)

the following statements hold.

1. Every X in C has mu_infinity(X)=-kappa. Hence every positive-time word

       T = exp(t_m X_m) ... exp(t_1 X_1)

   is a real contraction in one common polyhedral norm and obeys
   det(I+T)>0 on the isolated three-mode space. Embedded local words obey
   det(I+T)>=0.
2. C has no common H>0 satisfying X^T H+H X<=0 for every X in C.
   Consequently no fixed complex similarity carries C into an ordinary
   nondegenerate Hermitian contraction cone, expansion cone, or split equality
   class in the same one-particle dimension.
3. C real-linearly spans all of M_3(R).
4. The number-conserving Nambu lifts of C cannot satisfy Eqs. (2)-(3) of
   Wei, Phys. Rev. B 110, 075146 (2024), after any one fixed complex
   orthogonal CAR basis transformation.
5. The two S3 Fock twirls are Hermitian. At epsilon=1/100,
   kappa=1/1000 they are interacting and non-Gaussian for all sufficiently
   small positive tau; this persists on an open parameter neighborhood.

The decimal-looking matrix is therefore one convenient rational interior point,
not an isolated or fitted solution.

## 2. Common polyhedral contraction

Each row of A has diagonal entry equal to minus its absolute off-diagonal row sum,
followed by the strict shift -kappa I. Therefore

    mu_infinity(A)
      = max_i [A_ii + sum_(j!=i) |A_ij|]
      = -kappa.

Permutation matrices and S are infinity-norm isometries, so the same equality holds
for all twelve generators. Submultiplicativity gives

    ||T||_infinity <= exp[-kappa sum_j t_j] < 1.

Every real eigenvalue of T lies in (-1,1), while nonreal eigenvalues occur in
conjugate pairs. Hence

    det(I+T)
      = product_(lambda real) (1+lambda)
        product_(Im lambda>0) |1+lambda|^2
      > 0.

The opposite-sign directed pair A_13 A_31=-2 epsilon<0 is invariant under a
diagonal site-sign gauge. Thus the family is not made Metzler by such a gauge.

## 3. Exact exclusion of every common ellipsoid

Assume that H>0 satisfies

    X^T H+H X<=0

for every X in C(epsilon,kappa). For each permutation matrix Pi define

    H_bar = (1/6) sum_(Pi in S3) Pi^T H Pi.

The family C(epsilon,kappa) is closed under permutation conjugation. Therefore,
for every X in C(epsilon,kappa),

    X^T H_bar+H_bar X
      = (1/6) sum_Pi Pi^T
          [(Pi X Pi^T)^T H+H(Pi X Pi^T)]
        Pi
      <= 0.

Moreover H_bar>0. Since H_bar commutes with the natural permutation
representation, there are real alpha,beta such that

    H_bar = alpha I + beta ee^T,
    e=(1,1,1)^T.

Its restriction to e^perp is alpha I, so positivity gives alpha>0. After division
by alpha we may consequently write

    H_r = I+r ee^T,    r=beta/alpha,    r>-1/3.

Set

    x=(1,1,3/5)^T,    y=Sx=(1,1,-3/5)^T.

The A inequality must hold on x, whereas the B=SAS inequality must hold on y.
Direct calculation gives

    x^T(A^T H_r+H_r A)x
      = (2/25) [
          2-40 epsilon-59 kappa
          +13 r(2-8 epsilon-13 kappa)
        ],

and

    y^T(B^T H_r+H_r B)y
      = (2/25) [
          2-40 epsilon-59 kappa
          -7 r(6+8 epsilon+7 kappa)
        ].

Condition (R) implies

    2-40 epsilon-59 kappa>0,
    2-8 epsilon-13 kappa>0,
    6+8 epsilon+7 kappa>0.

The first quadratic-form inequality therefore requires

    r <= -(2-40 epsilon-59 kappa)
          / [13(2-8 epsilon-13 kappa)] < 0,                       (A-bound)

whereas the second requires

    r >=  (2-40 epsilon-59 kappa)
          / [7(6+8 epsilon+7 kappa)] > 0.                         (B-bound)

The two necessary conditions are incompatible. Hence no common positive-definite
H exists. At epsilon=1/100 and kappa=1/1000 the two bounds are

    r <= -1541/24791,    r >= 1541/42609.

### Fixed-similarity consequence

The preceding result also excludes every ordinary nondegenerate Hermitian
contraction metric after an arbitrary fixed complex similarity. Suppose, to the
contrary, that one fixed L in GL_3(C) and one fixed nonsingular Hermitian eta obey

    Y_X^dagger eta+eta Y_X<=0,    Y_X=L X L^(-1),

for all X in C. Pull the metric back as

    G=L^dagger eta L.

Then G is nonsingular Hermitian and

    X^dagger G+G X<=0.

Fix any X in C, which is Hurwitz by Section 2, and put

    Q=-(X^dagger G+G X)>=0.

The Lyapunov integral gives

    G=integral_0^infinity exp(X^dagger t) Q exp(X t) dt>=0.

Since G is nonsingular, G>0. Because X is real, H=Re G is a real symmetric
positive-definite matrix and taking real parts gives

    X^T H+H X<=0

for every X in C, contradicting the result above. An expansion inequality is
reduced to the contraction case by replacing eta with -eta. The equality case is
included as well. Hence the obstruction covers arbitrary fixed real or complex
similarities to ordinary nondegenerate Hermitian contraction or expansion
semigroups, including split-metric equality classes.

This consequence is same-dimensional and metric-based. It does not exclude a
general invariant-cone realization, a dilation by ancillary modes, or a different
Gaussian support.

## 4. Exact full-span certificate

Let

    E=span{e},    V=e^perp,
    Q=ee^T/3,     P=I-Q.

The natural permutation representation is E direct-sum V, where E is trivial and
V is the two-dimensional standard representation. Consequently, under conjugation
by S3,

    M_3(R)
      = Hom(E,E) direct-sum Hom(V,E) direct-sum Hom(E,V)
        direct-sum End(V)
      = 2 trivial + sign + 3 standard.

We now give explicit coordinates on the three standard copies. Define

    u(X)=P X e,
    v(X)=P X^T e,
    w(X)=P diag(P X P),

and

    Phi(X)=(u(X),v(X),w(X)) in V direct-sum V direct-sum V.

For every permutation matrix Pi, P commutes with Pi, Pi e=e, and

    diag(Pi Y Pi^T)=Pi diag(Y).

It follows that

    Phi(Pi X Pi^T)=Pi Phi(X),

with Pi acting on each of the three V factors. Thus Phi is equivariant.

The restriction of Phi to the standard isotypic component is an isomorphism.
Indeed, on Hom(E,V), every matrix has the form

    X=u e^T/3,    u in V,

and Phi(X)=(u,0,0). Similarly, on Hom(V,E), every matrix has the form

    X=e v^T/3,    v in V,

and Phi(X)=(0,v,0).

The remaining standard copy is the space

    Sym_0(V)
      ={Y:Y^T=Y, Ye=0, tr Y=0}

inside End(V). For Y in Sym_0(V), PYP=Y and diag(Y) lies in V, so

    w(Y)=diag(Y).

This map is invertible. Explicitly, if d=(d_1,d_2,d_3)^T lies in V, then

    Y(d) =
      [ d_1  d_3  d_2 ]
      [ d_3  d_2  d_1 ]
      [ d_2  d_1  d_3 ]

is symmetric, has zero row sums and zero trace, and satisfies diag(Y(d))=d.
Therefore Phi maps the three standard summands isomorphically onto V^3. Its
kernel is precisely the sum of the two trivial copies and the sign copy.

Write the three standard coordinates as the columns of

    R(X)=[u(X)  v(X)  w(X)],

and denote its i-th site row by

    r_i(X)=(u_i(X),v_i(X),w_i(X)).

Every column of R(X) belongs to V, hence

    r_1(X)+r_2(X)+r_3(X)=0.

The multiplicity space generated by the permutation orbit of a collection of
matrices is the linear span of all of their site rows. To see this directly,
identify V^3 with V tensor R^3. The restrictions to V of the four group elements

    I, (12), (23), (12)(23)

are linearly independent in End(V). For example, in the basis

    (1,-1,0)^T,    (1,1,-2)^T

their matrices are

    [ 1  0 ]   [ -1  0 ]   [ 1/2  3/2 ]   [ -1/2  -3/2 ]
    [ 0  1 ],  [  0  1 ],  [ 1/2 -1/2 ],  [  1/2  -1/2 ],

respectively. Hence the real span of the S3 action on V is all of End(V).
For a tensor R in V tensor R^3, applying End(V) to its V factor generates
V tensor M_R, where M_R is the span of its site rows. For several seed tensors,
the generated multiplicity space is the span of all of their site rows.

For the present A and B, direct evaluation gives

    9 r_1(A)=(-12 epsilon,  9-3 epsilon,  -epsilon),
    9 r_2(A)=(  6 epsilon,    6 epsilon,  3-epsilon),
    9 r_1(B)=(         18, -9-9 epsilon, -3 epsilon).

Thus these three site rows span the full three-dimensional multiplicity space
whenever

    det [
      -12 epsilon      9-3 epsilon      -epsilon
        6 epsilon        6 epsilon       3-epsilon
           18          -9-9 epsilon     -3 epsilon
    ]
      =162(2 epsilon^3+epsilon^2-4 epsilon+3)

is nonzero. If

    f(epsilon)=2 epsilon^3+epsilon^2-4 epsilon+3,

then

    f'(epsilon)=2(3 epsilon-2)(epsilon+1).

The only stationary point on epsilon>=0 is epsilon=2/3, where

    f(2/3)=37/27>0.

It is the global minimum on the nonnegative half-line. Hence all three standard
copies, of total dimension six, occur in the orbit span.

For completeness, define the sign coordinate

    chi(X)
      =(X_12-X_21)+(X_23-X_32)+(X_31-X_13).

Permutation conjugation gives

    chi(Pi X Pi^T)=sgn(Pi) chi(X),

so chi detects the one-dimensional sign summand. For A,

    chi(A)=4+epsilon != 0,

and the sign summand is therefore present.

Finally, tr X and e^T X e are independent coordinates on the two trivial
summands. Their values on A and B have rank two because

    tr A=tr B=-4-epsilon-3 kappa != 0,

while

    e^T B e-e^T A e=-6+2 epsilon != 0

throughout (R). The orbit span consequently contains two trivial dimensions,
one sign dimension, and six standard dimensions. Their dimensions add to

    2+1+3*2=9.

Therefore the two original S3 orbits span all of M_3(R). No larger signed orbit
is required.

## 5. Odd-dimensional obstruction to the Wei 2024 classes

### 5.1 General lemma

Let F be a real family in M_n(R), with n odd. Assume every X in F is Hurwitz,
span_R F=M_n(R), and there is no H>0 satisfying

    X^T H+H X<=0                                                    (Q)

for all X. Then the number-conserving Nambu lifts of F do not satisfy Wei's
Eqs. (2)-(3) for one fixed pair J1,J2, even after an arbitrary fixed
complex-orthogonal CAR basis change.

### 5.2 Nambu setup and reality rigidity

Let zeta=sqrt(2)(c,c^dagger)^T. Its CAR bilinear form and number-conserving
action generator are

    B_CAR = [ 0  I ],
            [ I  0 ]

    D_X = diag(X,-X^T).

Then D_X^T B_CAR+B_CAR D_X=0. The ordinary skew-symmetric coefficient of the
quadratic form is K_X=B_CAR D_X, not D_X itself, and

    (1/4) zeta^T K_X zeta = c^dagger X c - (1/2) tr X.

Consequently the physical Gaussian differs from the corresponding spin lift only
by the strictly positive scalar exp[tau tr(X)/2]. This scalar cannot affect a sign
and will be suppressed in the fixed-support comparison below.

Let W be the one fixed complex CAR basis transformation in a hypothetical Wei
representation, and let J1,J2 be one fixed pair common to every X. Choose the
convention that W maps the original Nambu bilinear form to the canonical
Majorana coordinate space:

    W^T W=B_CAR,
    A_X=W D_X W^(-1).

The CAR identity for D_X then gives A_X^T=-A_X. Pull the two Wei structures back
to the original Nambu coordinates by defining

    U=W^(-1) J1 conjugate(W),
    eta=W^dagger (i J2) W.

Wei's first condition is equivalently

    A_X J1=J1 conjugate(A_X).

With the convention above this becomes

    D_X U=U conjugate(D_X).

Thus the pulled reality operation is the antilinear CAR isometry

    Theta_1=U K,    Theta_1^2=+I or -I,

commuting with every D_X. This reality equality is real-linear in X. Since
span_R F=M_n(R), it extends from X in F to D_Y for every Y in M_n(R), in
particular to Y=I.

Write U in particle-hole blocks. Commutation with

    D_I=diag(I,-I)

kills the off-diagonal blocks. Commutation with all D_Y then gives

    U=diag(alpha I,delta I).

CAR preservation gives alpha delta=1, whereas

    U conjugate(U)=diag(|alpha|^2 I,|delta|^2 I).

Thus Theta_1^2=-I is impossible. A CAR-preserving phase gauge commuting with every
D_X makes Theta_1=K. Full span has removed any hidden Kramers partner.

### 5.3 The contraction structure forces a common H>0

For the surviving symmetric J1 case, let eta_0=iJ2 and recall that

    eta=W^dagger eta_0 W.

Define the other pulled Hermitian form by

    G=U^T B_CAR=W^dagger J1 W.

The second equality uses W^T W=B_CAR and J1^T=J1. Thus G and eta are the
congruence transforms of J1 and eta_0 by the same W. Anticommutation of J1 and J2
gives the coordinate-independent identity

    eta G^(-1) eta = -G.                                          (C)

The other compatibility relation is

    U^dagger eta U = conjugate(eta).

The phase gauge above makes U=I, so G=B_CAR and eta=conjugate(eta). Since eta is
Hermitian, it is real symmetric. Equation (C) therefore becomes

    eta B_CAR eta = -B_CAR.                                       (CAR)

Write

    eta = [ H    R ]
          [ R^T  K ].

Wei's LMI pulls back to D_X^T eta+eta D_X<=0. Its particle-particle principal block
is (Q). For a fixed Hurwitz X define Q_X=-(X^T H+H X)>=0. Then

    H = integral_0^infinity exp(X^T t) Q_X exp(X t) dt >= 0.

If z is in ker H, then z^T Q_X z=0, hence Q_X z=0 and H X z=0. Therefore ker H is
invariant under every X. Full span leaves only ker H={0} or all of R^n, so H>0 or
H=0.

If H=0, the upper-right block of (CAR) requires R^2=-I_n. This is impossible for
odd n over the reals because det(R)^2=det(-I_n)=-1. Consequently H>0, contradicting
the hypothesis. This proves the lemma.

Every X in C(epsilon,kappa) is Hurwitz, and Sections 3-4 give the other hypotheses.
For every parameter point in (R), the supplied natural Nambu generator support
therefore lies outside both fixed-metric sufficient classes of Wei 2024, including
the complex-orthogonal Majorana extension stated after Eq. (3).

This statement concerns the supplied Gaussian vertex support and its natural
principal logarithms, using one common fixed pair and one common fixed complex
CAR basis in the same Nambu dimension. It does not exclude ancillary-mode
dilations, a general invariant-cone similarity, or a different Gaussian support.
Nor does it prove that the resulting Hamiltonian has no different
Hubbard-Stratonovich, fermion-bag, or other positive decomposition.

### 5.4 Small-time robustness against alternate logarithms

The discrete vertices satisfy a stronger local statement. There is a tau_0>0
such that, for every 0<tau<tau_0, the CAR transformations

    g_X(tau)=exp(tau D_X),    X in C(epsilon,kappa),

cannot be assigned alternate one-body logarithms that all satisfy Wei's
Eqs. (2)-(3) in one common complex-orthogonal CAR basis and for one common pair
J1,J2 on the same Nambu space, without adding ancillary modes. The basis and the
pair are allowed to depend on tau, but at each fixed tau they must be common to
the whole family.

We first fix the logarithmic neighborhood needed below. Since the family is
finite, there is a tau_pr>0 such that, for every X in C(epsilon,kappa) and
0<tau<tau_pr, the spectrum of tau D_X lies in the open strip

    {z:-pi<Im z<pi}.

The principal matrix logarithm then exists and the holomorphic functional calculus
gives

    Log(g_X(tau))=tau D_X.                                        (PL)

Suppose that the claimed tau_0 does not exist. There are then tau_m decreasing
to zero and, for each m, alternate generators L_(X,m) such that

    exp(L_(X,m))=g_X(tau_m)

and all L_(X,m), at that fixed m, obey one common Wei structure. Pull this
structure back to the original CAR coordinates, and denote its antilinear-reality
matrix and Hermitian contraction form by U_m and eta_m.

Wei's reality condition exponentiates to

    g_X(tau_m) U_m
      =U_m conjugate(g_X(tau_m)).

The matrices g_X(tau_m) are real. Hence U_m commutes with every g_X(tau_m).
For all sufficiently large m, equation (PL) applies. A matrix commuting with
g_X(tau_m) also commutes with every holomorphic function of it, and therefore

    U_m D_X=D_X U_m

for every X. The full-span reality-rigidity argument of Section 5.2 can now be
applied before making any use of the contraction block. It excludes the
Theta_1^2=-I case. After a CAR-preserving phase gauge that leaves all D_X and
g_X(tau_m) unchanged, we may take U_m=I. Section 5.3 then gives

    eta_m=conjugate(eta_m)=eta_m^T,
    eta_m B_CAR eta_m=-B_CAR.                                    (CAR-m)

Write

    eta_m =
      [ H_m    R_m   ]
      [ R_m^T  K_m   ],

where H_m is real symmetric.

The pulled-back Wei LMI for the alternate generator is

    L_(X,m)^dagger eta_m+eta_m L_(X,m)<=0.

Integrating the derivative of

    exp(s L_(X,m)^dagger) eta_m exp(s L_(X,m))

from s=0 to s=1 gives the group-level inequality

    g_X(tau_m)^dagger eta_m g_X(tau_m)-eta_m<=0.                  (G)

Since

    g_X(tau_m)
      =diag(exp(tau_m X),exp(-tau_m X^T)),

the particle-particle principal block of (G) is

    E_(X,m)^T H_m E_(X,m)-H_m<=0,
    E_(X,m)=exp(tau_m X).                                        (D)

Every X is Hurwitz, so E_(X,m) is Schur stable. Define

    Q_(X,m)=H_m-E_(X,m)^T H_m E_(X,m)>=0.

Iteration of this identity gives

    H_m
      =sum_(k=0)^(N-1)
         (E_(X,m)^T)^k Q_(X,m) E_(X,m)^k
       +(E_(X,m)^T)^N H_m E_(X,m)^N.

The last term tends to zero as N tends to infinity. Consequently

    H_m
      =sum_(k=0)^infinity
         (E_(X,m)^T)^k Q_(X,m) E_(X,m)^k
      >=0.                                                        (PSD)

Moreover H_m cannot vanish. If H_m=0, the upper-right block of (CAR-m) would give

    R_m^2=-I_3,

which is impossible over the reals because

    det(R_m)^2=det(-I_3)=-1.

Thus H_m is a nonzero positive-semidefinite matrix. Define

    H_hat_m=H_m/tr(H_m).

This normalization need not be extended to eta_m; it is used only in the homogeneous
particle-block inequality (D). We have

    H_hat_m>=0,    tr(H_hat_m)=1,

and the set of such matrices is compact. After passing to a subsequence,

    H_hat_m -> H_*

for some H_*>=0 with tr(H_*)=1.

For each fixed X, expansion of E_(X,m) in (D) gives

    E_(X,m)^T H_hat_m E_(X,m)-H_hat_m
      =tau_m(X^T H_hat_m+H_hat_m X)+O(tau_m^2).

The remainder is uniform along the sequence because the family is finite and
the normalized positive-semidefinite matrices have bounded norm. Divide by
tau_m and take the limit. The cone of negative-semidefinite matrices is closed,
so

    X^T H_*+H_* X<=0                                              (Q*)

for every X in C(epsilon,kappa).

It remains only to check that H_* is positive definite rather than merely
semidefinite. If z lies in ker(H_*), let

    Q_X=-(X^T H_*+H_* X)>=0.

Then z^T Q_X z=0, and positivity of Q_X implies Q_X z=0. Since H_* z=0, this
identity reduces to

    H_* X z=0.

Thus ker(H_*) is invariant under every X in C(epsilon,kappa), and hence under
their real linear span M_3(R). The only subspaces invariant under all of M_3(R)
are {0} and R^3. Because tr(H_*)=1, its kernel is not all of R^3. Therefore

    H_*>0.

Equation (Q*) now contradicts the exact no-common-H result of Section 3. This
proves the existence of tau_0.

The physical twirl may be chosen with tau smaller than both this tau_0 and the
open small-tau interval where its interacting non-Gaussian invariants remain
nonzero. The argument concerns alternate logarithms of the same finite CAR group
support. It does not exclude a different Gaussian support, a different
Hubbard-Stratonovich transformation, or a different many-body decomposition.

## 6. A wider seven-parameter design cone

Let a,b,c,d,delta_1,delta_2,delta_3 all be positive and set

    A(theta) = [ -a-b-delta_1      a          -b       ]
               [       0       -c-delta_2      c       ]
               [       d            0       -d-delta_3 ]

    B(theta)=S A(theta) S.

Every row has logarithmic infinity rate -delta_i. Fix any t in (0,1) and define

    G_t(theta)
      = d t(1-t) - b(1+t) - c(1-t)
        - delta_1 - delta_2 - delta_3 t^2.

If G_t(theta)>0, the same averaging proof excludes every common H>0. For
x=(1,1,t), the A and B inequalities are

    G_t + r p_t <= 0,
    G_t - r q_t <= 0,

where

    p_t=(2+t)[(1-t)(d-c)-b(1+t)-delta_1-delta_2-delta_3 t] > 0,
    q_t=(2-t)[(1-t)(c+d)+b(1+t)+delta_1+delta_2-delta_3 t] > 0.

The displayed signs are consequences of G_t>0, not additional assumptions.
Indeed, positivity of all seven parameters and t in (0,1) give

    d(1-t)>delta_3 t,

and

    p_t/(2+t)
      =G_t+(1-t)[d(1-t)-delta_3 t]>0,
    q_t/(2-t)
      =(1-t)d-delta_3 t+(1-t)c+b(1+t)+delta_1+delta_2>0.

They require r<0 and r>0. Multiplying by q_t and p_t and adding gives the exact
Farkas contradiction

    (p_t+q_t) G_t <= 0.

For fixed rational t these are rational linear inequalities. Within the
seven-parameter structured family, G_t>0 is a nonempty open convex cone; removing
overall scale leaves six essential continuous parameters. Here and below, "open"
means relative to this structured design space, not to the ambient space of
arbitrary twelve-tuples in M_3(R). At the original point and t=3/4,

    G_t=1679/16000,
    p_t=10109/16000,
    q_t=15375/16000.

Full span and non-Gaussian interaction are open algebraic conditions and hold at
this point. Their intersection with G_t>0 contains an open neighborhood.

## 7. Physical realization by two interacting S3 twirls

For X=A or B define

    M_X(tau) = (1/6) sum_(sigma in S3)
                 exp[tau c^dagger (P_sigma X P_sigma^T) c].

Within each particle-number sector the exterior-power representation of S3 is real
and multiplicity-free. Group averaging therefore makes M_X Hermitian.

We now give exact local certificates for interaction and failure of Gaussian
closure. Let alpha_X(tau) and beta_X(tau) be the scalar eigenvalues of the
one-particle twirl on the trivial and standard irreducible sectors. Then

    alpha_X(tau)=(1/3) e^T exp(tau X) e,
    beta_X(tau)=(1/2)[tr exp(tau X)-alpha_X(tau)].

Under the three-dimensional Hodge identification,

    wedge^2 exp(tau X)=exp[tau tr(X)] exp(-tau X^T).

The sign irrep in the two-particle sector corresponds to the uniform Hodge vector,
so its twirl eigenvalue is

    d_(2,X)(tau)
      =exp[tau tr(X)] (1/3) e^T exp(-tau X) e.

Put

    a_X=(1/3)e^T X e,        b_X=(1/3)e^T X^2 e,
    t_X=tr(X),                s_X=tr(X^2).

Taylor expansion gives

    beta_X(tau)
      =1+(t_X-a_X)tau/2+(s_X-b_X)tau^2/4+O(tau^3),
    d_(2,X)(tau)
      =1+(t_X-a_X)tau
       +(t_X^2/2-t_X a_X+b_X/2)tau^2+O(tau^3).

The two required certificates are different. A permutation-invariant operator that
is a constant plus a number-conserving one-body operator has vacuum eigenvalue one,
one-particle standard eigenvalue beta_X, and two-particle sign eigenvalue
2 beta_X-1. Hence

    d_(2,X)-(2 beta_X-1)
      =[(t_X^2-s_X)/2-t_X a_X+b_X]tau^2+O(tau^3)                 (I_X)

is an interaction certificate.

Likewise M_X(tau) is analytic and equals I at tau=0. If it were Gaussian at
arbitrarily small positive values of tau, its principal operator logarithm at those
values would be quadratic. Since M_X commutes with particle number, that logarithm
would be number-conserving, and exterior-power multiplicativity would require
d_(2,X)=beta_X^2. Thus

    d_(2,X)-beta_X^2
      =[(t_X^2-s_X)/2-t_X a_X+b_X
        -(t_X-a_X)^2/4]tau^2+O(tau^3)                            (G_X)

is a non-Gaussian certificate.

At epsilon=1/100 and kappa=1/1000, direct substitution into these exact formulas
produces

    I_A(tau)=(15062013/3000000)tau^2+O(tau^3),
    G_A(tau)=(363599/360000)tau^2+O(tau^3),

and

    I_B(tau)=(3056033/3000000)tau^2+O(tau^3),
    G_B(tau)=(797/120000)tau^2+O(tau^3).

All four leading coefficients are nonzero. Analyticity therefore makes both twirls
interacting and non-Gaussian for all sufficiently small positive tau. The
coefficients depend continuously on the matrix parameters, so the conclusion
persists on an open neighborhood of the rational point.

For positive g_A,g_B, sums of local copies on overlapping triangular clusters,

    H = -sum_Delta [g_A M_(A,Delta)+g_B M_(B,Delta)],

admit an exact determinant-valued continuous-time Gaussian-vertex series expansion.
Expanding exp(-beta H) and then resolving each twirl insertion selects one of the
twelve Gaussian generators with a nonnegative scalar activity. The individual
Gaussian vertices need not be Hermitian or positive operators; only the complete
twirl is Hermitian. The Fock trace for every sequence is

    det[I + product_j exp(t_j X_j)] >= 0.

This is an engineered interacting Hamiltonian with an exact sign-free series
expansion, not a standard auxiliary-field DQMC decomposition of a two-body Hubbard
Hamiltonian. No sampler, estimator, or scaling benchmark is claimed. Determinant
positivity holds at arbitrary word depth, not merely over a sampled range.

## 8. Novelty boundary and publication position

Established ingredients include logarithmic norms, common polyhedral Lyapunov
functions, contraction semigroups, and group twirling. The theorem candidate is the
combination of:

- an explicit seven-parameter QMC vertex family occupying an open region relative
  to its structured design cone and certified by a common polyhedral norm;
- exact failure of all common ellipsoidal metrics;
- a full-span odd-dimensional obstruction separating the same support from Wei 2024
  even under fixed complex CAR basis changes;
- a Hermitian interacting realization using only the original twelve vertices.

Current limitations are equally important:

- this positive-coupling twirled-contraction Hamiltonian has a vacuum ground-state
  no-go at mu=0;
- Hamiltonian-level inequivalence to every alternative positive decomposition is
  not proved;
- absence in a literature search cannot establish priority;
- a dedicated final-family harness and external proof review are still missing.

After those checks, the result may support a short mathematical-physics note or a
rigorous progress report on challenge issue 121. The current package is not yet a
publication-ready condensed-matter result.

The separate Perron-plus-second-compound construction in
`finite_density_extension.md` escapes the vacuum no-go locally, but its current
grand-canonical lattice realization is cell-factorized and conserves particle
number in every cell. Its one-particle-per-cell sector carries qutrit compass terms,
but projected qutrit positivity and itinerant intercell exchange are not proved.
