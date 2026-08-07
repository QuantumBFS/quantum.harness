# Finite-occupancy cell extension: Perron cones plus compound contraction

Date: 2026-07-29

Status: analytic research note. The determinant theorems, the explicit D4 family,
the local spectra, and the exclusion of a common one-particle indefinite metric are
proved below. The current lattice construction is a grand-canonical, cell-factorized
fermion embedding with no intercell hopping. Positivity after projection to one
particle per cell, equivalence to every possible 6-by-6 Majorana/MTR representation,
and literature priority are not proved. Finite density is an optional physical
extension, not an acceptance condition of issue #121. Nothing in this note should
be read as weakening the complete interacting finite-temperature realization in
`physical_realization.md`.

## Executive result

The vacuum no-go is not a theorem about every determinant-positive semigroup. It is
a theorem about semigroups that contract the entire one-particle space. A different
safe mechanism is possible:

1. every vertex preserves one common proper cone K, so every word has a nonnegative
   Perron eigenvalue equal to its spectral radius;
2. the second exterior power of every vertex contracts in one common norm.

The second condition permits at most one eigenvalue outside the unit disk. The first
condition forces that exceptional eigenvalue, if it exists, to be positive. Hence no
real eigenvalue can cross -1 and every word T obeys det(I+T)>0.

Unlike an ordinary contraction, a vertex may now have one eigenvalue a>1. A
Hermitian Gaussian vertex can therefore favor a one-particle state over the vacuum.
This gives a genuine algebraic escape from the vacuum no-go.

An explicit continuous family is

    G_v = b I + (a-b) v v^T,

with a>1, 0<b<1, and ab<1. For the exact example used below,

    a=2,   b=1/4,

and v belongs to

    V_D4 = {(e0+e1)/sqrt(2), (e0-e1)/sqrt(2),
            (e0+e2)/sqrt(2), (e0-e2)/sqrt(2)}.

These are a four-element D4 orbit inside a square polyhedral cone. This is already a
family with open parameters, not an isolated numerical A matrix.

## 1. Arbitrary-dimensional Perron-compound theorem

Let K be a proper cone in R^n: closed, convex, pointed, and with nonempty interior.
Let S be a set of real n-by-n matrices satisfying

    G K is a subset of K                                      (1)

for every G in S. Assume that one induced norm on the second exterior space obeys

    ||wedge^2 G||_2c <= q <= 1                                (2)

for every G in S. The subscript 2c labels the chosen common compound-space norm; it
need not be Euclidean.

For every nonempty word

    T = G_m ... G_2 G_1,

we then have

    det(I+T) >= 0.

If q<1, the inequality is strict.

### Proof

Cone invariance is multiplicatively closed, so T K is a subset of K. The
finite-dimensional Perron-Frobenius/Krein-Rutman theorem says that rho(T) is an
eigenvalue of T and rho(T)>=0.

The eigenvalues of wedge^2 T are all products lambda_i lambda_j with i<j. By
submultiplicativity,

    ||wedge^2 T||_2c <= q^m.

Suppose T had a real eigenvalue lambda<-1. Then rho(T)>=|lambda|>1, while +rho(T)
is also an eigenvalue. Consequently -rho(T)|lambda| is an eigenvalue of wedge^2 T
with magnitude greater than one, contradicting (2). Thus every negative real
eigenvalue lies in [-1,0). Nonreal eigenvalues occur in conjugate pairs, and hence

    det(I+T)
      = product_{lambda real}(1+lambda)
        product_{Im lambda>0}|1+lambda|^2
      >= 0.

When q<1, the same argument excludes lambda=-1, proving strict positivity.

This proof permits arbitrarily large positive Perron eigenvalues. It controls only
the product of any two eigenvalues, not the largest one-particle eigenvalue.

### A bounded positive-fugacity window

If q<1 and the word is nonempty, any negative real eigenvalue lambda satisfies

    |lambda| rho(T) <= q^m,   rho(T)>=|lambda|,

so

    |lambda| <= q^(m/2) <= sqrt(q).

It follows that

    det(I+zT)>0   for 0<=z<1/sqrt(q).

This allows a finite z>1 window. It does not allow a fixed positive chemical
potential for all inverse temperatures, because z=exp(beta mu) is unbounded as
beta tends to infinity.

