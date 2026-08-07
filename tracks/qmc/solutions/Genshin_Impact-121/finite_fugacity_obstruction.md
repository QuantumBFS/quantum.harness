# Finite-fugacity obstruction for positive and Metzler transfer products

Date: 2026-07-30

Status: analytic obstruction note. Statements marked **[Derived]** are proved
directly below. Decimal values marked **[Numerical]** are evaluations of the
displayed exact formulas, not independent numerical experiments. Statements
marked **[Primary]** are taken from the primary sources listed in section 8.

## Executive result

Let `T` be the real one-particle transfer matrix of one auxiliary-field
configuration, and let the fugacity be `z>0`. The grand-canonical fermion factor is

    p_T(z) = det(I + z T).

The exact all-fugacity criterion is spectral:

    p_T(z)>0 for every z>0

if and only if `T` has no negative real eigenvalue. Entrywise positivity,
substochasticity, an ordinary `ℓ∞` contraction, or membership in a product
semigroup of Metzler exponentials does not imply this criterion.

The sharp hierarchy relevant here is:

1. a general nonnegative strict-substochastic matrix can fail already in `2×2`;
2. one Metzler exponential has `p_T(z)≥0` for every `z>0`, but can have an
   even-multiplicity zero, with a minimal `3×3` example;
3. a product of two Metzler exponentials can have `p_T(z)<0`, again minimally
   in `3×3`;
4. one symmetric positive-definite (SPD) matrix, or a product of two SPD
   matrices, is safe for every `z>0`; three SPD factors already need not be safe.

Consequently, an ordinary contraction certificate at `z=1` extends only to the
bounded window

    z ||T||_∞ < 1.

It does not establish sign-freedom at arbitrary chemical potential.

## 1. Exact fixed-matrix criterion

### 1.1 Strict positivity

**Theorem [Derived].** For a real square matrix `T`,

    det(I+zT)>0 for every z>0

if and only if `T` has no negative real eigenvalue.

To see this, list the eigenvalues with algebraic multiplicity. Realness pairs every
nonreal eigenvalue with its conjugate, and

    det(I+zT)
      = ∏_{λ real} (1+zλ)
        ∏_{Im λ>0} |1+zλ|².

Every conjugate-pair factor is strictly positive. A nonnegative real eigenvalue
also gives a positive factor. Conversely, every negative real eigenvalue `λ<0`
creates a positive zero at

    z = -1/λ.

This argument does not assume diagonalizability.

### 1.2 Weak nonnegativity

**Corollary [Derived].**

    det(I+zT)≥0 for every z>0

if and only if every distinct negative real eigenvalue of `T` has even algebraic
multiplicity. An odd multiplicity gives a sign-changing positive root; an even
multiplicity gives a touching root.

Thus an all-`z` nonnegative theorem is weaker than the strict sign-free statement
needed to exclude zero-weight configurations and conditioning singularities.

## 2. General nonnegative and substochastic matrices

Consider the exact matrix

    T₂ = (1/4) [[1, 2],
                [2, 1]].

It is entrywise strictly positive and strict substochastic:

    ||T₂||_∞ = 3/4 < 1.

Its eigenvalues are `3/4` and `-1/4`, so

    det(I+zT₂) = (1+3z/4)(1-z/4).

Therefore the determinant vanishes at `z=4` and is negative for `z>4`.

This is the minimal dimension for a general nonnegative counterexample: a
one-dimensional nonnegative matrix has no negative eigenvalue.

### What the ordinary norm bound does prove

**Lemma [Derived].** If

    z ||T||_∞ < 1,

then `det(I+zT)>0`.

Indeed, every eigenvalue obeys `|zλ|≤zρ(T)≤z||T||_∞<1`, so `-1` is not an
eigenvalue of `zT`. The determinant is nonzero throughout the connected interval
from `z=0`, where it equals one, and hence remains positive.

The `2×2` example shows that this window cannot be replaced by all `z>0` using
only entrywise positivity plus strict substochasticity.

## 3. One Metzler exponential: nonnegative, but not strictly positive

A real matrix `A` is Metzler when every off-diagonal entry is nonnegative.
Choosing a scalar `α` such that `A+αI≥0` entrywise gives

    e^A = e^(-α) e^(A+αI) ≥ 0

entrywise. This is an elementary positivity proof.

More is true for one real exponential. Culver's real-logarithm theorem says that
each Jordan block associated with a negative real eigenvalue of a real matrix
having a real logarithm must occur an even number of times. Since `e^A` has the
real logarithm `A`, every negative eigenvalue of `e^A` has even algebraic
multiplicity. Hence

    det(I+z e^A) ≥ 0 for every z>0.                         (3.1)

