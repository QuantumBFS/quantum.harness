# Sign-Problem-Free Hunter: Research Foundations

Status: initial evidence map, 2026-07-27. This document separates known
theorems, exact baseline certificates, derived observations, and open research
directions. A statement is not called new until it passes the novelty checklist
below.

## 1. The object we are studying

After a Hubbard--Stratonovich decoupling, a finite-temperature auxiliary-field
or determinantal QMC configuration has a fermionic weight of the form

```text
w(A_1, ..., A_L) = det(I + exp(A_1) exp(A_2) ... exp(A_L)).
```

The scalar Hubbard--Stratonovich prefactor must also be nonnegative, but the
challenge isolates the matrix part. A structured generator class is
sign-problem-free if `w >= 0` for every allowed product depth and every choice
of generators in the class.

This is stronger than observing positive weights in a particular simulation.
It is a uniform matrix statement that can certify a whole family of QMC
algorithms.

## 2. Known theorem anchors

### 2.1 Split orthogonal group

Let

```text
eta = diag(I_n, -I_n).
```

The split orthogonal group is

```text
O(n,n) = {M : M^T eta M = eta}.
```

Writing `M` in `n x n` blocks, its four components are labelled by the signs
of `det(M_11)` and `det(M_22)`. The exact sign theorem is

```text
det(I + M) >= 0  on O^{++}(n,n),
det(I + M) <= 0  on O^{--}(n,n),
det(I + M)  = 0  on the two mixed components.
```

The Lie algebra condition

```text
A^T eta + eta A = 0
```