### Exact particle-sector ceiling from a low compound contraction

The determinant theorem and the ground-state filling question are distinct. The
following proposition gives the precise obstruction for Hermitian positive
Gaussian Hamiltonian terms.

Let G_a be real symmetric positive definite, let g_a≥0, and define

    H=−sum_a g_a Γ(G_a).

Fix r≥1. If one Euclidean exterior norm obeys

    ||wedge^r G_a||₂≤q<1

for every a, then no sector with N≥r can be a ground sector. Indeed, if
s₁≥...≥s_n>0 are the singular values of G_a, then

    s₁...s_r≤q,   s_r<1,

and for every N≥r,

    ||wedge^N G_a||₂=s₁...s_N≤s₁...s_r≤q.

Since wedge^N G_a is positive definite,

    E_min(H restricted to wedge^N V)≥−q sum_a g_a
                                      >−sum_a g_a=E_vac.       (4)

The same proof applies to a Hermitian twirl or positive convex average when every
resolved positive Gaussian obeys the same bound. Thus r=1 reproduces the vacuum
no-go. A global r=2 certificate permits at most one particle in the ground state;
a fixed r can never support nonzero density as the volume tends to infinity. To
place N≈νn particles using this particular ceiling mechanism, r must exceed N and
therefore scale at least linearly with n.

For one D4 cell, r=2 and q=ab<1, so (4) excludes N≥2 while the Perron direction
allows N=1 to beat the vacuum. This is the intended local escape. It must not be
misstated as a global total-particle bound for the cell-factorized lattice: a local
embedding has spectator identity directions, and a direct sum of two cells has
wedge² components G_i tensor G_j. Two cells may each have one expanding Perron mode,
so the strict global second-compound bound fails. Extensive occupancy in the
current model comes only from fixed-cell factorization, not from tensorization of
the one-expanding-mode theorem.

## 2. Exact D4 polyhedral family

Work in R^3 with basis e0,e1,e2 and the square cone

    K_square = {x : x0>=|x1| and x0>=|x2|}.

Its dual cone is

    K_square^* = {y : y0>=|y1|+|y2|}.

Every vector in V_D4 belongs to both K_square and K_square^*. Therefore, for x in
K_square,

    G_v x = b x + (a-b) v (v^T x)

is a positive linear combination of two vectors in K_square. Hence every G_v
preserves K_square.

The square cone has four extreme rays, whereas a three-dimensional simplicial cone
such as the nonnegative orthant has only three. An invertible linear map preserves
the number of extreme rays. This certificate is therefore not entrywise
nonnegativity hidden by a change of one-particle basis.

Each G_v is real symmetric positive definite, with eigenvalues

    a along v,   b,b on v^perp.

Its two largest singular values are a and b, so the Euclidean compound norm is

    ||wedge^2 G_v||_2 = ab.

Thus every a>1, 0<b<1, ab<1 gives a strict determinant-positive semigroup. For
a=2,b=1/4,

    ||wedge^2 G_v||_2 = 1/2,

and every nonempty word made from the four vertices has det(I+T)>0.

The construction also works for any collection of unit vectors contained in
K intersection K^*, provided the same a,b obey ab<1. It is therefore a continuous
geometric family rather than four special matrices.

## 3. Exact exclusion of a common one-particle indefinite metric

The full D4 family admits no nonzero Hermitian matrix eta satisfying either

    G_v^dagger eta G_v - eta <= 0                              (3)

for all v, or the reversed inequality for all v. This excludes every ordinary
one-particle contraction or expansion semigroup based on a fixed nondegenerate
quadratic metric, including indefinite metrics.

### Proof for (3)

Every v in V_D4 has an orthogonal partner w in V_D4. For example,

    (e0+e1)/sqrt(2) is orthogonal to (e0-e1)/sqrt(2).

The vector w has eigenvalue b under G_v and eigenvalue a under G_w. Evaluating the
two negative-semidefinite inequalities on w gives

    (b^2-1) w^dagger eta w <= 0   implies   w^dagger eta w >=0,
    (a^2-1) w^dagger eta w <= 0   implies   w^dagger eta w <=0.

Therefore w^dagger eta w=0. The same holds for every v in V_D4.