This implication is **[Derived]** from Culver's **[Primary]** theorem. It does not
give strict positivity.

### 3.1 Exact minimal `3×3` zero

Let

    P = [[0, 1, 0],
         [0, 0, 1],
         [1, 0, 0]],

    a = 2π/√3,
    A = a(P-I),
    q = exp(-√3 π).

The matrix `A` is an irreducible Metzler Markov generator: its row sums vanish.
The eigenvalues of `A` are

    0,  -√3 π + iπ,  -√3 π - iπ.

Therefore **[Derived]**

    E = e^A = ((1+q)/3) J - q I,

where `J` is the all-ones matrix, and

    spectrum(E) = {1, -q, -q}.

Because `q<1/2`, all entries of `E` are strictly positive. Its row sums are one,
so `E` is a strictly positive stochastic matrix. Nevertheless,

    det(I+zE) = (1+z)(1-qz)²,

which vanishes at

    z₀ = 1/q = exp(√3 π)
       ≈ 230.76458831914576.                               [Numerical]

The determinant touches zero and does not become negative, in agreement with
(3.1).

For any `κ>0`,

    A_κ = A - κI,
    e^(A_κ) = e^(-κ) E

is a strictly positive strict-substochastic Metzler exponential. Its all-fugacity
strictness still fails, now at

    z₀(κ) = exp(κ+√3 π).

### 3.2 Minimality

For a real `2×2` Metzler matrix

    A = [[a, b],
         [c, d]],   b,c≥0,

the eigenvalue discriminant is

    (a-d)² + 4bc ≥ 0.

Both eigenvalues of `A` are real, so both eigenvalues of `e^A` are positive.
No negative real eigenvalue, and hence no positive fugacity zero, is possible.
The `3×3` construction above is therefore dimension-minimal within the
single-Metzler-exponential class.

The displayed example is our exact construction, not an example copied from the
embedding literature. Davies and Chen--Chen in section 8 are primary context for
embeddable Markov matrices and coinciding negative eigenvalues.

## 4. Two Metzler exponentials: the determinant can be negative

Retain `E` and `q` from section 3 and define

    D = diag(1/2, 1/2, 1/4) = e^B,
    B = diag(-ln 2, -ln 2, -ln 4).

The matrix `B` is Metzler, while `D` is nonnegative and strict substochastic.
Set

    T = D E.

Then `T` is entrywise strictly positive, strict substochastic, and a product of
two Metzler exponentials.

### 4.1 Exact spectrum reduction

The vector `(1,-1,0)^T` is an eigenvector with

    λ₁ = -q/2.

The subspace `{(x,x,y)^T}` is invariant. In coordinates `(x,y)`, the restriction
of `T` is

    M = (1/3) [[d(2-q),   d(1+q)],
               [2e(1+q), e(1-2q)]],

with `d=1/2` and `e=1/4`. Its trace and determinant are

    τ = 5/12 - q/3,
    det M = -deq = -q/8.

Thus the other two eigenvalues are

    λ_± = (τ ± √(τ²+q/2))/2,

with `λ_+>0` and `λ_-<0`. Their values are

    q   ≈ 0.004333420509983131,                             [Numerical]
    λ₁ ≈ -0.0021667102549915655,                           [Numerical]
    λ_+≈  0.41652266875418265,                             [Numerical]
    λ_-≈ -0.0013004755908437027.                           [Numerical]

The two positive roots of `det(I+zT)` are therefore

    z₁ = -1/λ₁ = 2/q
       ≈ 461.5291766382915,                                [Numerical]

    z₂ = -1/λ_-
       ≈ 768.9494574452068.                                [Numerical]

Consequently **[Derived]**

    det(I+zT) < 0 for z₁<z<z₂.

This is stronger than the single-exponential obstruction: a product can produce
two distinct negative eigenvalues, two distinct positive roots, and a genuinely
negative fugacity interval.

### 4.2 Both factors can be strict contractions

For any `0<r<1`, define

    E_r = rE = exp(A + (ln r)I).

Both `E_r` and `D` are strict-substochastic Metzler exponentials. The product
`D E_r=rT` has the same sign failure, with the interval rescaled to

    z₁/r < z < z₂/r.

Here `E_r` is entrywise strictly positive, while the diagonal factor `D` is only
entrywise nonnegative. If strict entrywise positivity of every factor is also
required, set

    B_ε = B + ε(J-I),