ensures that every `exp(A)` lies in the identity component. Therefore every
finite product of such exponentials has nonnegative weight. This is the main
result of [Wang et al., PRL 115, 250601
(2015)](https://arxiv.org/abs/1506.05349), developed from the first
[MathOverflow question](https://mathoverflow.net/questions/204460/how-to-prove-this-determinant-is-positive).

In block form,

```text
A = [[C, B],
     [B^T, D]],
```

where `C` and `D` are real skew-symmetric. The original numerical conjecture
was the special case `C = D = 0`.

Unequal signatures do not give a new direction. If `M` is in the identity
component of `O(p,q)` and `r = max(p,q)`, pad the smaller-signature side with
an identity block. The padded matrix lies in the identity component of
`O(r,r)` and

```text
det(I + padded(M)) = 2^abs(p-q) det(I + M).
```

The split theorem therefore already implies nonnegativity on the identity
component of every `O(p,q)`. A search over unequal sublattice sizes must not
be reported as a new matrix class.

### 2.2 Majorana and Kramers positivity

Majorana reflection positivity gives a sufficient block-kernel condition for
positive configuration weights. In the notation of [Wei et al., PRL 116,
250601 (2016)](https://arxiv.org/abs/1601.01994), the kernel has the form

```text
V = [[ A,    i B],
     [-iB^T, A* ]],
```

where `A^T = -A` and Hermitian `B` is positive or negative semidefinite.

A second sufficient condition in the same paper is Majorana Kramers
positivity. For every coefficient matrix `V`, there must be fixed
transformations `S,P` with

```text
S^T V S = conjugate(V),
P V P^(-1) = V,
S^2 = -I,
P^2 = I,
P S = -S P.
```

`S` is real antisymmetric; `P` is a symmetric or antisymmetric Hermitian
involution. The first relation creates reciprocal-conjugate eigenvalue
quartets, while the second enforces the degeneracy needed when a quartet
collapses on the unit circle. A complex candidate is not new merely because
it lies outside the real split-orthogonal form; it must also fail this test.

A complementary classification by anticommuting Majorana time-reversal
symmetries found two fundamental sign-free symmetry classes, called the
Majorana and Kramers classes. It already contains a "periodic table" of
symmetry classes; see [Li, Jiang, and Yao, PRL 117, 267002
(2016)](https://arxiv.org/abs/1601.05780). Any proposed Altland--Zirnbauer
table must be distinguished explicitly from this prior classification.

### 2.3 Contraction semigroups

The real split-orthogonal condition has a cone extension

```text
A^T eta + eta A >= 0.
```

Products of the corresponding exponentials form a semigroup rather than a
group. The result first appeared through Majorana reflection positivity and an
independent matrix argument in the second
[MathOverflow question](https://mathoverflow.net/questions/229788/how-to-prove-this-determinant-is-positive-ii).
The broader contraction-semigroup framework is given in [Wei, PRB 110, 075146
(2024)](https://arxiv.org/abs/1712.09412).

For numerical generation, every matrix in this real cone can be written as

```text
A = K + eta H,
```

with `K^T eta + eta K = 0` and symmetric `H >= 0`, because then
`A^T eta + eta A = 2H`.

The full 2024 filter is broader than this real special case. For complex
skew-symmetric Majorana coefficient matrices `A`, it asks whether there are
two anticommuting real orthogonal matrices `J_1,J_2`, with `J_2`
skew-symmetric, such that

```text
J_1^T A J_1 = conjugate(A),
i (J_2 A - conjugate(A) J_2) <= 0.
```

`J_1` may be symmetric or skew-symmetric. The first condition makes the
fermionic trace real; the second places the evolution in a contraction
semigroup whose strict interior cannot cross zero. Equality reduces to known
symmetry mechanisms, while the cone contains Majorana reflection positivity
and a Kramers-plus-pairing class. A novelty check against only
`A^T eta + eta A >= 0` is therefore insufficient.

For the totally nonnegative path class, this broader check is now complete:
the allowed `+D/-D` diagonal directions force the cone inequality to equality,
and the resulting site-local anticommutation relations are incompatible with
`J_2^2=-I`, even after a fixed complex orthogonal Majorana basis change. See
[TN_NOVELTY_AUDIT.md](TN_NOVELTY_AUDIT.md).

### 2.4 Pseudo-unitary prior art

The split unitary direction is not untouched. For

```text
U(p,q) = {D : D^dagger eta D = eta},
```

the following identity holds:

```text
conj(det(I + D)) = det(D)^(-1) det(I + D).              (1)
```

It follows directly from `D^dagger = eta D^(-1) eta`. Thus the phase of the
weight is locked to half the phase of `det(D)`, modulo pi. In particular,
`det(I + D)` is real on `SU(p,q)`, but need not be nonnegative.

For the QMC product `D = product_l exp(A_l)`, noncommutativity does not affect
the determinant:

```text
det(D) = exp(sum_l trace(A_l)).
```

The configuration-weight phase is therefore

```text
arg(w) = Im(sum_l trace(A_l))/2  modulo pi.
```

This separates a known, additive phase from a residual binary sign. If the
trace phase is configuration-independent it is only a global factor; if an HS
prefactor supplies the inverse phase it may be cancelled; if every generator
is traceless, the weight is real. None of these observations alone fixes the
remaining sign.

Appendix B of [Xu et al., PRX 9, 021022
(2019)](https://arxiv.org/abs/1807.07574) proves the `SU(p,q)` reality result
and uses an even number of fermion flavours so that the total weight is
nonnegative. Equation (1) is a direct extension to `U(p,q)` and must be treated
as a prior-art-adjacent observation, not yet as a novel result.

## 3. Exact baseline certificates

These small certificates should become non-floating-point tests for the
oracle.

### 3.1 Four components of O(1,1)

With `eta = diag(1,-1)`, the following rational matrices satisfy
`M^T eta M = eta`:

```text
M_{++} = [[ 5/3,  4/3],    det(I + M_{++}) = 16/3,
          [ 4/3,  5/3]]

M_{--} = [[-5/3, -4/3],    det(I + M_{--}) = -4/3,
          [-4/3, -5/3]]

M_{+-} = diag( 1,-1),      det(I + M_{+-}) = 0,
M_{-+} = diag(-1, 1),      det(I + M_{-+}) = 0.
```

They exercise every branch of the exact group theorem and catch an oracle
that silently labels every group element positive.

### 3.2 Exact symplectic counterexample

For `n = 1`, `Sp(2,R) = SL(2,R)`. Define symplectic shears

```text
U(x) = [[1,x],[0,1]] = exp([[0,x],[0,0]]),
L(y) = [[1,0],[y,1]] = exp([[0,0],[y,0]]).
```

Each exponent is a rational element of `sp(2,R)`. The exact product

```text
U(-3) L(1) U(-3/2) L(2) = diag(-2,-1/2)
```

satisfies `D^T J D = J`, where `J = [[0,1],[-1,0]]`, but

```text
det(I + D) = -1/2.
```

This is an exact rational, product-of-exponentials certificate that the real
symplectic group does not give a universally nonnegative determinant class.
It is a strong negative control, not a novelty claim.

The obstruction persists in every higher rank: take the direct sum of this
`2 x 2` block with `I_(2n-2)`. The result lies in `Sp(2n,R)` and has

```text
det(I + D_n) = (-1/2) 2^(2n-2) < 0.
```

### 3.3 Exact SU(1,1) negative examples and a similarity reduction

The 2019 pseudo-unitary paper supplies

```text
D = [[-sqrt(2), 1],
     [1, -sqrt(2)]] in SU(1,1),

det(I + D) = 2 - 2 sqrt(2) < 0.
```

This distinguishes "the determinant is real" from "the determinant is
nonnegative." Squaring the one-flavour determinant, as happens for two
identical flavours, removes this sign.

There is also a rational certificate. The fixed Cayley transform

```text
C = (1/sqrt(2)) [[1,-i],
                 [1, i]]
```

maps `SL(2,R) = Sp(2,R)` to `SU(1,1)`. Applying it to the symplectic
certificate above gives

```text
C diag(-2,-1/2) C^(-1)
    = [[-5/4,-3/4],
       [-3/4,-5/4]] in SU(1,1),

det(I + C D C^(-1)) = -1/2.
```

Because the determinant weight is invariant under a fixed similarity
transformation, the lowest-dimensional `Sp(2,R)` and `SU(1,1)` negative
directions are the same obstruction in different bases. They must not be
counted as two independent findings.

Embedding the rational `SU(1,1)` block and filling all other positive and
negative directions with identities gives, for every `p,q >= 1`, an element
of `SU(p,q)` with

```text
det(I + D_(p,q)) = (-1/2) 2^(p+q-2) < 0.
```

Thus a single fermion flavour fails universally across the noncompact
pseudo-unitary family; the useful known statement is phase/reality control,
followed by even-flavour squaring.

### 3.4 Small classical-group smoke table

The following analytic checks are useful before attempting a large
Altland--Zirnbauer sweep. They are calibration facts, not novelty claims.

| Matrix group | Sign of `det(I+D)` | Reason or exact obstruction |
|---|---|---|
| `O(n)` | nonnegative | non-real eigenvalues pair as conjugates; `det(D)=-1` forces a `-1` eigenvalue and hence zero weight |
| identity component of `O(p,q)` | nonnegative | padding reduction to the split `O(r,r)` theorem |
| `Sp(2n,R)` | can be negative | rational shear certificate above, padded by identities |
| compact `USp(2n)` | nonnegative | conjugate/Kramers eigenvalue pairing; already a known mechanism |
| `SU(2)` | nonnegative | eigenvalues are `lambda` and `conj(lambda)` |
| `SU(n)`, `n >= 3` | can be negative | with `zeta = exp(2 pi i/n)`, `D = zeta I_n` has weight `(1+zeta)^n = -(2 cos(pi/n))^n` |
| `SU(p,q)`, `p,q >= 1` | real but can be negative | rational embedded `SU(1,1)` certificate above |
| `U(p,q)` | fixed phase, not fixed sign | equation (1) locks the phase to `arg(det(D))/2` modulo `pi` |

The surviving compact rows are immediately suspect of reducing to orthogonal
or Kramers pairing. The noncompact symplectic and pseudo-unitary rows are
already eliminated as universal one-flavour nonnegative classes.

## 4. Novelty checklist

Before treating a surviving candidate as new, check all of the following.

1. **Similarity or basis change:** can a fixed invertible transformation map
   every generator to the split-orthogonal or Majorana-reflection-positive
   form?
2. **Kramers pairing:** is nonnegativity just complex-conjugate eigenvalue
   pairing plus even degeneracy?
3. **Majorana symmetry class:** does the generator set contain one of the two
   already sign-free Majorana time-reversal classes?
4. **Semigroup cone:** does the candidate satisfy an existing contraction
   inequality after a change of metric?
5. **Flavour squaring:** is positivity obtained only by taking an even power
   of a merely real determinant?
6. **Configuration prefactor:** can a deterministic phase be absorbed into
   the Hubbard--Stratonovich prefactor without making that prefactor
   sign- or phase-problematic?
7. **Physical realization:** identify hopping, pairing, and auxiliary-field
   bilinears whose single-particle matrices are exactly the proposed
   generators.
8. **Quantifiers:** verify that the statement holds for every product depth,
   not only for single exponentials or commuting generators.

## 5. Oracle requirements

The first implementation should have three layers.

1. **Structure layer:** construct generators and report residuals for the
   claimed algebra/cone constraints.
2. **Numerical layer:** form products of matrix exponentials, record the sign
   or phase of `det(I+product)`, the logarithmic magnitude, condition number,
   group/semigroup residuals, dimension, depth, seed, and sample index.
3. **Exact layer:** express small counterexamples with SymPy rationals,
   radicals, or nilpotent exponentials and verify the defining matrix identity
   and determinant symbolically.

Numerical outcomes near zero are `uncertain`, not positive or negative.
Suspect cases must be recomputed at increasing precision. Floating-point
output alone can reject a conjecture only provisionally; the final
counterexample is the exact certificate.

The initial regression suite should include:

- the four exact `O(1,1)` component controls above;
- random split-orthogonal Lie-algebra products with nonnegative weights;
- random semigroup-cone products with nonnegative weights;
- the exact rational `Sp(2,R)` counterexample;
- the exact `SU(1,1)` negative example and its positive even-flavour square;
- deterministic replay from a recorded seed.

For report readiness, committed code and small exact certificates should stay
under `tracks/qmc/solutions/no-negative-vibes/`. Generated scans belong under
`tracks/qmc/results/<run-id>/` and should retain a `run.json`, per-cell
manifests, machine-readable tables, and plots. The final narrative must state
the sampled dimensions, depths, sample counts, seeds, precision escalation
policy, software versions, and which claims are exact versus empirical.

## 6. Direction triage

| Direction | Current assessment | Immediate value | Main risk |
|---|---|---|---|
| `Sp(2n,R)` | Closed negatively at `n=1` by the exact certificate above | Excellent oracle/exact-arithmetic baseline | Low novelty by itself |
| `U(p,q)` / `SU(p,q)` | Phase locking and `SU` reality are already known; sign can be negative | A clean bridge between phase constraints and even-flavour sign freedom | Easy to rediscover prior art |
| Classical/AZ table | Potentially broad and physically meaningful | Systematic map of positive, negative, zero, and fixed-phase structures | Must not duplicate the 2016 Majorana symmetry table |
| Semigroup extensions | Natural next step for any group entry that survives | Could produce genuinely larger generator cones | The 2024 framework is broad and may already subsume it |
| Complex Majorana matrix formulation | Explicitly open in the challenge | Clear theorem-level target | Highest mathematical difficulty |
| Free-form generator search | Well matched to an automated oracle | May reveal unexpected small classes | Severe multiple-testing and novelty burden |

Recommended order:

1. implement and validate the oracle against the exact anchors;
2. ship the symplectic negative certificate as the first closed direction;
3. reproduce pseudo-unitary phase locking and prior-art examples;
4. choose one narrowly defined extension only after the novelty checklist;
5. map a surviving class to a concrete Hubbard--Stratonovich decoupling before
   investing in a full proof.

## 7. Primary sources

- [Challenge issue #121](https://github.com/QuantumBFS/quantum.harness/issues/121)
- [MathOverflow I](https://mathoverflow.net/questions/204460/how-to-prove-this-determinant-is-positive)
- [Tao, standard branch of the matrix logarithm](https://terrytao.wordpress.com/2015/05/03/the-standard-branch-of-the-matrix-logarithm/)
- [Wang et al., split orthogonal group](https://arxiv.org/abs/1506.05349)
- [Wu and Zhang, Kramers time-reversal condition](https://arxiv.org/abs/cond-mat/0407272)
- [MathOverflow II](https://mathoverflow.net/questions/229788/how-to-prove-this-determinant-is-positive-ii)
- [Wei et al., Majorana positivity](https://arxiv.org/abs/1601.01994)
- [Li, Jiang, and Yao, Majorana time-reversal classes](https://arxiv.org/abs/1601.05780)
- [Wei, contraction semigroups](https://arxiv.org/abs/1712.09412)
- [Xu et al., pseudo-unitary `SU(p,q)` application](https://arxiv.org/abs/1807.07574)
- [Li and Yao, sign-problem-free fermionic QMC review](https://arxiv.org/abs/1805.08219)