Set Q_v=G_v^dagger eta G_v-eta. Since Q_v<=0 and

    v^dagger Q_v v=(a^2-1)v^dagger eta v=0,

negative semidefiniteness implies Q_v v=0. For any u perpendicular to v,

    u^dagger Q_v v=(ab-1)u^dagger eta v=0.

Because ab is not one, eta v=0. Three vectors in V_D4 are linearly independent,
so eta=0. This contradicts the nondegeneracy required of a metric.

The reversed semidefinite inequality gives the same conclusion with all intermediate
signs reversed.

Since

    log G_v = (log b) I + log(a/b) v v^T,

a common generator inequality

    (log G_v)^dagger eta + eta log G_v <= 0

would exponentiate to (3). It is therefore excluded as well.

### Exclusion of the same-support Wei/Majorana fixed-metric representation

The four principal logs have a four-dimensional linear span, not the full
six-dimensional space of real symmetric 3-by-3 matrices. Their generated Lie
algebra is nevertheless all of gl(3,R).

Indeed, differences of opposite orbit elements give

    X_01=E_01+E_10,   X_02=E_02+E_20.

Their sums give two inequivalent diagonal directions. Commuting those diagonals
with X_01 and X_02 generates the skew 01 and 02 matrices, while
[X_01,X_02] gives the skew 12 matrix. Further diagonal commutators give X_12;
the original traceful diagonal plus [X_ij,skew_ij] gives every diagonal. Hence the
full matrix algebra is generated and the common commutant is scalar.

Consequently the support is irreducible and has no nontrivial common invariant
subspace. A number-conserving complex-CAR Wei/MTR reality operator must lie in this
commutant; in odd one-particle dimension a scalar commutant cannot carry the
required Kramers square -I. The remaining fixed-metric top-block condition would
give a real symmetric H satisfying

    (log G_v)^T H + H log G_v <= 0

for every v. Exponentiation gives G_v^T H G_v-H<=0, but the direct proof above
forces H=0. The remaining Majorana block relation in odd dimension then rules out a
nondegenerate fixed metric. Thus this exact log-vertex support is not a disguised
Wei complex-CAR fixed-metric contraction class.

This is stronger than merely excluding a three-dimensional positive metric.
It does not exclude a different Gaussian/HS decomposition of the same Hamiltonian,
an enlarged or explicitly doubled fermion representation, nonprincipal complex logs,
or a representation not using this fixed vertex support. Those alternatives and
historical priority remain open.

## 4. Hermitian finite-density local physics

Define the Fock-space Gaussian vertex

    O_v = Gamma(G_v) = exp[dGamma(log G_v)].

Because G_v is symmetric positive definite, O_v is Hermitian positive definite;
no group twirl is required. Its sector maxima are

    N=0 : 1,
    N=1 : a,
    N=2 : ab,
    N=3 : ab^2.

For a>1>b and ab<1, the unique largest eigenvalue is a in the one-particle state

    |v> = c_v^dagger |0>.

Consequently -g O_v locally favors exactly one fermion rather than vacuum or full
occupancy. This is the precise step that the common-contraction construction could
not achieve.

For the equal D4 orbit sum,

    H_cell = -kappa sum_{v in V_D4} O_v,

the exact largest eigenvalues of the positive orbit sum in each number sector at
a=2,b=1/4 are

    N=0 : 4,
    N=1 : 9/2, 11/4, 11/4,
    N=2 : 9/8, 25/16, 25/16,
    N=3 : 1/2.

Thus the decoupled H_cell has a unique N=1 ground state e0, separated from the
vacuum by kappa/2. This is a rigorous finite-occupancy local ground state at mu=0.

## 5. A local lattice model and its exact determinant proof

Put three fermion orbitals in every cell i and write O_i(v)=Gamma_i(G_v). Allow
onsite orbit sums and bond vertices

    O_i(v) O_j(w)
      = Gamma(G_v on cell i direct-sum G_w on cell j).

A general positive-vertex Hamiltonian is

    H = -sum_i,v h_i,v O_i(v)
        -sum_<ij>,v,w J_ij,vw O_i(v) O_j(w),

with h_i,v>=0 and J_ij,vw>=0.

Every one-particle propagation matrix in the stochastic-series expansion is block
diagonal in the fixed cells. For a configuration C,

    T(C) = direct-sum_i T_i(C),