with sufficiently small `ε>0`. Then `B_ε` is irreducible Metzler with negative
row sums, so `e^(B_ε)` is strictly positive and strict substochastic. At a fixed
`z` strictly inside the negative interval, determinant continuity preserves the
strict negative sign for all sufficiently small `ε`. This last perturbative
upgrade is **[Derived by continuity]**; no numerical `ε` threshold is claimed.

### 4.3 Minimality

Every `2×2` nonnegative matrix

    X = [[a,b],
         [c,d]]

has real eigenvalues because its discriminant is `(a-d)²+4bc≥0`. If additionally
`det X>0`, its nonnegative trace forces both eigenvalues to be positive. A product
of real exponentials always has

    det(e^(A_m) ... e^(A_1)) = exp(∑_j tr A_j) > 0.

Hence a `2×2` product of Metzler exponentials cannot have a negative eigenvalue.
The example above proves that dimension three is minimal.

## 5. SPD factors: the safe and unsafe boundaries

Here SPD means real symmetric positive definite. It is a spectral/quadratic-form
property and must not be confused with entrywise nonnegativity.

### 5.1 One or two SPD factors are safe

If `T` itself is SPD, all its eigenvalues are positive and the criterion in
section 1 applies.

If

    T = A B

with `A` and `B` SPD, then `AB` is similar to the SPD matrix

    A^(1/2) B A^(1/2).

Thus all eigenvalues of `AB` are positive and

    det(I+zAB)>0 for every z>0.                              [Derived]

The same conclusion holds for any mutually commuting family of SPD factors,
because their product is again SPD.

### 5.2 Three SPD and entrywise-nonnegative factors can already fail

The following exact construction also closes the narrower
"doubly nonnegative factor" loophole. Define

    A_j = U_j U_j^T + (3/100) I,

with

    U₁ = [[0,1,1],
          [0,0,1],
          [5,6,0]],

    U₂ = [[0,2,4],
          [6,0,4],
          [0,1,2]],

    U₃ = [[5,6,4],
          [1,3,1],
          [1,5,0]].

Every `A_j` is exactly SPD because

    x^T A_j x = ||U_j^T x||² + (3/100)||x||² > 0

for `x≠0`. Every entry is also nonnegative. Their product is exactly

    A₁A₂A₃ = 10^(-6)
      [[14610959127,  5547109600,  7725525900],
       [ 5329719600,  2045197627,  2866091600],
       [84887685900, 32038821600, 44467152827]].

Direct integer arithmetic gives **[Derived, exact]**

    det(I + 34 A₁A₂A₃)
      = -2609548711966855069686607368 / 10^18
      < 0.

Equivalently, the decimal value is

    -2609548711.966855069686607368.                          [Numerical display]

Thus three factors suffice for failure even when every factor is both SPD and
entrywise nonnegative. Since one and two SPD factors are safe, three is the
minimal factor count for this `3×3` phenomenon. Adding an arbitrarily small
positive multiple of `J` to each factor makes every entry strictly positive;
the strict negative determinant persists for sufficiently small perturbations.

These `A_j` are not claimed to be exponentials of symmetric Metzler generators:
an SPD matrix has a symmetric logarithm, but that logarithm need not be Metzler.
This example therefore belongs to the SPD-factor boundary, not to section 4.

### 5.3 Arbitrary SPD products are broadly unconstrained

Ballantine proved **[Primary]** that a real `2×2` matrix of positive determinant
which is not a negative scalar matrix is a product of four real SPD matrices.
For example,

    S = diag(-1,-2)

has positive determinant and is not scalar, so it admits such a four-SPD
factorization. Yet

    det(I+zS) = (1-z)(1-2z) < 0

for

    1/2 < z < 1.

Ballantine's theorem supplies existence of the factors; the determinant
calculation is **[Derived]**. This shows that "each local factor is SPD" is not
an all-fugacity certificate once noncommuting products of unrestricted length are
allowed.

## 6. Consequence for chemical potential

Assume the standard fugacity convention

    z = exp(β μ),

where `β>0` is inverse temperature. If the current construction proves a
configuration-wise bound

    ||T_C||_∞ ≤ ρ < 1

uniformly over all configurations `C`, then section 2 proves only

    0 < z < 1/ρ,

or equivalently

    μ < -(1/β) ln ρ.                                        [Derived]

At `μ=0`, one has `z=1`, which is inside this window. All negative chemical
potentials are also inside it. Positive chemical potential is covered only up to
the displayed finite threshold. At fixed `μ>0`, `z=exp(βμ)` grows without bound
as `β→∞`, so no `β`-independent positive-density conclusion follows from ordinary
contraction.

If the code or Hamiltonian uses the opposite convention `z=exp(-βμ)`, the
inequality reverses in the obvious way; the spectral obstruction itself is
unchanged.

