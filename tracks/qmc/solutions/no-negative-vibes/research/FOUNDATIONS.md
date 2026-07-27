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

### 2.2 Majorana and Kramers positivity

Majorana reflection positivity gives a sufficient block-kernel condition for
positive configuration weights. In the notation of [Wei et al., PRL 116,
250601 (2016)](https://arxiv.org/abs/1601.01994), the kernel has the form

```text
V = [[ A,    i B],
     [-iB^T, A* ]],
```

where `A^T = -A` and Hermitian `B` is positive or negative semidefinite.

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

### 3.3 Exact SU(1,1) negative example

The 2019 pseudo-unitary paper supplies

```text
D = [[-sqrt(2), 1],
     [1, -sqrt(2)]] in SU(1,1),

det(I + D) = 2 - 2 sqrt(2) < 0.
```

This distinguishes "the determinant is real" from "the determinant is
nonnegative." Squaring the one-flavour determinant, as happens for two
identical flavours, removes this sign.

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
- [MathOverflow II](https://mathoverflow.net/questions/229788/how-to-prove-this-determinant-is-positive-ii)
- [Wei et al., Majorana positivity](https://arxiv.org/abs/1601.01994)
- [Li, Jiang, and Yao, Majorana time-reversal classes](https://arxiv.org/abs/1601.05780)
- [Wei, contraction semigroups](https://arxiv.org/abs/1712.09412)
- [Xu et al., pseudo-unitary `SU(p,q)` application](https://arxiv.org/abs/1807.07574)
- [Li and Yao, sign-problem-free fermionic QMC review](https://arxiv.org/abs/1805.08219)