where each T_i is a word in the local D4 semigroup. Therefore

    det[I+T(C)] = product_i det[I+T_i(C)] >0.

This is an all-orders analytic certificate, not a random-word observation.

On a fixed finite graph, sufficiently weak bond terms compared with the full product
gap preserve the one-fermion-per-cell ground sector. A thermodynamic statement needs
a degree- and coupling-uniform gap bound, which is not supplied here. The conserved
N_i=1 sector is three-dimensional and carries a qutrit representation, but strong
H_cell makes e0 unique; an active low-energy qutrit manifold has not been established.

### Matched and crossed D4 pairs generate both exchange signs

Let

    X_01=|e0><e1|+|e1><e0|,
    G_{s,x}=A_x+s (a-b)X_01/2,   s=+1,-1,

where A_x is diagonal. Then

    G_{+,x} tensor G_{+,x} + G_{-,x} tensor G_{-,x}
      = 2 A_x tensor A_x + (a-b)^2 X_01 tensor X_01/2,

while

    G_{+,x} tensor G_{-,x} + G_{-,x} tensor G_{+,x}
      = 2 A_x tensor A_x - (a-b)^2 X_01 tensor X_01/2.

Since H carries an overall minus sign, matched and crossed positive vertex pairs
produce respectively ferro and antiferro X_01 X_01 exchange. The y pair similarly
produces X_02 X_02. In the conserved N_i=1 sector, a triangular arrangement of
crossed pairs therefore contains sign-frustrated qutrit compass-type terms.
Independently, the full grand-canonical fermionic expansion has positive determinant
weights; this does not prove positivity after projection to the qutrit sector.

There is an exact diagonal-sign-gauge obstruction already in the e0,e1 subspace.
Put crossed x pairs on all three edges of a triangle. The restricted off-diagonal
term is +J sum_triangle X_01,i X_01,j. In the configuration graph,

    |000> -> |110> -> |101> -> |000>

is a three-edge cycle with positive edge-sign product. A diagonal sign gauge that
made every off-diagonal element nonpositive would require the product around an odd
cycle to be negative, which is impossible. Thus this restriction is not Fock-sign-
gauge stoquastic.

The pure one-color X_01 X_01 model is nevertheless diagonal in the local X_01
basis and is classically simple. A serious quantum target must use both x and y
bond colors, because X_01 and X_02 do not commute on a shared cell. Whether the full
two-color compass model is curable by a more general local unitary is not yet proved.

This is the most concrete nontrivial physical target found in this audit.

## 6. Why the current lattice extension is not yet an itinerant-fermion result

The determinant proof uses a fixed direct sum of three-orbital cells. It has three
important consequences:

1. every local particle number N_i is conserved;
2. fermions never exchange between different cells;
3. in the N_i=1 sector the model is exactly a qutrit/spin model.

Thus the grand-canonical fermion embedding has a strictly positive factorized
determinant expansion, and its conserved N_i=1 sector carries a qutrit Hamiltonian.
It does not follow that the canonically projected qutrit configuration weights are
nonnegative, and the construction does not solve the exchange sign of itinerant
finite-density fermions.

Allowing one-particle hopping between cells destroys block factorization. A scalable
replacement must control an extensive number of expanding channels without reducing
to a fixed occupied subspace, total nonnegativity, or a Kramers square.

### Exact cell-hopping no-go for the present certificate

The absence of intercell hopping is not merely a choice made in the example. It is
forced by preserving the full one-particle-per-cell subspace. Let

    V=direct-sum_(i=1)^L V_i,   dim V_i≥2,

and identify

    W=(wedge^1 V₁) wedge ... wedge (wedge^1 V_L)

with the Fock subspace containing exactly one particle in every cell. If a
number-conserving one-body generator h satisfies

    dGamma(h)W is a subset of W,                               (5)

then h is block diagonal in the cells.

To prove this, write h_ij:V_j→V_i for an off-diagonal block. Acting on
v₁ wedge ... wedge v_L, h_ij replaces v_j by h_ij v_j and produces a component
with two particles in cell i and a hole in cell j. Different occupancy patterns
are linearly independent and cannot cancel. If h_ij v_j is nonzero, dim V_i≥2
allows v_i to be chosen nonparallel to it, so the wedge is nonzero. Condition (5)
for every vector in W therefore forces h_ij=0 for every i≠j.