To obtain arbitrary-fugacity sign-freedom, one needs an additional invariant
that excludes negative real spectrum for every ordered word. Examples of genuinely
sufficient structures are:

- the full word `T_C` is SPD;
- the full word is always a product of exactly two SPD matrices;
- all SPD factors commute;
- a flavor-pairing or antiunitary mechanism makes the fermion factor an absolute
  square;
- another theorem directly proves that every word has no negative real eigenvalue.

Entrywise positivity, substochasticity, a single Metzler-exponential
parameterization, or closure under products of Metzler exponentials is not enough
for strict positivity at every fugacity.

Canonical fixed-particle-number positivity is a separate question. Positivity of
`det(I+zT)` on `z>0` does not by itself make every coefficient of that polynomial
nonnegative.

## 7. Boundary table

| Class | `det(I+zT)>0` for all `z>0`? | Sharp obstruction or safe reason |
|---|---:|---|
| General nonnegative strict-substochastic `T` | No | Exact `2×2` counterexample in section 2 |
| One Metzler exponential `e^A` | Not always strict; always `≥0` | Exact `3×3` even-multiplicity zero |
| Product of two Metzler exponentials | No | Exact minimal `3×3` negative interval |
| `T` itself SPD | Yes | Positive spectrum |
| Product of two SPD matrices | Yes | Similar to an SPD matrix |
| Product of three SPD, entrywise-nonnegative matrices | No | Exact `3×3` construction in section 5.2 |
| Arbitrary SPD product | No | Ballantine factorization plus `diag(-1,-2)` |
| Ordinary `ℓ∞` contraction | Only while `z||T||_∞<1` | Neumann/spectral-radius window |

## 8. Primary literature anchors

- W. J. Culver, "On the Existence and Uniqueness of the Real Logarithm of
  a Matrix," Proceedings of the American Mathematical Society 17,
  1146-1151 (1966). The real-logarithm criterion used in section 3:
  https://doi.org/10.1090/S0002-9939-1966-0202740-6

- E. B. Davies, "Embeddable Markov Matrices," Electronic Journal of Probability
  15, 1474-1486 (2010). Primary context for Markov matrices that are one
  generator exponential:
  https://doi.org/10.1214/EJP.v15-733
  and https://arxiv.org/abs/1001.1693

- Y. Chen and J. Chen, "On the Imbedding Problem for Three-State Time
  Homogeneous Markov Chains with Coinciding Negative Eigenvalues," Journal of
  Theoretical Probability 24, 928-938 (2011). Primary context for the
  three-state negative-doublet phenomenon:
  https://doi.org/10.1007/s10959-010-0316-5
  and https://arxiv.org/abs/1009.2152

- A. Davydov, S. Jafarpour, and F. Bullo, "Non-Euclidean Contraction Theory for
  Robust Nonlinear Stability," IEEE Transactions on Automatic Control 67
  (2022). Primary source for the `ℓ₁/ℓ∞` matrix-measure contraction framework;
  the finite-fugacity implication in section 2 is derived here:
  https://doi.org/10.1109/TAC.2022.3183966
  and https://arxiv.org/abs/2103.12263

- C. S. Ballantine, "Products of Positive Definite Matrices. I," Pacific Journal
  of Mathematics 23, 427-433 (1967). Primary `2×2` real-SPD factorization
  theorem used in section 5.3. The journal archive supplies a publisher PDF;
  no DOI is asserted here:
  https://msp.org/pjm/1967/23-3/pjm-v23-n3-p02-p.pdf

- C. S. Ballantine, "Products of Positive Definite Matrices. II," Pacific Journal
  of Mathematics 24, 7-17 (1968). Primary continuation and general-dimensional
  bounds:
  https://msp.org/pjm/1968/24-1/pjm-v24-n1-p02-s.pdf

- C. S. Ballantine, "Products of Positive Definite Matrices. IV," Linear Algebra
  and its Applications 3, 79-114 (1970). Primary later characterization:
  https://doi.org/10.1016/0024-3795(70)90030-3

- M. Abdelgalil and T. T. Georgiou, "The factorization of matrices into products
  of positive definite factors" (2025; revised 2026). Modern primary treatment
  of factor count and spectral effects:
  https://arxiv.org/abs/2507.12560

The `2×2` substochastic matrix, the explicit three-cycle exponential, the
two-exponential product, the exact three-factor doubly-nonnegative SPD example,
and all fugacity-window deductions in this note are our derivations. The cited
papers anchor the invoked general theorems and surrounding mathematical context;
they are not claimed as sources of those exact displayed counterexamples.
