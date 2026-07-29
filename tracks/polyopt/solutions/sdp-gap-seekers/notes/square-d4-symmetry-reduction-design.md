# Square J1-J2 — D4 symmetry-restricted reduction (design)

Date: 2026-07-29
Status: design, pending Sihan coordination (Feishu) before implementation.

## Why

The unrestricted (`NoStateSymmetry`) Square J1-J2 relaxation hits a hard
computational wall above Rung A:

- Rung A (`bare_weight_one`, 28 positive / 4 gap, 56-dim real PSD): feasible in
  1.4 s, but too weak — feasible at every γ, so it cannot upper-bound the gap.
- Rung B (`bare_operator` degree-2, 352 / 4, 704-dim real PSD): intractable.
  OOM at 122 GB and at 250 GB; on a 499 GB node it ran 32 min with **zero**
  interior-point iterations (stuck in the first Schur/factorization). Cost grows
  ~PSD-dim³, so there is no tractable integer-degree rung between A and B.

Symmetry restriction is the proven tractable direction (the SS exact-reduction
showed 39×/52× speedup). The patch point-group **D4** is the cheapest first
generator (finite group, already supported by the L=1 patch geometry, no
momentum/Bloch reformulation needed).

## Scope and labelling

This produces a **D4-symmetric-state bulk-gap upper bound**, not the
unrestricted bound. Every result must be reported as
"symmetry-restricted to the D4-invariant KMS states" with the generator list
`⟨C4, σv⟩`. It does not commute with the advisor's "unsymmetrized first" — it
supersedes it for Square, because the unsymmetrized stronger rungs are
demonstrably out of reach on the available hardware.

## Patch and group (verified)

`Λ_1 = [-1,1]² ∩ ℤ²`, 9 sites, lexicographic ordering:

```text
1=(-1,-1) 2=(-1,0) 3=(-1,1) 4=(0,-1) 5=(0,0) 6=(0,1) 7=(1,-1) 8=(1,0) 9=(1,1)
```

Inner patch `I_1 = {5}` (the centre). The patch is invariant under `C4: (x,y)↦(-y,x)`
and `σ: (x,y)↦(x,-y)` (both verified by closure). `D4 = ⟨C4, σ⟩`, order 8.

`D4` irreps: `A1, A2, B1, B2` (1-dim) and `E` (2-dim); `Σ d_λ² = 8`.

## Group action

A spatial symmetry `g ∈ D4` acts on a canonical Pauli word by **relabeling
sites, leaving the Pauli axis unchanged** (spatial symmetry does not rotate
spin):

```text
g · [(s1,a1), …, (sk,ak)] = sort [(g(s1),a1), …, (g(sk),ak)]
```

This is an automorphism with phase `+1`. It lifts to state symbols
`ζ(w) ↦ ζ(g·w)` and to scalar moments. The Hamiltonian terms are mapped to
Hamiltonian terms (the J1/J2 bond set is D4-invariant), so `[H, ·]` commutes
with the action — the commutator-energy `K` and the gap matrix `A_γ` are
D4-equivariant.

## Block-diagonalization

For a D4-invariant state, `L(ζ(g·p)) = L(ζ(p))`, so the positive moment matrix
`M[j,k] = L(ζ(b_j† b_k))` commutes with the D4 representation `U(g) b_j = g·b_j`.
`M` therefore block-diagonalizes into the irrep sectors. Concretely:

1. Build the real orthogonal matrix `b_j ↦ (irrep components)` from the
   projection operators `P_λ = (d_λ/8) Σ_g χ_λ(g)* U(g)`. For the 1-dim irreps
   this is a signed incidence; for `E` a 2-column basis per copy.
2. Conjugate each PSD block `M`, `A_γ` into block-diagonal form
   `Qᵀ M Q = ⊕_λ M_λ`. Each `M_λ ⪰ 0` is an independent, smaller PSD.
3. The stationarity equalities and `L(1)=1` are likewise projected (they live
   in the `A1` sector plus the identity).

The JuMP model then carries one `HermitianPSDCone` per `(role, irrep)` block
instead of one 352-dim cone. The scalar-moment variable count also drops
(many moments are symmetry-equated).

## Expected tractability

The 352 bare degree-2 words decompose over `D4`; the largest sector is the
`E` copy, typically O(352/5·2) ≈ 100–140 dim. A 140-dim PSD costs
`(140/704)³ ≈ 1/125` of Rung B's factorization → minutes and a few GB, well
inside the 123 GB Kunshan nodes (and trivially on xh5). This should turn the
intractable Rung B into a runnable Rung B′.

## Implementation plan (module: `src/SquareSymmetryD4.jl`)

1. `d4_site_permutations(patch)` → `Vector{Dict{Int,Int}}` (8 elements), with a
   unit test that the set is a closed group and that bond sites map to bond
   sites.
2. `apply_d4(g, word::PauliWord)` → `PauliWord`; orbit/orbit-stabilizer helpers.
3. `d4_character_table()` → the 5 irreps with their characters.
4. `irrep_projection(basis_entries, d4)` → for each irrep `λ`, an explicit real
   basis (columns of `Q_λ`) for the `λ`-isotypic subspace of the
   positive/gap/operator-word space. Deterministic, hashed.
5. `block_diagonalize_core_mgk(plan, projections)` → re-express `M`, `K`, `G`
   per irrep block, using the existing exact `CoreMGK` coefficients conjugated
   by `Q`.
6. Extend `SquareGapConic` to emit one PSD cone per `(role, irrep)` block plus
   the projected stationarity + normalization; keep the runmeta/labelling
   fields stating `symmetry = D4, generators = [C4, σ]`.
7. Validation gate (must pass before any solve):
   - reconstruct the full unrestricted `M` from the blocks and confirm it
     equals the `CoreMGK` `M` coefficient-for-coefficient (block-diag is an
     exact reparameterization of the restricted problem);
   - confirm each block is Hermitian with real diagonal;
   - confirm the Hamiltonian/stationarity commutes with `D4`.

## Open questions for Sihan / advisor

- Does Sihan already have Square spatial-symmetry (D4 / translation) machinery
  on a branch? (Their SS reduction docs are spin-conjugation / continuous-spin,
  not spatial — but worth confirming before I build D4 from scratch.)
- Is D4 the right first generator, or should we start from a single mirror
  (`σ`, order-2, simplest possible projection) to de-risk before the full D4?
- The result is a D4-restricted bound. Is that an acceptable headline for issue
  #88, or only a stepping stone toward translation/C4-blocked momentum bases?