The same conclusion holds if the certificate preserves a full-dimensional proper
cone C_cell inside W: span(C_cell)=W, so linear invariance of the cone implies (5).
Discrete permutations of entire cells can preserve W, but they are disconnected
relabelings and become qutrit/spin exchange after fixing one particle per cell;
they are not continuous charge hopping.

This proposition concerns the whole subspace W, not one decomposable wedge ray. A
single fixed ray only forces a block-triangular invariant plane, and must not be
used to claim block diagonalization. Genuine itinerancy therefore requires a new
cone spanning charge-fluctuating cell sectors, or a word-dependent extensive
unstable bundle; it cannot be obtained by a small hopping perturbation that keeps
the present tensor-cell certificate.

## 7. General fixed-splitting no-go

Suppose the one-particle space has one common invariant splitting

    V = V_s direct-sum V_u,

and every vertex is block diagonal, G=G_s direct-sum G_u, with

    ||G_s||<=1,   ||G_u^(-1)||<=1.

For every word T,

    det(I+T)
      = det(I+T_s) det(T_u) det(I+T_u^(-1)).

The first and third factors are nonnegative. Its sign is sign det(T_u), a product
of one-vertex orientation characters. Choosing the Hamiltonian coefficient signs to
cancel that character gives a sign-free expansion.

However, fill every orbital in V_u and empty every orbital in V_s. The resulting
Slater determinant is a common eigenstate of every vertex. Exterior-power duality
shows that, after normalization by |det G_u|, every particle excitation in V_s and
every hole excitation in V_u is contractive. Once the Hermitian physical vertices
are formed, that same Slater determinant minimizes every local Hamiltonian term.

Therefore every common fixed stable/unstable splitting has a frustration-free Slater
ground state. Special cases are

- V_u empty: the vacuum no-go;
- V_s empty: the full-filling/inverse-contraction no-go;
- particle-hole doubled blocks: a fixed half-filled Slater reference, usually the
  known split-orthogonal, reflection-positive, or Kramers-square route.

The D4 Perron family escapes this no-go precisely because its expanding Perron line
depends on v; no common unstable linear subspace exists.

## 8. Exact all-fugacity and canonical criteria

For one fixed real T,

    p_T(z)=det(I+zT)

is nonnegative for every z>0 if and only if every distinct negative real eigenvalue
of T has even algebraic multiplicity. Complex pairs contribute positive quadratic
factors, positive real eigenvalues never vanish for z>0, and an odd-multiplicity
negative eigenvalue creates a sign-changing positive root z=-1/lambda.

Strict positivity for all z>0 is equivalent to having no negative real eigenvalue.
For a real 3-by-3 word with detT>0, all-z nonnegativity therefore permits either no
negative real spectrum or one exactly degenerate negative pair; two distinct
negative eigenvalues create a negative interval between their positive roots.

For the S3 Hamiltonian in `physical_realization.md`, a uniform chemical potential
produces z=exp(βμ). Hence fixed μ>0 over arbitrarily large β requires this criterion
for every word. The current z=1 contraction proof does not establish it, so that
finite-density route remains open rather than disproved.

Thus positivity at z=1 is much weaker than positivity at arbitrary positive chemical
potential for all beta. A common norm alone cannot provide the latter.

The fixed-N weight is

    Z_N(T)=Tr(wedge^N T),

the coefficient of z^N in det(I+zT). Even positivity of p_T(z) for all z>0 does not
imply every coefficient is nonnegative. In the D4 cell construction, projection to
N_i=1 replaces each local grand-canonical determinant by tr(T_i); the
Perron-compound theorem does not prove these traces nonnegative. Canonical
finite-density or direct qutrit QMC therefore needs a separate compound-trace or
cone proof.

Known easy sufficient mechanisms are:

- two identical/conjugate flavors: determinant square, already Kramers/MTR;
- total nonnegativity: every principal minor and every Z_N is nonnegative, but the
  induced Fock matrices are entrywise nonnegative and -H is stoquastic/Jordan-Wigner
  type;
- a common triangular positive-diagonal semigroup: arbitrary-z positivity, but any
  Hermitian element in the common flag algebra is simultaneously diagonal/classical.

## 9. k-expanding hierarchy

