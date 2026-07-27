# Theory problems for offloading — SDP spectral gap certification on square-lattice J1-J2

> These are self-contained mathematical problems. The context is semidefinite
> programming (SDP) certification of spectral gaps in quantum spin systems via
> the noncommutative polynomial optimization (NCSOS / moment-SOS) hierarchy.
> References: Wang et al., "Scalable Ground-State Certification of Quantum Spin
> Systems via Structured Noncommutative Polynomial Optimization,"
> arXiv:2604.01555 (2026); the SpectralGap code at
> `wangjie212/SpectralGap` (file `src/sdp.jl`).

## Model

Square-lattice spin-1/2 antiferromagnetic J1-J2 Heisenberg model:

$$H = J_1 \sum_{\langle i,j \rangle} \vec{S}_i \cdot \vec{S}_j + J_2 \sum_{\langle\langle i,j \rangle\rangle} \vec{S}_i \cdot \vec{S}_j$$

on an L×L lattice with periodic boundary conditions. Here ⟨i,j⟩ are nearest-neighbor bonds (horizontal/vertical) and ⟨⟨i,j⟩⟩ are next-nearest-neighbor bonds (diagonal). The ratio g = J₂/J₁ controls frustration: g=0 is the unfrustrated square-lattice Heisenberg model; g ≈ 0.5 is near the Néel-to-VBS transition (its nature — direct vs. via an intermediate spin liquid — is debated).

Each site carries spin-1/2 operators S^α_i (α = x, y, z) satisfying [S^α_i, S^β_j] = i δ_{ij} ε_{αβγ} S^γ_i and (S^α_i)² = 1/4.

---

## Problem A (hardest, highest priority): The gap-certification SDP formulation

### Background: energy certification works

The standard NCSOS hierarchy certifies a **lower bound** on the ground-state
energy. At relaxation level d, one builds a moment matrix M_d(y) whose entries
are expectation values y_α = ⟨ψ|O_α|ψ⟩ of NC monomials O_α up to degree d. The
constraint M_d ≽ 0 (positive semidefinite) plus the localizing constraints
(gₖ M_d gₖ^† ≽ 0 for each defining polynomial gₖ, e.g., (S^α_i)² = 1/4)
restricts y to the set of valid quantum moments. Minimizing ⟨H⟩ over this
feasible set gives a certified lower bound on E₀.

This is implemented and working (QMBCertify.jl).

### The open problem: certify the spectral gap Δ = E₁ − E₀

To certify an **upper bound** on the gap — i.e., prove Δ ≤ γ — one must show
that a state exists with energy ≤ E₀ + γ that is **orthogonal to the ground
state**. The challenge: the ground state is unknown, so orthogonality cannot be
encoded directly.

The SpectralGap code (arXiv:2604.01555, Sec. on spectral gaps) handles this for
the 1D transverse-field Ising model and the kagome Heisenberg model. The
formulation uses:

1. A **gap-variable SDP**: introduce a scalar γ and ask whether the SDP
   "minimize ⟨H⟩ subject to: the state has support in the orthogonal complement
   of the ground-state sector" is feasible. If the minimum is ≥ E₀ + γ, the gap
   is certified.

2. **Strengthening constraints**: additional polynomial identities valid for the
   specific model that tighten the relaxation (see Problem B).

3. **Sign symmetry**: for bipartite antiferromagnets, the sign-flip symmetry
   (S^z_i → (−1)^i S^z_i on sublattice A vs. B) block-diagonalizes the moment
   matrix, halving the effective dimension.

### What we need

A concrete, self-contained derivation of the gap-certification SDP for the
**square-lattice J1-J2 Heisenberg model**. Specifically:

1. **Moment matrix structure**: what NC monomials appear in M_d for this model
   at level d? What is the matrix dimension as a function of L and d?

2. **The orthogonality encoding**: how is "state orthogonal to the ground state"
   encoded as an SDP constraint? The SpectralGap approach for Ising/kagome uses
   a specific reformulation — derive the analogous one for the square-lattice
   Heisenberg model. Reference: read `src/sdp.jl` and `src/strengthening.jl` in
   the SpectralGap repository for the existing implementations.

3. **The bisection protocol**: the certification is binary (feasible/infeasible
   at a given γ). What is the correct SDP to solve at each bisection step?
   What does OPTIMAL vs. DUAL_INFEASIBLE mean physically?

4. **Scaling estimate**: at what (L, d) does the SDP matrix become too large
   for Mosek (roughly: matrices > 10⁴×10⁴ are expensive, > 10⁵ are infeasible)?
   What is the largest (L, d) we can hope to solve?

**Deliverable**: a mathematical specification complete enough that a programmer
can implement `certify_Heisenberg_square_gap(L, g, gamma, d)` in Julia/JuMP
without additional theory work.

---

## Problem B (medium priority): Strengthening identities for the square lattice

### Background

The raw NCSOS relaxation gives loose bounds at low d. "Strengthening" adds
**valid polynomial identities** — equalities that hold for all physical states
of the model — as additional linear constraints on the moment vector y. These
are model-specific.

For the kagome Heisenberg model, the SpectralGap code uses triangle-based
identities: on each 3-site triangle, the projector onto total spin S=0 is
P₀ = 1/3 − (2/3) S⃗ᵢ·S⃗ⱼ − (2/3) S⃗ᵢ·S⃗ₖ − (2/3) S⃗ⱼ·S⃗ₖ + (4/3)(S⃗ᵢ·S⃗ⱼ)(S⃗ᵢ·S⃗ₖ) + ….
These projectors give polynomial identities that the moment vector must satisfy.

### What we need

The analogous identities for the **square lattice**:

1. **Bond projectors**: for a spin-1/2 pair ⟨i,j⟩, the singlet projector is
   P_{ij}^{(0)} = 1/4 − S⃗ᵢ·S⃗ⱼ. The triplet projector is P_{ij}^{(1)} = 3/4 +
   S⃗ᵢ·S⃗ⱼ. What identities follow from P² = P and P^{(0)} + P^{(1)} = 1?

2. **Plaquette operators**: on a 4-site square plaquette (sites 1,2,3,4), the
   total spin of the plaquette S_total = Σᵢ S⃗ᵢ satisfies Casimir-type
   identities. What are the polynomial identities for S²_total, and how do they
   constrain the moment vector?

3. **Sum rules**: for the J1-J2 model on a square lattice, are there lattice-
   level sum rules (e.g., Σ_{⟨ij⟩} S⃗ᵢ·S⃗ⱼ = const · S²_total / N) that provide
   additional constraints?

4. **J2-specific identities**: the next-nearest-neighbor coupling introduces
   diagonal bonds. Do these create new polynomial structures not present in the
   J1-only model?

**Deliverable**: a list of valid polynomial identities (each written as
"monomial combination = constant"), with a brief note on which ones are
expected to tighten the gap bound most. Prioritize identities involving ≤ 4
sites (so they fit in low-d moment matrices).

---

## Problem C (lower priority): Symmetry block-diagonalization

### Background

The square-lattice J1-J2 Heisenberg model with periodic BC has symmetry group:

G = (Z_L × Z_L) ⋊ D₄ × SU(2)

where Z_L × Z_L are lattice translations, D₄ is the point group of the square
(C₄ rotations + reflections), and SU(2) is the global spin-rotation symmetry.

The moment matrix M_d is indexed by NC monomials in S^x, S^y, S^z at all sites.
Without symmetry exploitation, the matrix dimension grows combinatorially.
Block-diagonalizing via symmetries reduces it by a factor of ~|G|/2.

### What we need

1. **Irrep decomposition**: how does G act on the monomial basis at degree d?
   What are the irreducible blocks?

2. **Which block contains the gap**: the ground state is in the trivial irrep
   (translation-invariant, A₁, SU(2) singlet). The first excited state is in
   which irrep? (For the square-lattice Heisenberg model, the one-magnon
   sector has momentum k and spin S=1.)

3. **Block sizes**: what is the dimension of each block as a function of L and d?

**Deliverable**: a block-diagonal structure specification that tells us which
submatrix to keep and which to discard, reducing the SDP size.

---

## How to use this note

- **Problem A** is the hardest and most valuable — it's the core theoretical
  contribution. If the theory model can derive the gap SDP formulation, the rest
  is implementation.
- **Problem B** is algebra — derive polynomial identities for the square lattice
  by analogy to the kagome case.
- **Problem C** is representation theory — standard but tedious.
- The SpectralGap code (`wangjie212/SpectralGap`, files `src/sdp.jl`,
  `src/strengthening.jl`, `src/basicfunction.jl`) contains the existing
  implementations for Ising and kagome. Reading these shows the *code pattern*;
  the theory model should derive the *mathematical content* for the square
  lattice.
- QMBCertify (`wangjie212/QMBCertify`) handles energy certification for square
  Heisenberg — its symmetry and sparsity code may already contain parts of the
  answer.