There is an arbitrary-index extension. Let S be a real matrix semigroup. Assume

1. for every j=1,...,k, wedge^j S preserves a proper cone K_j;
2. one common norm on wedge^(k+1) obeys ||wedge^(k+1)G||<=1 for every generator.

Then det(I+T)>=0 for every word T.

To prove it, let r be the number of eigenvalues of T outside the unit disk. The
(k+1)-compound bound gives r<=k. If r>0, the product of all r unstable eigenvalues
is the unique eigenvalue of wedge^r T with maximal modulus. Cone preservation of
wedge^r T forces this product to be positive. Hence the number of negative real
unstable eigenvalues is even; all stable negative eigenvalues give nonnegative
factors 1+lambda.

The uniqueness statement remains valid for nonnormal matrices, Jordan blocks,
repeated eigenvalues, and equal moduli. Schur triangularization shows that the
compound spectrum consists of products of eigenvalues counted with algebraic
multiplicity. Since r counts every eigenvalue with modulus greater than one, any
different r-element product must replace at least one unstable factor by a factor
of modulus at most one, and therefore has strictly smaller modulus. Complex
unstable eigenvalues enter in conjugate pairs. A boundary eigenvalue lambda=-1 may
make the determinant zero but cannot make it negative.

This hierarchy can support a local term whose maximum lies in an intermediate
particle sector k. It is not automatically total positivity because the K_j may be
non-simplicial, non-coordinate polyhedral cones.

For an extensive itinerant density k proportional to volume, however, the number and
dimension of the required exterior cones grow rapidly. The cell-factorized model is
a tensorized shortcut, but it removes intercell fermion exchange. A publishable
itinerant construction needs a local/tensor certificate for this hierarchy or a
word-dependent dominated splitting that remains efficient with system size.

## 10. Publication assessment

The result is stronger than the earlier all-contraction candidate:

- it genuinely evades the vacuum no-go;
- it is a continuous parameter family;
- its local terms are Hermitian without twirling;
- its decoupled cell Hamiltonian has a unique N=1 local ground state at mu=0;
- it has no common one-particle positive or indefinite quadratic metric.

It is not yet a publication-ready condensed-matter result:

- common invariant cones, Perron semigroups, compound contractions, and dominated
  splittings are established mathematics;
- a hidden alternative Majorana/MTR or positive Gaussian decomposition of the same
  Hamiltonian has not been excluded;
- the scalable model has fixed cells and no intercell fermion exchange;
- no phase diagram, critical point, or algorithmic benchmark has been produced.

Current rating: a credible research lemma and a promising construction principle,
not yet a PRB claim. It could become publishable if either

1. the D4 family is excluded from alternative Majorana/MTR/Wei decompositions and
   yields a two-color nonstoquastic qutrit model with a useful QMC algorithm; or
2. the cone-compound hierarchy is extended to local itinerant hopping at extensive
   density and produces new finite-density physics.

A PRB or SciPost-level paper would need a scalable algorithm, a physically motivated
model, a novelty audit against alternative decompositions, and a nontrivial phase or
critical point. A broad one-flavor itinerant finite-density class could be PRL-level.

## 11. Literature anchors

- Z.-C. Wei, Semigroup approach to the sign problem in quantum Monte Carlo
  simulations, Phys. Rev. B 110, 075146 (2024):
  https://doi.org/10.1103/PhysRevB.110.075146
- V. Yu. Protasov, Perron matrix semigroups (2025):
  https://arxiv.org/abs/2502.10571
- R. Alseidi, M. Margaliot, and J. Garloff, Discrete-time k-positive linear
  systems, IEEE Trans. Autom. Control 66, 399-405 (2021):
  https://doi.org/10.1109/TAC.2020.2987285
- E. Weiss and M. Margaliot, A generalization of linear positive systems with
  applications to nonlinear systems (2019):
  https://arxiv.org/abs/1902.01630
- L. Wang et al., Split orthogonal group: a guiding principle for sign-problem-free
  fermionic simulations, Phys. Rev. Lett. 115, 250601 (2015):
  https://doi.org/10.1103/PhysRevLett.115.250601

No searched QMC source was found that combines a proper Perron cone with a strict
second-compound contraction to certify det(I+word)>=0. This is a negative search
result, not a proof of priority.
